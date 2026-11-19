"""10-minute window aggregation, continuous-connection counts, peak engagement, fusion."""
from datetime import timedelta

from app.analytics.fusion import FusionConfig, FusionEngine
from app.analytics.windows import aggregate_windows, build_intervals, peak_window
from app.schemas import ClassStartIn, HeartbeatIn, TelemetryIn

from conftest import T0, at

W = 600


def test_build_intervals_reconstructs_segments():
    ev = [("A", "CONNECTED", at(0)), ("A", "DISCONNECTED", at(100)), ("A", "RECONNECTED", at(160)),
          ("B", "CONNECTED", at(30))]
    iv, still_open = build_intervals(ev, at(300))
    assert iv["A"] == [(at(0), at(100)), (at(160), at(300))]
    assert iv["B"] == [(at(30), at(300))]
    assert still_open == {"A", "B"}


def test_aggregation_of_ten_minute_windows():
    # 2 devices, 30-minute class -> 3 windows.
    # window 0: A 8/10 engaged, B 4/10  -> mean 60 %
    # window 1: A 10/10, B 10/10        -> 100 %
    # window 2: A 2/10, B has only 2 observations (< min_obs) -> only A counts -> 20 %
    obs = [("A", 0, 10, 8), ("B", 0, 10, 4), ("A", 1, 10, 10), ("B", 1, 10, 10), ("A", 2, 10, 2), ("B", 2, 2, 2)]
    intervals = {"A": [(at(0), at(1800))], "B": [(at(0), at(1800))]}
    w = aggregate_windows(obs, intervals, at(0), at(1800), W, ended=True)
    assert [x["engagement_percentage"] for x in w] == [60.0, 100.0, 20.0]
    assert [x["connected_students"] for x in w] == [2, 2, 2]
    assert w[0]["estimated_engaged_students"] == 1 and w[0]["possible_drift_students"] == 1
    assert all(x["status"] == "complete" for x in w)
    assert w[2]["contributing_students"] == 1


def test_connected_students_is_time_weighted_not_end_of_window_snapshot():
    # B is connected for only the last 100 s of a 600 s window -> time-weighted connected count is 1.17 -> 1
    intervals = {"A": [(at(0), at(600))], "B": [(at(500), at(600))]}
    w = aggregate_windows([], intervals, at(0), at(600), W, ended=True)
    assert w[0]["connected_students"] == 1


def test_partial_and_in_progress_windows():
    w = aggregate_windows([], {}, at(0), at(900), W, scheduled_end=at(1800), ended=False)
    assert [x["status"] for x in w] == ["complete", "in_progress", "upcoming"]
    ended = aggregate_windows([], {}, at(0), at(900), W, ended=True)
    assert [x["status"] for x in ended] == ["complete", "partial"]
    assert ended[1]["covered_seconds"] == 300


def test_peak_window_highest_and_ties_resolve_to_earliest():
    obs = [("A", 0, 10, 5), ("A", 1, 10, 9), ("A", 2, 10, 9), ("A", 3, 10, 3)]
    w = aggregate_windows(obs, {"A": [(at(0), at(2400))]}, at(0), at(2400), W, ended=True)
    p = peak_window(w, W)
    assert p["index"] == 1 and p["engagement_percentage"] == 90.0


def test_peak_window_none_when_no_data():
    assert peak_window(aggregate_windows([], {}, at(0), at(600), W, ended=True), W) is None


def test_continuous_connection_metrics(core):
    """A: connected the whole class. B: joins late. C: disconnects once. D: joins at start, never sends telemetry."""
    core.start_class(ClassStartIn(name="Physics"), now=at(0))
    for d in ("SIM-01", "SIM-02", "SIM-03", "SIM-04"):
        pass
    core.heartbeat(HeartbeatIn(device_id="SIM-01"), now=at(2))
    core.heartbeat(HeartbeatIn(device_id="SIM-03"), now=at(3))
    core.heartbeat(HeartbeatIn(device_id="SIM-04"), now=at(4))
    for t in range(5, 400, 5):                       # keep 01, 03, 04 alive; 03 will drop out at 100
        core.heartbeat(HeartbeatIn(device_id="SIM-01"), now=at(t))
        core.heartbeat(HeartbeatIn(device_id="SIM-04"), now=at(t))
        if t < 100:
            core.heartbeat(HeartbeatIn(device_id="SIM-03"), now=at(t))
        core.check_timeouts(now=at(t))
        if t == 200:
            core.heartbeat(HeartbeatIn(device_id="SIM-02"), now=at(t))       # late joiner (> 60 s grace)
        if t >= 200:
            core.heartbeat(HeartbeatIn(device_id="SIM-02"), now=at(t))
    core.heartbeat(HeartbeatIn(device_id="SIM-03"), now=at(390))            # 03 returns
    cid = core.current_class()["id"]
    s = core.class_analytics(cid, now=at(400))["summary"]
    assert s["total_registered"] == 4
    assert s["joined_after_start"] == 1
    assert s["disconnected_at_least_once"] == 1
    assert s["continuous_from_start"] == 2           # SIM-01 and SIM-04
    assert s["peak_connections"] == 4


def test_join_grace_period(core):
    core.start_class(ClassStartIn(name="Physics"), now=at(0))
    core.heartbeat(HeartbeatIn(device_id="SIM-01"), now=at(30))              # inside 60 s grace: not late
    core.heartbeat(HeartbeatIn(device_id="SIM-02"), now=at(90))              # outside: late
    s = core.class_analytics(core.current_class()["id"], now=at(100))["summary"]
    assert s["joined_after_start"] == 1 and s["continuous_from_start"] == 1


def test_end_to_end_window_analytics_with_real_pipeline(core):
    core.start_class(ClassStartIn(name="Physics", window_seconds=60), now=at(0))
    # two devices, 3 minutes: SIM-01 always engaged, SIM-02 drifts in the middle minute
    for t in range(1, 181, 2):
        for dev in ("SIM-01", "SIM-02"):
            core.heartbeat(HeartbeatIn(device_id=dev), now=at(t))
            drifting = dev == "SIM-02" and 60 <= t < 120
            core.telemetry(TelemetryIn(device_id=dev, motion_score=0.9 if drifting else 0.05,
                                       motion_state="POSSIBLE_ATTENTION_DRIFT" if drifting else "NORMAL",
                                       acceleration_magnitude=1, angular_velocity=0.1, orientation_change=1), now=at(t))
    core.end_class(now=at(180))
    cid = core.list_classes()[0]["id"]
    a = core.class_analytics(cid, now=at(200))
    pct = [w["engagement_percentage"] for w in a["windows"]]
    assert len(pct) == 3
    assert pct[0] > pct[1] and pct[2] > pct[1]        # the middle minute is the low-engagement window
    assert a["peak"]["index"] in (0, 2)
    assert a["summary"]["possible_drift_events"] >= 1
    assert "not" in a["methodology"].lower()
    # source filter
    only_sim = core.class_analytics(cid, "REAL", now=at(200))
    assert only_sim["summary"]["total_registered"] == 0


def test_fusion_motion_only_and_recovery():
    eng = FusionEngine(FusionConfig())
    calm = eng.evaluate("d", 0.05, "NORMAL")
    assert calm.attention_state == "ENGAGED" and calm.fusion_mode == "MOTION_ONLY"
    for _ in range(6):
        res = eng.evaluate("d", 0.9, "POSSIBLE_ATTENTION_DRIFT")
    assert res.attention_state == "POSSIBLE_ATTENTION_DRIFT"
    for _ in range(6):
        back = eng.evaluate("d", 0.05, "NORMAL")
    assert back.attention_state == "ENGAGED"
    assert 0.0 <= back.confidence <= 1.0


def test_fusion_hysteresis_prevents_chatter_near_the_threshold():
    """A borderline signal (raw score ~0.48, between drift threshold 0.45 and exit level 0.50) keeps whichever state
    the student was already in."""
    steady, drifting = FusionEngine(FusionConfig()), FusionEngine(FusionConfig())
    for _ in range(4):
        steady.evaluate("s", 0.05, "NORMAL")
        drifting.evaluate("d", 0.9, "POSSIBLE_ATTENTION_DRIFT")
    for _ in range(8):
        a = steady.evaluate("s", 0.57, "MOVING")
        b = drifting.evaluate("d", 0.57, "MOVING")
    assert a.attention_state == "ENGAGED"
    assert b.attention_state == "POSSIBLE_ATTENTION_DRIFT"


def test_fusion_weights_shift_with_movement():
    eng = FusionEngine(FusionConfig())
    still = eng.evaluate("a", 0.05, "NORMAL", eeg_evidence=0.1)
    moving = eng.evaluate("b", 0.6, "MOVING", eeg_evidence=0.1)
    assert still.fusion_mode == moving.fusion_mode == "MOTION_EEG"
    assert still.weights[1] > moving.weights[1]             # EEG weighs more when the head is stable
