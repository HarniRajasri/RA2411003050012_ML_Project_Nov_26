"""DEMO / SIMULATED sample data generator.

Creates ONE finished class flagged is_demo=True, filled with synthetic SIM-Dxx devices. It exists so the
History and Analytics pages have something to show before a real class has been run. It is always labelled
DEMO / SIMULATED in the UI and must never be mixed up with real hardware data.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from sqlalchemy import insert

from ..analytics import windows as wnd
from ..models import (AttentionEvent, ClassDevice, ClassSession, ConnectionEvent, EventLog, FeedbackEvent, Telemetry)
from ..utils import utcnow

BASE_ENGAGEMENT = [0.80, 0.86, 0.74, 0.90, 0.68, 0.62, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7]


def seed_demo_class(core, devices: int = 30, minutes: int = 60, window_seconds: int = 600,
                    seed: int | None = None, now: datetime | None = None) -> dict:
    rng = random.Random(seed)
    now = now or utcnow()
    start = (now - timedelta(hours=2)).replace(microsecond=0)
    end = start + timedelta(minutes=minutes)
    ids = [f"SIM-D{i:02d}" for i in range(1, devices + 1)]

    with core.db.session() as db:
        cls = ClassSession(name="DEMO / SIMULATED - Physics (sample data)", start_time=start, scheduled_end=end,
                           end_time=end, status="ENDED", window_seconds=window_seconds, is_demo=True)
        db.add(cls)
        db.flush()
        for did in ids:
            core._get_or_create_device(db, did, start)

        conn_rows, att_rows, tel_rows, fb_rows, log_rows, cd_rows = [], [], [], [], [], []
        intervals: dict[str, list] = {}
        log_rows.append(dict(class_id=cls.id, device_id=None, event_type="CLASS_STARTED", source="SIMULATED",
                             message="Class started: DEMO / SIMULATED sample", timestamp=start))
        for k, did in enumerate(ids):
            late = rng.random() < 0.10
            join = start + timedelta(seconds=rng.uniform(300, 600) if late else rng.uniform(2, 45))
            segs = [[join, end]]
            dc = 0
            if rng.random() < 0.15:                       # one disconnection
                drop = join + timedelta(minutes=rng.uniform(10, minutes - 12))
                back = drop + timedelta(minutes=rng.uniform(1.5, 5))
                segs = [[join, drop], [back, end]] if rng.random() < 0.8 else [[join, drop]]
                dc = 1
            intervals[did] = segs
            conn_rows.append(dict(class_id=cls.id, device_id=did, event_type="CONNECTED", timestamp=segs[0][0]))
            log_rows.append(dict(class_id=cls.id, device_id=did, event_type="DEVICE_CONNECTED", source="SIMULATED",
                                 message=f"{did} connected" + (" (joined after class start)" if late else ""),
                                 timestamp=segs[0][0]))
            if dc:
                conn_rows.append(dict(class_id=cls.id, device_id=did, event_type="DISCONNECTED", timestamp=segs[0][1]))
                log_rows.append(dict(class_id=cls.id, device_id=did, event_type="DEVICE_DISCONNECTED", source="SIMULATED",
                                     message=f"{did} disconnected", timestamp=segs[0][1]))
                if len(segs) > 1:
                    conn_rows.append(dict(class_id=cls.id, device_id=did, event_type="RECONNECTED", timestamp=segs[1][0]))
                    log_rows.append(dict(class_id=cls.id, device_id=did, event_type="DEVICE_RECONNECTED", source="SIMULATED",
                                         message=f"{did} reconnected", timestamp=segs[1][0]))

            offset = rng.uniform(-0.10, 0.10)
            drift_events, prev_drift = 0, False
            in_drift = False                              # two-state chain: drift episodes last ~2 minutes on average
            for a, b in segs:
                t = a
                while t < b:
                    w = int((t - start).total_seconds() // window_seconds)
                    p_eng = min(0.97, max(0.05, BASE_ENGAGEMENT[min(w, len(BASE_ENGAGEMENT) - 1)] + offset))
                    leave = 1.0 / 12.0                           # per 10 s sample
                    enter = min(0.5, leave * (1.0 - p_eng) / p_eng)   # keeps the long-run engaged share at p_eng
                    in_drift = (rng.random() >= leave) if in_drift else (rng.random() < enter)
                    engaged = not in_drift
                    if engaged:
                        mstate = "NORMAL" if rng.random() < 0.85 else "MOVING"
                        score = rng.uniform(0.02, 0.15) if mstate == "NORMAL" else rng.uniform(0.35, 0.5)
                    else:
                        mstate = rng.choice(["POSSIBLE_ATTENTION_DRIFT", "FEEDBACK", "MOVING"])
                        score = rng.uniform(0.5, 0.9)
                    att_score = rng.uniform(0.55, 0.92) if engaged else rng.uniform(0.1, 0.42)
                    att_rows.append(dict(class_id=cls.id, device_id=did, timestamp=t,
                                         state="ENGAGED" if engaged else "POSSIBLE_ATTENTION_DRIFT", score=round(att_score, 3),
                                         confidence=round(rng.uniform(0.45, 0.8), 3), source="SIMULATED",
                                         fusion_mode="MOTION_ONLY", eeg_source=None))
                    tel_rows.append(dict(class_id=cls.id, device_id=did, timestamp=t, motion_score=round(score, 3),
                                         motion_state=mstate, orientation_change=round(rng.uniform(2, 40), 1),
                                         angular_velocity=round(rng.uniform(0.1, 1.6), 2),
                                         acceleration_magnitude=round(rng.gauss(1.0, 0.05), 3), source="SIMULATED"))
                    if not engaged and not prev_drift:
                        drift_events += 1
                        acked = rng.random() < 0.7
                        fb_rows.append(dict(class_id=cls.id, device_id=did, timestamp=t, feedback_type="LED_VIBRATION",
                                            acknowledged=acked, acknowledged_at=t + timedelta(seconds=rng.uniform(3, 12)) if acked else None))
                    prev_drift = not engaged
                    t += timedelta(seconds=10)
            cd_rows.append(dict(class_id=cls.id, device_id=did, first_connected_at=segs[0][0], last_connected_at=segs[-1][0],
                                joined_late=late, disconnect_count=dc, reconnect_count=1 if len(segs) > 1 else 0,
                                drift_events=drift_events))

        # peak simultaneous connections by sweep line
        points = []
        for segs in intervals.values():
            for a, b in segs:
                points += [(a, 1), (b, -1)]
        cur = peak = 0
        for _, d in sorted(points):
            cur += d
            peak = max(peak, cur)
        cls.peak_connections = peak
        log_rows.append(dict(class_id=cls.id, device_id=None, event_type="CLASS_ENDED", source="SIMULATED",
                             message="Class ended: DEMO / SIMULATED sample", timestamp=end))
        for model, rows in ((ConnectionEvent, conn_rows), (ClassDevice, cd_rows), (AttentionEvent, att_rows),
                            (Telemetry, tel_rows), (FeedbackEvent, fb_rows), (EventLog, log_rows)):
            if rows:
                db.execute(insert(model), rows)
        db.flush()
        windows, _, _ = wnd.compute_windows(db, cls, end, "ALL", core.s.min_obs_per_window)
        core._persist_windows(db, cls, windows, end)
        core._cache.clear()
        core.dirty = True
        return {"class_id": cls.id, "devices": devices, "label": "DEMO / SIMULATED data", "windows": len(windows)}
