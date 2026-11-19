"""Domain logic for classes, devices, connectivity, telemetry, feedback and live state.

All methods are synchronous (SQLite is fast and local) and accept an optional `now` so time-dependent behaviour
(timeouts, windows) is deterministic in tests. UI updates are queued in `outbox`; the async publisher loop in
main.py drains the outbox and broadcasts over WebSocket.
"""
from __future__ import annotations

import logging
from collections import deque
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..analytics import windows as wnd
from ..analytics.fusion import FusionEngine
from ..analytics.summary import class_summary
from ..config import Settings
from ..constants import *  # noqa: F401,F403
from ..database import Database
from ..errors import ClassNotActiveError, ConflictError, NotFoundError
from ..models import (AttentionEvent, ClassDevice, ClassSession, ConnectionEvent, Device, EngagementWindow,
                      EventLog, FeedbackEvent, Telemetry)
from ..schemas import ClassStartIn, DeviceRegisterIn, FeedbackIn, HeartbeatIn, TelemetryIn
from ..utils import iso, utcnow

log = logging.getLogger("khorizon.core")

METHODOLOGY = (
    "Estimated engagement per window = mean, over devices with enough observations in that window, of the share of "
    "that device's observations classified 'estimated engaged' (motion-based, optionally fused with EEG-derived "
    "features for the device that has them). Connected students is the time-weighted average connected count in the "
    "window. These are probabilistic estimates of class-level trends, not measurements of individual attention, "
    "listening or comprehension, and must not be used for punitive decisions."
)


class KHorizonCore:
    def __init__(self, settings: Settings, database: Database, fusion: FusionEngine, eeg=None):
        self.s = settings
        self.db = database
        self.fusion = fusion
        self.eeg = eeg
        self.outbox: list[dict] = []
        self.dirty = True
        self.live_history: deque = deque(maxlen=900)
        self._last_hist: datetime | None = None
        self._enrolled: set[tuple[int, str]] = set()
        self._cache: dict[tuple, tuple[float, dict]] = {}

    # ------------------------------------------------------------------ helpers
    def drain(self) -> list[dict]:
        out, self.outbox = self.outbox, []
        return out

    def active_class(self, db: Session) -> ClassSession | None:
        return db.scalar(select(ClassSession).where(ClassSession.status == CLASS_ACTIVE).order_by(ClassSession.id.desc()))

    def _emit(self, db: Session, event_type: str, message: str, *, cls: ClassSession | None = None,
              device_id: str | None = None, source: str = "SYSTEM", ts: datetime | None = None) -> None:
        row = EventLog(class_id=cls.id if cls else None, device_id=device_id, event_type=event_type,
                       message=message, source=source, timestamp=ts or utcnow())
        db.add(row)
        db.flush()
        self.outbox.append({"type": "event", "event": self.event_dict(row)})
        self.dirty = True

    @staticmethod
    def event_dict(e: EventLog) -> dict:
        return {"id": e.id, "class_id": e.class_id, "device_id": e.device_id, "event_type": e.event_type,
                "message": e.message, "source": e.source, "timestamp": iso(e.timestamp)}

    def class_dict(self, c: ClassSession, now: datetime | None = None) -> dict:
        now = now or utcnow()
        end = c.end_time or now
        return {"id": c.id, "name": c.name, "status": c.status, "start_time": iso(c.start_time),
                "end_time": iso(c.end_time), "scheduled_end": iso(c.scheduled_end),
                "window_seconds": c.window_seconds, "peak_connections": c.peak_connections, "is_demo": c.is_demo,
                "elapsed_seconds": max(0, int((end - c.start_time).total_seconds()))}

    def session_state(self, cls: ClassSession | None) -> dict:
        """Returned to devices on every call so the headband knows whether a class is running."""
        return {"class_active": cls is not None, "class_id": cls.id if cls else None,
                "class_name": cls.name if cls else None, "server_time": iso(utcnow()),
                "heartbeat_interval": self.s.heartbeat_interval}

    # ------------------------------------------------------------------ class control
    def start_class(self, p: ClassStartIn, now: datetime | None = None) -> dict:
        now = now or utcnow()
        with self.db.session() as db:
            active = self.active_class(db)
            if active:
                raise ConflictError(f"Class '{active.name}' is already active. End it before starting a new one.")
            sched = p.scheduled_end
            if sched is None and p.duration_minutes:
                sched = now + timedelta(minutes=p.duration_minutes)
            if sched is not None and sched.tzinfo is not None:
                sched = sched.astimezone(timezone.utc).replace(tzinfo=None)
            if sched is not None and sched <= now:
                raise ConflictError("Scheduled end must be after the start time.")
            cls = ClassSession(name=p.name, start_time=now, scheduled_end=sched, status=CLASS_ACTIVE,
                               window_seconds=p.window_seconds or self.s.engagement_window_seconds,
                               is_demo=p.is_demo)
            db.add(cls)
            db.flush()
            self._enrolled = set()
            self._emit(db, "CLASS_STARTED", f"Class started: {cls.name}", cls=cls, ts=now)
            # devices already online (heartbeats before START CLASS) become participants at the start time
            online = db.scalars(select(Device).where(Device.status == DEV_CONNECTED).order_by(Device.device_id)).all()
            for d in online:
                db.add(ClassDevice(class_id=cls.id, device_id=d.device_id, first_connected_at=now,
                                   last_connected_at=now, joined_late=False))
                db.add(ConnectionEvent(class_id=cls.id, device_id=d.device_id, event_type=EV_CONNECTED, timestamp=now))
                self._enrolled.add((cls.id, d.device_id))
                self._emit(db, "DEVICE_CONNECTED", f"{d.device_id} connected", cls=cls, device_id=d.device_id,
                           source=d.source, ts=now)
            cls.peak_connections = len(online)
            self.live_history.clear()
            self._last_hist = None
            self._cache.clear()
            log.info("class_started id=%s name=%r devices=%d", cls.id, cls.name, len(online))
            return self.class_dict(cls, now)

    def end_class(self, now: datetime | None = None) -> dict:
        now = now or utcnow()
        with self.db.session() as db:
            cls = self.active_class(db)
            if not cls:
                raise ClassNotActiveError("There is no active class to end.")
            cls.end_time = now
            cls.status = CLASS_ENDED
            db.flush()
            windows, _, _ = wnd.compute_windows(db, cls, now, "ALL", self.s.min_obs_per_window)
            self._persist_windows(db, cls, windows, now)
            self._emit(db, "CLASS_ENDED", f"Class ended: {cls.name}", cls=cls, ts=now)
            self._cache.clear()
            log.info("class_ended id=%s name=%r", cls.id, cls.name)
            return self.class_dict(cls, now)

    def _persist_windows(self, db: Session, cls: ClassSession, windows: list[dict], now: datetime) -> None:
        existing = {w.window_index: w for w in db.scalars(select(EngagementWindow).where(EngagementWindow.class_id == cls.id))}
        for w in windows:
            if w["status"] == "upcoming":
                continue
            row = existing.get(w["index"])
            if row is None:
                row = EngagementWindow(class_id=cls.id, window_index=w["index"], window_start=w["window_start"],
                                       window_end=w["window_end"])
                db.add(row)
            row.window_end = w["window_end"]
            row.connected_students = w["connected_students"] or 0
            row.estimated_engaged_students = w["estimated_engaged_students"] or 0
            row.possible_drift_students = w["possible_drift_students"] or 0
            row.engagement_percentage = w["engagement_percentage"]
            row.observations = w["observations"]
            row.covered_seconds = w["covered_seconds"]
            row.updated_at = now

    def persist_active_windows(self, now: datetime | None = None) -> None:
        now = now or utcnow()
        with self.db.session() as db:
            cls = self.active_class(db)
            if cls:
                windows, _, _ = wnd.compute_windows(db, cls, now, "ALL", self.s.min_obs_per_window)
                self._persist_windows(db, cls, windows, now)

    # ------------------------------------------------------------------ devices
    def _get_or_create_device(self, db: Session, device_id: str, now: datetime, mac: str | None = None,
                              fw: str | None = None, label: str | None = None) -> tuple[Device, bool]:
        dev = db.scalar(select(Device).where(Device.device_id == device_id))
        created = dev is None
        if created:
            src = SRC_SIM if device_id.upper().startswith(SIM_PREFIX) else SRC_REAL
            dev = Device(device_id=device_id, source=src, mac_address=mac, firmware_version=fw, student_label=label,
                         created_at=now, status=DEV_DISCONNECTED)
            db.add(dev)
            db.flush()
            log.info("device_registered device=%s source=%s", device_id, src)
        else:
            if mac:
                dev.mac_address = mac
            if fw:
                dev.firmware_version = fw
            if label is not None:
                dev.student_label = label
        return dev, created

    def _enrolled_cd(self, db: Session, cls: ClassSession, device_id: str) -> ClassDevice | None:
        return db.scalar(select(ClassDevice).where(ClassDevice.class_id == cls.id, ClassDevice.device_id == device_id))

    def _connected_in_class(self, db: Session, cls: ClassSession) -> int:
        return db.scalar(select(func.count()).select_from(ClassDevice)
                         .join(Device, Device.device_id == ClassDevice.device_id)
                         .where(ClassDevice.class_id == cls.id, Device.status == DEV_CONNECTED)) or 0

    def _touch(self, db: Session, dev: Device, now: datetime, cls: ClassSession | None) -> None:
        """Any message from a device proves it is alive: refresh last_seen and connection state."""
        prev = dev.status
        if dev.last_seen is None or now > dev.last_seen:
            dev.last_seen = now
        if prev != DEV_CONNECTED:
            dev.status = DEV_CONNECTED
            dev.connected_since = now
            self.dirty = True
        if cls is not None and (prev != DEV_CONNECTED or (cls.id, dev.device_id) not in self._enrolled):
            self._record_connection(db, cls, dev, now, prev)

    def _record_connection(self, db: Session, cls: ClassSession, dev: Device, now: datetime, prev: str) -> None:
        cd = self._enrolled_cd(db, cls, dev.device_id)
        if cd is None:
            late = (now - cls.start_time).total_seconds() > self.s.join_grace_seconds
            db.add(ClassDevice(class_id=cls.id, device_id=dev.device_id, first_connected_at=now,
                               last_connected_at=now, joined_late=late))
            etype, msg = EV_CONNECTED, f"{dev.device_id} connected" + (" (joined after class start)" if late else "")
        elif prev in (DEV_CONNECTED, DEV_RECONNECTING):
            self._enrolled.add((cls.id, dev.device_id))       # already counted as connected (e.g. server restart)
            cd.last_connected_at = now
            return
        else:
            cd.reconnect_count += 1
            cd.last_connected_at = now
            etype, msg = EV_RECONNECTED, f"{dev.device_id} reconnected"
        self._enrolled.add((cls.id, dev.device_id))
        db.add(ConnectionEvent(class_id=cls.id, device_id=dev.device_id, event_type=etype, timestamp=now))
        db.flush()
        connected = self._connected_in_class(db, cls)
        if connected > cls.peak_connections:
            cls.peak_connections = connected
        self._emit(db, "DEVICE_" + etype, msg, cls=cls, device_id=dev.device_id, source=dev.source, ts=now)
        log.info("device_%s device=%s class=%s", etype.lower(), dev.device_id, cls.id)

    def _mark_disconnected(self, db: Session, dev: Device, now: datetime, cls: ClassSession | None) -> None:
        dev.status = DEV_DISCONNECTED
        dev.last_disconnected_at = now
        dev.motion_state = None
        dev.attention_state = None
        dev.attention_score = None
        self.fusion.reset(dev.device_id)
        self.dirty = True
        if cls is not None:
            cd = self._enrolled_cd(db, cls, dev.device_id)
            if cd is not None:
                cd.disconnect_count += 1
                db.add(ConnectionEvent(class_id=cls.id, device_id=dev.device_id, event_type=EV_DISCONNECTED, timestamp=now))
                self._emit(db, "DEVICE_DISCONNECTED", f"{dev.device_id} disconnected", cls=cls,
                           device_id=dev.device_id, source=dev.source, ts=now)
        log.warning("device_disconnected device=%s", dev.device_id)

    def register_device(self, p: DeviceRegisterIn, now: datetime | None = None) -> dict:
        now = now or utcnow()
        with self.db.session() as db:
            dev, created = self._get_or_create_device(db, p.device_id, now, p.mac_address, p.firmware_version, p.student_label)
            cls = self.active_class(db)
            self._touch(db, dev, now, cls)
            return {"device_id": dev.device_id, "registered": True, "already_registered": not created,
                    "source": dev.source, **self.session_state(cls)}

    def heartbeat(self, p: HeartbeatIn, now: datetime | None = None) -> dict:
        now = now or utcnow()
        with self.db.session() as db:
            dev, _ = self._get_or_create_device(db, p.device_id, now)
            cls = self.active_class(db)
            self._touch(db, dev, now, cls)
            return {"ok": True, **self.session_state(cls)}

    def telemetry(self, p: TelemetryIn, now: datetime | None = None) -> dict:
        now = now or utcnow()
        with self.db.session() as db:
            dev, _ = self._get_or_create_device(db, p.device_id, now)
            cls = self.active_class(db)
            self._touch(db, dev, now, cls)
            dev.motion_state = p.motion_state
            if cls is None:
                # Visible for bench testing, but nothing is stored or counted outside an active class.
                dev.last_telemetry_at = now
                return {"ok": True, "stored": False, "reason": "NO_ACTIVE_CLASS", **self.session_state(None)}

            eeg = self.eeg.evidence_for(dev.device_id, dev.source) if self.eeg else None
            res = self.fusion.evaluate(dev.device_id, p.motion_score, p.motion_state, eeg[0] if eeg else None)
            eeg_label = eeg[1] if eeg else None
            db.add(Telemetry(class_id=cls.id, device_id=dev.device_id, timestamp=now, motion_score=p.motion_score,
                             motion_state=p.motion_state, orientation_change=p.orientation_change,
                             angular_velocity=p.angular_velocity, acceleration_magnitude=p.acceleration_magnitude,
                             source=dev.source))
            db.add(AttentionEvent(class_id=cls.id, device_id=dev.device_id, timestamp=now, state=res.attention_state,
                                  score=res.attention_score, confidence=res.confidence, source=dev.source,
                                  fusion_mode=res.fusion_mode, eeg_source=eeg_label))
            prev_state = dev.attention_state
            dev.attention_state = res.attention_state
            dev.attention_score = res.attention_score
            dev.fusion_mode = res.fusion_mode + (f"({eeg_label})" if eeg_label else "")
            dev.last_telemetry_at = now
            if res.attention_state == ATTN_DRIFT and prev_state != ATTN_DRIFT:
                cd = self._enrolled_cd(db, cls, dev.device_id)
                if cd is not None:
                    cd.drift_events += 1
                if dev.source == SRC_REAL:
                    self._emit(db, "DRIFT_ESTIMATED", f"{dev.device_id} possible attention drift (estimate)",
                               cls=cls, device_id=dev.device_id, source=dev.source, ts=now)
            self.dirty = True
            return {"ok": True, "stored": True, **self.session_state(cls)}

    def feedback(self, p: FeedbackIn, now: datetime | None = None) -> dict:
        now = now or utcnow()
        with self.db.session() as db:
            dev, _ = self._get_or_create_device(db, p.device_id, now)
            cls = self.active_class(db)
            self._touch(db, dev, now, cls)
            if cls is None:
                return {"ok": True, "stored": False, "reason": "NO_ACTIVE_CLASS", **self.session_state(None)}
            real = dev.source == SRC_REAL
            if p.event == FB_TRIGGERED:
                db.add(FeedbackEvent(class_id=cls.id, device_id=dev.device_id, timestamp=now,
                                     feedback_type=p.feedback_type or "LED_VIBRATION", acknowledged=False))
                if real:
                    self._emit(db, FB_TRIGGERED, f"{dev.device_id} feedback shown (red LED + vibration)",
                               cls=cls, device_id=dev.device_id, source=dev.source, ts=now)
            else:
                row = db.scalar(select(FeedbackEvent).where(
                    FeedbackEvent.class_id == cls.id, FeedbackEvent.device_id == dev.device_id,
                    FeedbackEvent.acknowledged.is_(False)).order_by(FeedbackEvent.id.desc()))
                if row is None:
                    row = FeedbackEvent(class_id=cls.id, device_id=dev.device_id, timestamp=now,
                                        feedback_type=p.feedback_type or "LED_VIBRATION")
                    db.add(row)
                row.acknowledged = True
                row.acknowledged_at = now
                if real:
                    self._emit(db, FB_ACKNOWLEDGED, f"{dev.device_id} feedback acknowledged (button)",
                               cls=cls, device_id=dev.device_id, source=dev.source, ts=now)
            self.dirty = True
            return {"ok": True, "stored": True, **self.session_state(cls)}

    def check_timeouts(self, now: datetime | None = None) -> int:
        """Heartbeat supervision. Late -> RECONNECTING, missing beyond DEVICE_TIMEOUT -> DISCONNECTED."""
        now = now or utcnow()
        changed = 0
        with self.db.session() as db:
            cls = self.active_class(db)
            devs = db.scalars(select(Device).where(Device.status.in_([DEV_CONNECTED, DEV_RECONNECTING]))).all()
            for d in devs:
                if d.last_seen is None:
                    continue
                age = (now - d.last_seen).total_seconds()
                if age > self.s.device_timeout:
                    self._mark_disconnected(db, d, now, cls)
                    changed += 1
                elif age > self.s.device_stale_after and d.status == DEV_CONNECTED:
                    d.status = DEV_RECONNECTING
                    self.dirty = True
                    changed += 1
        return changed

    def list_devices(self) -> list[dict]:
        with self.db.session() as db:
            return [self.device_dict(d) for d in db.scalars(select(Device).order_by(Device.source, Device.device_id))]

    def device_dict(self, d: Device, detail: bool = True) -> dict:
        out = {"device_id": d.device_id, "student_label": d.student_label, "source": d.source, "status": d.status,
               "last_seen": iso(d.last_seen), "connected_since": iso(d.connected_since),
               "last_disconnected_at": iso(d.last_disconnected_at), "motion_state": d.motion_state,
               "attention_state": d.attention_state, "fusion_mode": d.fusion_mode}
        if detail:
            out.update({"mac_address": d.mac_address, "firmware_version": d.firmware_version,
                        "created_at": iso(d.created_at), "attention_score": d.attention_score})
        return out

    def get_device(self, device_id: str) -> dict:
        with self.db.session() as db:
            d = db.scalar(select(Device).where(Device.device_id == device_id))
            if d is None:
                raise NotFoundError(f"Device '{device_id}' is not registered.")
            return self.device_dict(d)

    def set_label(self, device_id: str, label: str | None) -> dict:
        with self.db.session() as db:
            d = db.scalar(select(Device).where(Device.device_id == device_id))
            if d is None:
                raise NotFoundError(f"Device '{device_id}' is not registered.")
            d.student_label = label or None
            self.dirty = True
            return self.device_dict(d)

    # ------------------------------------------------------------------ live snapshot
    def snapshot(self, now: datetime | None = None) -> dict:
        now = now or utcnow()
        stale = timedelta(seconds=self.s.stale_telemetry_seconds)
        with self.db.session() as db:
            cls = self.active_class(db)
            devices = db.scalars(select(Device).order_by(Device.source, Device.device_id)).all()
            cds = {}
            if cls:
                cds = {cd.device_id: cd for cd in db.scalars(select(ClassDevice).where(ClassDevice.class_id == cls.id))}
            rows = []
            engaged = drift = connected = 0
            for d in devices:
                cd = cds.get(d.device_id)
                fresh = d.last_telemetry_at is not None and now - d.last_telemetry_at <= stale
                att = d.attention_state if (fresh and d.status == DEV_CONNECTED and cd is not None) else None
                if cd is not None and d.status == DEV_CONNECTED:
                    connected += 1
                    engaged += att == ATTN_ENGAGED
                    drift += att == ATTN_DRIFT
                row = self.device_dict(d, detail=False)
                row.update({"attention_state": att if cd is not None else None, "in_class": cd is not None,
                            "joined_late": bool(cd and cd.joined_late), "disconnect_count": cd.disconnect_count if cd else 0})
                rows.append(row)
            observed = engaged + drift
            pct = round(100.0 * engaged / observed, 1) if observed else None
            metrics = {
                "class_active": cls is not None,
                "connected": connected, "estimated_engaged": engaged, "possible_drift": drift,
                "no_data": max(0, connected - observed), "engagement_percentage": pct,
                "continuous_from_start": sum(1 for cd in cds.values() if not cd.joined_late and cd.disconnect_count == 0),
                "disconnected_at_least_once": sum(1 for cd in cds.values() if cd.disconnect_count > 0),
                "joined_after_start": sum(1 for cd in cds.values() if cd.joined_late),
                "total_registered": len(cds),
                "peak_connections": cls.peak_connections if cls else 0,
                "devices_online_real": sum(1 for d in devices if d.source == SRC_REAL and d.status == DEV_CONNECTED),
                "devices_online_sim": sum(1 for d in devices if d.source == SRC_SIM and d.status == DEV_CONNECTED),
            }
            point = None
            if cls is not None:
                point = {"t": iso(now), "engagement": pct, "connected": connected, "drift": drift, "engaged": engaged}
                if self._last_hist is None or (now - self._last_hist).total_seconds() >= self.s.live_history_interval:
                    self.live_history.append(point)
                    self._last_hist = now
            return {"type": "snapshot", "server_time": iso(now), "class": self.class_dict(cls, now) if cls else None,
                    "metrics": metrics, "devices": rows, "live_point": point,
                    "eeg": self.eeg.status() if self.eeg else {"mode": "OFF", "available": False},
                    "has_simulated": any(d.source == SRC_SIM for d in devices),
                    "settings": {"heartbeat_interval": self.s.heartbeat_interval, "device_timeout": self.s.device_timeout}}

    # ------------------------------------------------------------------ queries for REST
    def current_class(self) -> dict | None:
        with self.db.session() as db:
            c = self.active_class(db)
            return self.class_dict(c) if c else None

    def get_class(self, class_id: int) -> ClassSession:
        with self.db.session() as db:
            c = db.get(ClassSession, class_id)
            if c is None:
                raise NotFoundError(f"Class {class_id} was not found.")
            return c

    def list_classes(self, limit: int = 50) -> list[dict]:
        with self.db.session() as db:
            out = []
            for c in db.scalars(select(ClassSession).order_by(ClassSession.id.desc()).limit(limit)):
                d = self.class_dict(c)
                ws = db.execute(select(EngagementWindow.engagement_percentage, EngagementWindow.covered_seconds)
                                .where(EngagementWindow.class_id == c.id)).all()
                ws = [(p, s) for p, s in ws if p is not None and s > 0]
                tot = sum(s for _, s in ws)
                d["average_engagement_percentage"] = round(sum(p * s for p, s in ws) / tot, 1) if tot else None
                d["total_registered"] = db.scalar(select(func.count()).select_from(ClassDevice).where(ClassDevice.class_id == c.id)) or 0
                out.append(d)
            return out

    def class_analytics(self, class_id: int, source: str = "ALL", now: datetime | None = None) -> dict:
        use_cache = now is None
        now = now or utcnow()
        key = (class_id, source)
        if use_cache and key in self._cache:
            ts, data = self._cache[key]
            if time.monotonic() - ts < 2.0:
                return data
        with self.db.session() as db:
            cls = db.get(ClassSession, class_id)
            if cls is None:
                raise NotFoundError(f"Class {class_id} was not found.")
            windows, _, still_open = wnd.compute_windows(db, cls, now, source, self.s.min_obs_per_window)
            until = cls.end_time or now
            summary = class_summary(db, cls, until, source, windows, still_open)
            peak = wnd.peak_window(windows, cls.window_seconds)
            out_windows = [{**w, "window_start": iso(w["window_start"]), "window_end": iso(w["window_end"])} for w in windows]
            peak_out = None
            if peak:
                peak_out = {"index": peak["index"], "window_start": iso(peak["window_start"]),
                            "window_end": iso(peak["window_end"]), "engagement_percentage": peak["engagement_percentage"],
                            "statement": "Highest estimated engagement observed during this interval"}
            data = {"class": self.class_dict(cls, now), "source_filter": source, "windows": out_windows,
                    "peak": peak_out, "summary": summary, "methodology": METHODOLOGY}
        if use_cache:
            self._cache[key] = (time.monotonic(), data)
        return data

    def class_timeline(self, class_id: int, now: datetime | None = None) -> dict:
        now = now or utcnow()
        with self.db.session() as db:
            cls = db.get(ClassSession, class_id)
            if cls is None:
                raise NotFoundError(f"Class {class_id} was not found.")
            _, intervals, _ = wnd.compute_windows(db, cls, now, "ALL", self.s.min_obs_per_window)
            info = {d.device_id: d for d in db.scalars(select(Device).where(Device.device_id.in_(list(intervals) or [""])))}
            cds = {cd.device_id: cd for cd in db.scalars(select(ClassDevice).where(ClassDevice.class_id == class_id))}
            devs = []
            for dev_id, ivs in sorted(intervals.items(), key=lambda kv: (info[kv[0]].source if kv[0] in info else "", kv[0])):
                cd = cds.get(dev_id)
                devs.append({"device_id": dev_id, "source": info[dev_id].source if dev_id in info else SRC_REAL,
                             "joined_late": bool(cd and cd.joined_late), "disconnect_count": cd.disconnect_count if cd else 0,
                             "segments": [{"start": iso(a), "end": iso(b)} for a, b in ivs]})
            return {"class": self.class_dict(cls, now), "start": iso(cls.start_time),
                    "end": iso(cls.end_time or max(now, cls.scheduled_end or now)), "devices": devs}

    def list_events(self, limit: int = 100, class_id: int | None = None) -> list[dict]:
        with self.db.session() as db:
            q = select(EventLog).order_by(EventLog.id.desc()).limit(limit)
            if class_id is not None:
                q = q.where(EventLog.class_id == class_id)
            return [self.event_dict(e) for e in db.scalars(q)]

    def connection_events(self, class_id: int) -> list[dict]:
        with self.db.session() as db:
            rows = db.scalars(select(ConnectionEvent).where(ConnectionEvent.class_id == class_id)
                              .order_by(ConnectionEvent.timestamp, ConnectionEvent.id)).all()
            return [{"device_id": r.device_id, "event_type": r.event_type, "timestamp": iso(r.timestamp)} for r in rows]

