"""Class-level summary: continuity, feedback counts, distributions, averages."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import case, func, select, text
from sqlalchemy.orm import Session

from ..constants import DEV_CONNECTED
from ..models import ClassDevice, ClassSession, Device, FeedbackEvent


def class_summary(db: Session, cls: ClassSession, until: datetime, source: str,
                  windows: list, still_open: set) -> dict:
    ended = cls.status == "ENDED" and cls.end_time is not None
    end = cls.end_time if ended else until
    duration = max(0.0, (end - cls.start_time).total_seconds())

    q = select(ClassDevice, Device).join(Device, Device.device_id == ClassDevice.device_id).where(
        ClassDevice.class_id == cls.id)
    if source in ("REAL", "SIMULATED"):
        q = q.where(Device.source == source)
    pairs = db.execute(q).all()
    total = len(pairs)
    if ended:
        connected_now = sum(1 for cd, _ in pairs if cd.device_id in still_open)
    else:
        connected_now = sum(1 for _, d in pairs if d.status == DEV_CONNECTED)
    continuous = sum(1 for cd, _ in pairs if not cd.joined_late and cd.disconnect_count == 0)
    disconnected_once = sum(1 for cd, _ in pairs if cd.disconnect_count > 0)
    joined_late = sum(1 for cd, _ in pairs if cd.joined_late)
    drift_events = sum(cd.drift_events for cd, _ in pairs)
    real = sum(1 for _, d in pairs if d.source == "REAL")

    fq = select(func.count(FeedbackEvent.id), func.coalesce(func.sum(case((FeedbackEvent.acknowledged, 1), else_=0)), 0)) \
        .select_from(FeedbackEvent).join(Device, Device.device_id == FeedbackEvent.device_id) \
        .where(FeedbackEvent.class_id == cls.id)
    if source in ("REAL", "SIMULATED"):
        fq = fq.where(Device.source == source)
    fb_total, fb_ack = db.execute(fq).one()

    params = {"cid": cls.id}
    src_sql = ""
    if source in ("REAL", "SIMULATED"):
        src_sql, params["src"] = " AND source = :src", source
    attn = {r[0]: int(r[1]) for r in db.execute(text(
        "SELECT state, COUNT(*) FROM attention_events WHERE class_id = :cid" + src_sql + " GROUP BY state"), params)}
    motion = {r[0]: int(r[1]) for r in db.execute(text(
        "SELECT motion_state, COUNT(*) FROM telemetry WHERE class_id = :cid" + src_sql + " GROUP BY motion_state"), params)}

    weighted = [(w["engagement_percentage"], w["covered_seconds"]) for w in windows
                if w["engagement_percentage"] is not None and w["covered_seconds"] > 0]
    wsum = sum(c for _, c in weighted)
    avg = round(sum(p * c for p, c in weighted) / wsum, 1) if wsum else None

    return {
        "duration_seconds": round(duration),
        "total_registered": total,
        "real_devices": real,
        "simulated_devices": total - real,
        "peak_connections": cls.peak_connections,
        "connected_now": connected_now,
        "continuous_from_start": continuous,
        "disconnected_at_least_once": disconnected_once,
        "joined_after_start": joined_late,
        "average_engagement_percentage": avg,
        "possible_drift_events": drift_events,
        "feedback_events": int(fb_total or 0),
        "feedback_acknowledged": int(fb_ack or 0),
        "attention_distribution": attn,
        "motion_distribution": motion,
    }
