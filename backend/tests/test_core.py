"""Class control, device registration, heartbeat supervision, reconnection, telemetry handling."""
import pytest
from pydantic import ValidationError

from app.errors import ClassNotActiveError, ConflictError
from app.schemas import (ClassStartIn, DeviceRegisterIn, FeedbackIn, HeartbeatIn, TelemetryIn)

from conftest import at


def hb(core, dev, t):
    return core.heartbeat(HeartbeatIn(device_id=dev), now=at(t))


def tel(core, dev, t, state="NORMAL", score=0.05):
    return core.telemetry(TelemetryIn(device_id=dev, motion_score=score, motion_state=state, acceleration_magnitude=1.0,
                                      angular_velocity=0.1, orientation_change=2.0), now=at(t))


def test_database_initialises(core):
    assert core.db.healthy()
    assert core.current_class() is None


def test_start_and_end_class(core):
    c = core.start_class(ClassStartIn(name="Physics", duration_minutes=50), now=at(0))
    assert c["status"] == "ACTIVE" and c["scheduled_end"] is not None
    assert core.current_class()["id"] == c["id"]
    with pytest.raises(ConflictError):
        core.start_class(ClassStartIn(name="Second"), now=at(5))
    ended = core.end_class(now=at(600))
    assert ended["status"] == "ENDED" and ended["elapsed_seconds"] == 600
    with pytest.raises(ClassNotActiveError):
        core.end_class(now=at(601))
    core.start_class(ClassStartIn(name="Next"), now=at(700))      # a new class can start after the previous ended


def test_scheduled_end_must_be_in_future(core):
    from datetime import timedelta
    with pytest.raises(ConflictError):
        core.start_class(ClassStartIn(name="Bad", scheduled_end=at(-10)), now=at(0))


def test_device_registration(core):
    r = core.register_device(DeviceRegisterIn(device_id="KH-S01", mac_address="AA:BB:CC:DD:EE:FF", firmware_version="1.0.0"), now=at(0))
    assert r["registered"] and not r["already_registered"] and r["source"] == "REAL"
    again = core.register_device(DeviceRegisterIn(device_id="KH-S01"), now=at(1))
    assert again["already_registered"]
    sim = core.register_device(DeviceRegisterIn(device_id="SIM-01"), now=at(2))
    assert sim["source"] == "SIMULATED"
    d = core.get_device("KH-S01")
    assert d["mac_address"] == "AA:BB:CC:DD:EE:FF" and d["status"] == "CONNECTED"


@pytest.mark.parametrize("bad", ["", "ab", "has space", "x" * 40, "bad/id", "-lead"])
def test_invalid_device_ids_rejected(bad):
    with pytest.raises(ValidationError):
        DeviceRegisterIn(device_id=bad)


def test_invalid_mac_rejected():
    with pytest.raises(ValidationError):
        DeviceRegisterIn(device_id="KH-S01", mac_address="not-a-mac")


def test_heartbeat_reports_class_state(core):
    assert hb(core, "KH-S01", 0)["class_active"] is False
    core.start_class(ClassStartIn(name="Maths"), now=at(1))
    r = hb(core, "KH-S01", 2)
    assert r["class_active"] and r["class_name"] == "Maths"


def test_connection_timeout_and_reconnection(core):
    core.start_class(ClassStartIn(name="Maths"), now=at(0))
    hb(core, "KH-S01", 1)
    assert core.get_device("KH-S01")["status"] == "CONNECTED"

    core.check_timeouts(now=at(8))                       # 7 s since last heartbeat: still fine
    assert core.get_device("KH-S01")["status"] == "CONNECTED"
    core.check_timeouts(now=at(13))                      # 12 s > 2 x heartbeat interval -> late
    assert core.get_device("KH-S01")["status"] == "RECONNECTING"
    core.check_timeouts(now=at(20))                      # 19 s > DEVICE_TIMEOUT -> disconnected
    assert core.get_device("KH-S01")["status"] == "DISCONNECTED"

    hb(core, "KH-S01", 30)                               # comes back
    assert core.get_device("KH-S01")["status"] == "CONNECTED"

    cid = core.current_class()["id"]
    types = [e["event_type"] for e in core.connection_events(cid)]
    assert types == ["CONNECTED", "DISCONNECTED", "RECONNECTED"]
    kinds = [e["event_type"] for e in core.list_events(50, cid)]
    assert "DEVICE_DISCONNECTED" in kinds and "DEVICE_RECONNECTED" in kinds


def test_late_heartbeat_recovers_without_disconnect_event(core):
    core.start_class(ClassStartIn(name="Maths"), now=at(0))
    hb(core, "KH-S01", 1)
    core.check_timeouts(now=at(13))
    assert core.get_device("KH-S01")["status"] == "RECONNECTING"
    hb(core, "KH-S01", 14)
    assert core.get_device("KH-S01")["status"] == "CONNECTED"
    types = [e["event_type"] for e in core.connection_events(core.current_class()["id"])]
    assert types == ["CONNECTED"]


def test_telemetry_ignored_without_class(core):
    r = tel(core, "KH-S01", 0)
    assert r["ok"] and r["stored"] is False and r["reason"] == "NO_ACTIVE_CLASS"


def test_telemetry_stored_and_estimated(core):
    core.start_class(ClassStartIn(name="Maths"), now=at(0))
    hb(core, "KH-S01", 1)
    assert tel(core, "KH-S01", 2)["stored"] is True
    snap = core.snapshot(now=at(3))
    row = next(d for d in snap["devices"] if d["device_id"] == "KH-S01")
    assert row["attention_state"] == "ENGAGED" and snap["metrics"]["estimated_engaged"] == 1
    for i, t in enumerate(range(4, 20, 2)):
        tel(core, "KH-S01", t, state="POSSIBLE_ATTENTION_DRIFT", score=0.8)
    snap = core.snapshot(now=at(20))
    assert snap["metrics"]["possible_drift"] == 1


@pytest.mark.parametrize("kwargs", [
    dict(motion_score=1.5, motion_state="NORMAL"),
    dict(motion_score=-0.1, motion_state="NORMAL"),
    dict(motion_score=0.2, motion_state="DANCING"),
])
def test_telemetry_validation(kwargs):
    with pytest.raises(ValidationError):
        TelemetryIn(device_id="KH-S01", acceleration_magnitude=1, angular_velocity=0, orientation_change=0, **kwargs)


def test_feedback_trigger_and_acknowledge(core):
    core.start_class(ClassStartIn(name="Maths"), now=at(0))
    hb(core, "KH-S01", 1)
    core.feedback(FeedbackIn(device_id="KH-S01", event="FEEDBACK_TRIGGERED"), now=at(5))
    core.feedback(FeedbackIn(device_id="KH-S01", event="FEEDBACK_ACKNOWLEDGED"), now=at(9))
    s = core.class_analytics(core.current_class()["id"], now=at(10))["summary"]
    assert s["feedback_events"] == 1 and s["feedback_acknowledged"] == 1


def test_disconnect_marks_state_unknown_in_snapshot(core):
    core.start_class(ClassStartIn(name="Maths"), now=at(0))
    hb(core, "KH-S01", 1)
    tel(core, "KH-S01", 2)
    core.check_timeouts(now=at(30))
    snap = core.snapshot(now=at(30))
    assert snap["metrics"]["connected"] == 0
    assert snap["metrics"]["disconnected_at_least_once"] == 1
