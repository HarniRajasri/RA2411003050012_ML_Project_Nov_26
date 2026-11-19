"""Fixed-length analytics windows (default 10 minutes).

Aggregation method (documented in README):
  For every window and every device with >= MIN_OBS valid observations in that window:
      p = (observations classified ENGAGED) / (all observations)
  engagement_percentage       = 100 * mean(p over those devices)
  estimated_engaged_students  = number of devices with p >= 0.5
  possible_drift_students     = number of devices with p <  0.5
  connected_students          = time-weighted average number of connected devices during the window
                                (reconstructed from stored connection events - not an end-of-window snapshot)
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from math import ceil

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models import ClassSession
from ..utils import epoch


def build_intervals(events, end: datetime):
    """events: iterable of (device_id, event_type, timestamp) ordered by time.
    Returns ({device_id: [(start, end), ...]}, set_of_devices_connected_at_end)."""
    open_at: dict[str, datetime] = {}
    out: dict[str, list] = defaultdict(list)
    for dev, etype, ts in events:
        if etype in ("CONNECTED", "RECONNECTED"):
            open_at.setdefault(dev, ts)
        elif etype == "DISCONNECTED":
            st = open_at.pop(dev, None)
            if st is not None:
                out[dev].append((st, ts))
    still_open = set(open_at)
    for dev, st in open_at.items():
        out[dev].append((st, end))
    return dict(out), still_open


def _overlap(a0: datetime, a1: datetime, b0: datetime, b1: datetime) -> float:
    return max(0.0, (min(a1, b1) - max(a0, b0)).total_seconds())


def aggregate_windows(obs, intervals, start: datetime, until: datetime, window_seconds: int,
                      scheduled_end: datetime | None = None, ended: bool = False, min_obs: int = 3):
    """Pure function (unit-tested). obs: iterable of (device_id, bucket_index, n_obs, n_engaged)."""
    W = window_seconds
    last = until if ended else (max(until, scheduled_end) if scheduled_end else until)
    total = max((last - start).total_seconds(), 0.0)
    n = max(1, ceil(total / W))
    per_bucket: dict[int, list] = defaultdict(list)
    for dev, b, cnt, eng in obs:
        if 0 <= b < n:
            per_bucket[b].append((dev, cnt, eng))

    windows = []
    for i in range(n):
        ws = start + timedelta(seconds=i * W)
        we_full = ws + timedelta(seconds=W)
        cov_end = min(until, we_full)
        covered = max(0.0, (cov_end - ws).total_seconds())
        if ended:
            status = "complete" if covered >= W - 1e-6 else "partial"
        elif until >= we_full:
            status = "complete"
        elif until > ws:
            status = "in_progress"
        else:
            status = "upcoming"

        fractions = [eng / cnt for _, cnt, eng in per_bucket.get(i, []) if cnt >= min_obs]
        n_obs = sum(cnt for _, cnt, _ in per_bucket.get(i, []))
        pct = round(100.0 * sum(fractions) / len(fractions), 1) if fractions else None
        engaged = sum(1 for f in fractions if f >= 0.5)

        connected = None
        if covered > 0:
            tot = sum(_overlap(s, e, ws, cov_end) for ivs in intervals.values() for s, e in ivs)
            connected = int(round(tot / covered))
        windows.append({
            "index": i,
            "window_start": ws,
            "window_end": min(we_full, last),
            "status": status,
            "covered_seconds": round(covered, 1),
            "connected_students": connected,
            "contributing_students": len(fractions),
            "estimated_engaged_students": engaged if fractions else None,
            "possible_drift_students": (len(fractions) - engaged) if fractions else None,
            "engagement_percentage": pct,
            "observations": n_obs,
        })
    return windows


def peak_window(windows, window_seconds: int):
    """Highest estimated engagement interval. Windows covering < 50% of the window length are ignored
    unless nothing else is available. Ties resolve to the earliest window."""
    cands = [w for w in windows if w["engagement_percentage"] is not None and w["status"] != "upcoming"]
    pool = [w for w in cands if w["covered_seconds"] >= 0.5 * window_seconds] or cands
    if not pool:
        return None
    return max(pool, key=lambda w: (w["engagement_percentage"], -w["index"]))


def compute_windows(db: Session, cls: ClassSession, until: datetime, source: str = "ALL", min_obs: int = 3):
    """Fetch observations + connection events from the database and aggregate them."""
    ended = cls.status == "ENDED" and cls.end_time is not None
    horizon = cls.end_time if ended else until
    params = {"cid": cls.id, "start": epoch(cls.start_time), "w": int(cls.window_seconds)}
    src_sql = ""
    if source in ("REAL", "SIMULATED"):
        src_sql = " AND source = :src"
        params["src"] = source
    rows = db.execute(text(
        "SELECT device_id, "
        "CAST((CAST(strftime('%s', timestamp) AS INTEGER) - :start) / :w AS INTEGER) AS bucket, "
        "COUNT(*) AS n, "
        "SUM(CASE WHEN state = 'ENGAGED' THEN 1 ELSE 0 END) AS engaged "
        "FROM attention_events WHERE class_id = :cid" + src_sql + " GROUP BY device_id, bucket"), params).all()
    obs = [(r[0], int(r[1]), int(r[2]), int(r[3] or 0)) for r in rows]

    ev_params = {"cid": cls.id}
    ev_sql = ("SELECT ce.device_id, ce.event_type, ce.timestamp FROM connection_events ce "
              "JOIN devices d ON d.device_id = ce.device_id WHERE ce.class_id = :cid")
    if source in ("REAL", "SIMULATED"):
        ev_sql += " AND d.source = :src"
        ev_params["src"] = source
    ev_sql += " ORDER BY ce.timestamp, ce.id"
    raw = db.execute(text(ev_sql), ev_params).all()
    events = [(r[0], r[1], r[2] if isinstance(r[2], datetime) else datetime.fromisoformat(str(r[2]))) for r in raw]
    intervals, still_open = build_intervals(events, horizon)

    windows = aggregate_windows(obs, intervals, cls.start_time, horizon, cls.window_seconds,
                                cls.scheduled_end, ended, min_obs)
    return windows, intervals, still_open
