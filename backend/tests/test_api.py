"""HTTP API, WebSocket broadcast, simulation and demo seeding (integration)."""
import time

DEV = {"device_id": "KH-S01", "mac_address": "AA:BB:CC:DD:EE:FF", "firmware_version": "1.0.0"}


def telemetry(dev="KH-S01", state="NORMAL", score=0.05):
    return {"device_id": dev, "motion_score": score, "motion_state": state, "acceleration_magnitude": 1.0,
            "angular_velocity": 0.1, "orientation_change": 2.0}


def test_health(client):
    r = client.get("/api/health").json()
    assert r["backend"] == "OK" and r["database"] == "READY"


def test_settings_hide_secrets(client):
    s = client.get("/api/settings").json()
    assert "database_url" not in s and "device_api_key" not in s and "device_api_key_required" in s


def test_invalid_payloads_get_readable_errors(client):
    r = client.post("/api/device/telemetry", json={**telemetry(), "motion_score": 7})
    assert r.status_code == 422 and "motion_score" in r.json()["detail"]
    assert client.post("/api/device/register", json={"device_id": "x"}).status_code == 422
    assert client.post("/api/classes/end").status_code == 409
    assert client.get("/api/classes/999").status_code == 404
    assert client.get("/api/devices/nope").status_code == 404


def test_full_class_flow(client):
    assert client.post("/api/device/register", json=DEV).json()["registered"]
    r = client.post("/api/classes/start", json={"name": "Physics", "duration_minutes": 50})
    assert r.status_code == 201
    cid = r.json()["id"]
    assert client.post("/api/classes/start", json={"name": "Again"}).status_code == 409

    hb = client.post("/api/device/heartbeat", json={"device_id": "KH-S01", "rssi": -55, "sensor_ok": True}).json()
    assert hb["class_active"] is True
    assert client.post("/api/device/telemetry", json=telemetry()).json()["stored"] is True
    assert client.post("/api/device/feedback", json={"device_id": "KH-S01", "event": "FEEDBACK_TRIGGERED"}).status_code == 200
    assert client.post("/api/device/feedback", json={"device_id": "KH-S01", "event": "FEEDBACK_ACKNOWLEDGED"}).status_code == 200

    cur = client.get("/api/classes/current").json()
    assert cur["active"] and cur["class"]["id"] == cid
    devices = client.get("/api/devices").json()
    assert devices[0]["device_id"] == "KH-S01" and devices[0]["status"] == "CONNECTED"
    assert client.patch("/api/devices/KH-S01", json={"student_label": "Bench unit"}).json()["student_label"] == "Bench unit"

    assert client.post("/api/classes/end").json()["status"] == "ENDED"
    a = client.get(f"/api/classes/{cid}/analytics").json()
    assert a["summary"]["total_registered"] == 1 and a["summary"]["feedback_acknowledged"] == 1
    assert client.get(f"/api/classes/{cid}/timeline").json()["devices"][0]["device_id"] == "KH-S01"
    ev = client.get(f"/api/classes/{cid}/events").json()
    assert {e["event_type"] for e in ev["log"]} >= {"CLASS_STARTED", "CLASS_ENDED", "DEVICE_CONNECTED"}
    assert client.get("/api/classes").json()[0]["id"] == cid


def test_optional_device_key(tmp_path):
    from fastapi.testclient import TestClient
    from app.config import Settings
    from app.main import create_app
    s = Settings(database_url=f"sqlite:///{(tmp_path / 'k.db').as_posix()}", run_monitor=False, device_api_key="secret")
    with TestClient(create_app(s)) as c:
        assert c.post("/api/device/register", json=DEV).status_code == 401
        assert c.post("/api/device/register", json=DEV, headers={"X-KH-Key": "secret"}).status_code == 200
        assert c.get("/api/health").status_code == 200        # dashboard endpoints stay open


def test_websocket_broadcasts_snapshots_and_events(client):
    with client.websocket_connect("/ws/dashboard") as ws:
        assert ws.receive_json()["type"] == "hello"
        first = ws.receive_json()
        assert first["type"] == "snapshot" and first["metrics"]["class_active"] is False
        client.post("/api/classes/start", json={"name": "Physics"})
        client.post("/api/device/register", json=DEV)
        seen_event, seen_snapshot_with_device = False, False
        deadline = time.time() + 6
        while time.time() < deadline and not (seen_event and seen_snapshot_with_device):
            msg = ws.receive_json()
            if msg["type"] == "event" and msg["event"]["event_type"] in ("CLASS_STARTED", "DEVICE_CONNECTED"):
                seen_event = True
            if msg["type"] == "snapshot" and msg["metrics"]["connected"] == 1:
                seen_snapshot_with_device = True
        assert seen_event and seen_snapshot_with_device


def test_websocket_ping_pong(client):
    with client.websocket_connect("/ws/dashboard") as ws:
        ws.receive_json(); ws.receive_json()
        ws.send_text("ping")
        while True:
            m = ws.receive_json()
            if m["type"] == "pong":
                break


def test_simulation_controls_and_labelling(client, app):
    client.post("/api/classes/start", json={"name": "Sim class"})
    added = client.post("/api/sim/add", json={"count": 5}).json()
    assert added["count"] == 5 and all(i.startswith("SIM-") for i in added["added"])
    sim = app.state.sim
    for _ in range(3):
        for st in sim.students.values():          # make everyone due, then tick synchronously
            st.next_hb = st.next_tel = 0
        sim.tick()
    snap = client.get("/api/devices").json()
    assert len(snap) == 5 and all(d["source"] == "SIMULATED" and d["status"] == "CONNECTED" for d in snap)
    assert client.post("/api/sim/disconnect-random?count=2").json()["disconnected"]
    assert client.post("/api/sim/reconnect-all").json()["reconnected"]
    assert client.post("/api/sim/scenario", json={"scenario": "drift_wave", "fraction": 0.6}).json()["devices"]
    assert client.post("/api/sim/clear").json()["removed"] == 5
    assert client.post("/api/sim/disconnect-random").status_code == 409     # nothing left to disconnect


def test_demo_seed_creates_labelled_ended_class(client):
    r = client.post("/api/demo/seed")
    assert r.status_code == 201
    cid = r.json()["class_id"] if "class_id" in r.json() else r.json()["id"]
    a = client.get(f"/api/classes/{cid}/analytics").json()
    assert a["class"]["is_demo"] and a["class"]["status"] == "ENDED"
    assert "DEMO" in a["class"]["name"] and "SIMULATED" in a["class"]["name"]
    assert a["summary"]["total_registered"] >= 20
    assert a["summary"]["joined_after_start"] >= 1 and a["summary"]["disconnected_at_least_once"] >= 1
    assert len(a["windows"]) == 6 and a["peak"] is not None
    assert all(w["engagement_percentage"] is not None for w in a["windows"])


def test_eeg_status_endpoints(client):
    st = client.get("/api/eeg/status").json()
    assert st["mode"] == "OFF"
    assert client.post("/api/eeg/features", json={"source": "PHYSICAL_EEG", "delta": 1, "theta": 1, "alpha": 1,
                                                   "beta": 1, "gamma": 1}).status_code == 409
