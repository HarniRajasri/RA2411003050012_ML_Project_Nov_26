"""Central configuration. Every tunable lives here or in .env - nothing is hard-coded elsewhere."""
from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
load_dotenv(PROJECT_ROOT / ".env")


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return float(default)


def _int(name: str, default: int) -> int:
    try:
        return int(float(os.getenv(name, default)))
    except ValueError:
        return int(default)


def _str(name: str, default: str) -> str:
    v = os.getenv(name)
    return default if v is None else v.strip()


def resolve_database_url(url: str) -> str:
    """Make relative sqlite paths relative to the project root (not the current directory)."""
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return url
    path = url[len(prefix):]
    if path in ("", ":memory:"):
        return url
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return prefix + p.as_posix()


@dataclass
class Settings:
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    database_url: str = "sqlite:///data/khorizon.db"
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"])
    log_level: str = "INFO"
    device_api_key: str = ""

    heartbeat_interval: float = 5.0
    device_timeout: float = 15.0
    device_stale_after: float = 0.0        # 0 -> 2 x heartbeat_interval
    join_grace_seconds: float = 60.0
    stale_telemetry_seconds: float = 10.0

    motion_threshold: float = 0.35
    drift_threshold: float = 0.45
    engagement_window_seconds: int = 600
    min_obs_per_window: int = 3

    snapshot_interval: float = 1.0
    live_history_interval: float = 2.0
    monitor_interval: float = 1.0
    persist_interval: float = 15.0
    run_monitor: bool = True
    sim_telemetry_interval: float = 2.0

    eeg_mode: str = "OFF"
    eeg_replay_file: str = "data/eeg_features/sub-01_ses-01.csv"
    eeg_replay_step_seconds: float = 2.0
    eeg_target_device: str = "KH-S01"

    fusion_w_motion_moving: float = 0.75
    fusion_w_eeg_moving: float = 0.25
    fusion_w_motion_stable: float = 0.30
    fusion_w_eeg_stable: float = 0.70

    frontend_dist: str = ""

    def __post_init__(self) -> None:
        if not self.device_stale_after:
            self.device_stale_after = 2 * self.heartbeat_interval
        self.database_url = resolve_database_url(self.database_url)
        self.eeg_mode = self.eeg_mode.upper()
        if not self.frontend_dist:
            self.frontend_dist = str(PROJECT_ROOT / "frontend" / "dist")

    @classmethod
    def from_env(cls) -> "Settings":
        d = cls()
        origins = _str("CORS_ORIGINS", "")
        return cls(
            backend_host=_str("BACKEND_HOST", d.backend_host),
            backend_port=_int("BACKEND_PORT", d.backend_port),
            database_url=_str("DATABASE_URL", d.database_url),
            cors_origins=[o.strip() for o in origins.split(",") if o.strip()] or d.cors_origins,
            log_level=_str("LOG_LEVEL", d.log_level).upper(),
            device_api_key=_str("DEVICE_API_KEY", ""),
            heartbeat_interval=_float("HEARTBEAT_INTERVAL", d.heartbeat_interval),
            device_timeout=_float("DEVICE_TIMEOUT", d.device_timeout),
            device_stale_after=_float("DEVICE_STALE_AFTER", 0.0),
            join_grace_seconds=_float("JOIN_GRACE_SECONDS", d.join_grace_seconds),
            motion_threshold=_float("MOTION_THRESHOLD", d.motion_threshold),
            drift_threshold=_float("DRIFT_THRESHOLD", d.drift_threshold),
            engagement_window_seconds=_int("ENGAGEMENT_WINDOW_SECONDS", d.engagement_window_seconds),
            eeg_mode=_str("EEG_MODE", d.eeg_mode),
            eeg_replay_file=_str("EEG_REPLAY_FILE", d.eeg_replay_file),
            eeg_replay_step_seconds=_float("EEG_REPLAY_STEP_SECONDS", d.eeg_replay_step_seconds),
            eeg_target_device=_str("EEG_TARGET_DEVICE", d.eeg_target_device),
            fusion_w_motion_moving=_float("FUSION_W_MOTION_MOVING", d.fusion_w_motion_moving),
            fusion_w_eeg_moving=_float("FUSION_W_EEG_MOVING", d.fusion_w_eeg_moving),
            fusion_w_motion_stable=_float("FUSION_W_MOTION_STABLE", d.fusion_w_motion_stable),
            fusion_w_eeg_stable=_float("FUSION_W_EEG_STABLE", d.fusion_w_eeg_stable),
        )

    def public_dict(self) -> dict:
        """Settings safe to show in the UI (never secrets)."""
        hidden = {"device_api_key", "database_url"}
        out = {f.name: getattr(self, f.name) for f in fields(self) if f.name not in hidden}
        out["device_api_key_required"] = bool(self.device_api_key)
        return out
