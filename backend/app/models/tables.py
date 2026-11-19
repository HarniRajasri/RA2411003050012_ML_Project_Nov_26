"""Database tables. Device IDs are anonymous; no personal information is stored."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from ..utils import utcnow


class ClassSession(Base):
    __tablename__ = "classes"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    start_time: Mapped[datetime] = mapped_column(DateTime)
    scheduled_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", index=True)
    window_seconds: Mapped[int] = mapped_column(Integer, default=600)
    peak_connections: Mapped[int] = mapped_column(Integer, default=0)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)   # DEMO / SIMULATED sample data


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    student_label: Mapped[str | None] = mapped_column(String(40), nullable=True)
    mac_address: Mapped[str | None] = mapped_column(String(17), nullable=True)
    source: Mapped[str] = mapped_column(String(12), default="REAL")       # REAL | SIMULATED
    firmware_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="DISCONNECTED", index=True)
    connected_since: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_disconnected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # live state (latest observation only; history lives in telemetry / attention_events)
    motion_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    attention_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    attention_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    fusion_mode: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_telemetry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ClassDevice(Base):
    """A device that took part in a class (first qualifying connection + continuity counters)."""
    __tablename__ = "class_devices"
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), index=True)
    device_id: Mapped[str] = mapped_column(String(32), index=True)
    first_connected_at: Mapped[datetime] = mapped_column(DateTime)
    last_connected_at: Mapped[datetime] = mapped_column(DateTime)
    joined_late: Mapped[bool] = mapped_column(Boolean, default=False)
    disconnect_count: Mapped[int] = mapped_column(Integer, default=0)
    reconnect_count: Mapped[int] = mapped_column(Integer, default=0)
    drift_events: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint("class_id", "device_id", name="uq_class_device"),)


class ConnectionEvent(Base):
    __tablename__ = "connection_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"))
    device_id: Mapped[str] = mapped_column(String(32))
    event_type: Mapped[str] = mapped_column(String(16))   # CONNECTED | DISCONNECTED | RECONNECTED
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (Index("ix_conn_class_ts", "class_id", "timestamp"), Index("ix_conn_class_dev", "class_id", "device_id"))


class Telemetry(Base):
    __tablename__ = "telemetry"
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"))
    device_id: Mapped[str] = mapped_column(String(32))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    motion_score: Mapped[float] = mapped_column(Float)
    motion_state: Mapped[str] = mapped_column(String(32))
    orientation_change: Mapped[float] = mapped_column(Float)
    angular_velocity: Mapped[float] = mapped_column(Float)
    acceleration_magnitude: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(12), default="REAL")
    __table_args__ = (Index("ix_tel_class_dev_ts", "class_id", "device_id", "timestamp"),)


class AttentionEvent(Base):
    """One estimated-attention observation (output of the fusion engine)."""
    __tablename__ = "attention_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"))
    device_id: Mapped[str] = mapped_column(String(32))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    state: Mapped[str] = mapped_column(String(32))
    score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)    # model confidence, not certainty
    source: Mapped[str] = mapped_column(String(12), default="REAL")           # REAL | SIMULATED
    fusion_mode: Mapped[str] = mapped_column(String(40), default="MOTION_ONLY")
    eeg_source: Mapped[str | None] = mapped_column(String(24), nullable=True)  # DATASET_REPLAY | PHYSICAL_EEG
    __table_args__ = (Index("ix_att_class_ts", "class_id", "timestamp"), Index("ix_att_class_dev", "class_id", "device_id"))


class FeedbackEvent(Base):
    __tablename__ = "feedback_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), index=True)
    device_id: Mapped[str] = mapped_column(String(32), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    feedback_type: Mapped[str] = mapped_column(String(32), default="LED_VIBRATION")
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class EngagementWindow(Base):
    __tablename__ = "engagement_windows"
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), index=True)
    window_index: Mapped[int] = mapped_column(Integer)
    window_start: Mapped[datetime] = mapped_column(DateTime)
    window_end: Mapped[datetime] = mapped_column(DateTime)
    connected_students: Mapped[int] = mapped_column(Integer, default=0)
    estimated_engaged_students: Mapped[int] = mapped_column(Integer, default=0)
    possible_drift_students: Mapped[int] = mapped_column(Integer, default=0)
    engagement_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    observations: Mapped[int] = mapped_column(Integer, default=0)
    covered_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint("class_id", "window_index", name="uq_class_window"),)


class EventLog(Base):
    """Human-readable live event feed (class start/end, connections, feedback)."""
    __tablename__ = "event_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int | None] = mapped_column(ForeignKey("classes.id"), nullable=True, index=True)
    device_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    event_type: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(12), default="SYSTEM")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
