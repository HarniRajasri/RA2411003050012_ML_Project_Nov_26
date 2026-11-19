"""Request models. Everything a device or browser sends is validated here before it touches the database."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

DEVICE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{2,31}$"
MAC_PATTERN = r"^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$"
MotionState = Literal["NORMAL", "MOVING", "POSSIBLE_ATTENTION_DRIFT", "FEEDBACK"]


class _Base(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")


class DeviceRegisterIn(_Base):
    device_id: str = Field(pattern=DEVICE_ID_PATTERN)
    mac_address: Optional[str] = Field(default=None, pattern=MAC_PATTERN)
    firmware_version: Optional[str] = Field(default=None, max_length=32)
    student_label: Optional[str] = Field(default=None, max_length=40)


class HeartbeatIn(_Base):
    device_id: str = Field(pattern=DEVICE_ID_PATTERN)
    timestamp: Optional[str] = Field(default=None, max_length=40)   # informational only; server time is authoritative
    uptime_ms: Optional[int] = Field(default=None, ge=0)
    rssi: Optional[int] = Field(default=None, ge=-120, le=0)
    sensor_ok: Optional[bool] = None


class TelemetryIn(_Base):
    device_id: str = Field(pattern=DEVICE_ID_PATTERN)
    timestamp: Optional[str] = Field(default=None, max_length=40)
    motion_score: float = Field(ge=0.0, le=1.0)
    motion_state: MotionState
    acceleration_magnitude: float = Field(ge=0.0, le=50.0)     # g
    angular_velocity: float = Field(ge=0.0, le=100.0)          # rad/s
    orientation_change: float = Field(ge=0.0, le=360.0)        # degrees vs. slow baseline posture


class FeedbackIn(_Base):
    device_id: str = Field(pattern=DEVICE_ID_PATTERN)
    event: Literal["FEEDBACK_TRIGGERED", "FEEDBACK_ACKNOWLEDGED"]
    feedback_type: Optional[str] = Field(default=None, max_length=32)
    timestamp: Optional[str] = Field(default=None, max_length=40)


class ClassStartIn(_Base):
    name: str = Field(min_length=1, max_length=120)
    duration_minutes: Optional[int] = Field(default=None, ge=1, le=600)
    scheduled_end: Optional[datetime] = None
    window_seconds: Optional[int] = Field(default=None, ge=10, le=3600)
    is_demo: bool = False


class LabelIn(_Base):
    student_label: Optional[str] = Field(default=None, max_length=40)


class SimAddIn(_Base):
    count: int = Field(default=10, ge=1, le=60)


class SimScenarioIn(_Base):
    scenario: Literal["natural", "drift_wave", "focus_wave"]
    fraction: float = Field(default=0.5, ge=0.0, le=1.0)


class EEGFeaturesIn(_Base):
    source: Literal["DATASET_REPLAY", "PHYSICAL_EEG"]
    delta: float = Field(ge=0.0)
    theta: float = Field(ge=0.0)
    alpha: float = Field(ge=0.0)
    beta: float = Field(ge=0.0)
    gamma: float = Field(ge=0.0)
    condition: Optional[str] = Field(default=None, max_length=60)
