"""Chooses the EEG source from configuration and answers "what EEG evidence applies to this device?"."""
from __future__ import annotations

from ..constants import SRC_REAL
from .base import EEGSource
from .dataset_replay import DatasetReplaySource
from .physical import PushEEGSource


class EEGManager:
    def __init__(self, settings):
        self.mode = settings.eeg_mode
        self.target = settings.eeg_target_device
        self.source: EEGSource | None = None
        if self.mode == "DATASET_REPLAY":
            self.source = DatasetReplaySource(settings.eeg_replay_file, settings.eeg_replay_step_seconds)
        elif self.mode == "PHYSICAL_EEG":
            self.source = PushEEGSource()

    async def start(self) -> None:
        if self.source:
            await self.source.start()

    async def stop(self) -> None:
        if self.source:
            await self.source.stop()

    def applies_to(self, device_id: str, device_source: str) -> bool:
        if device_source != SRC_REAL:          # simulated students never receive EEG evidence
            return False
        return (not self.target) or device_id == self.target

    def evidence_for(self, device_id: str, device_source: str):
        """Returns (evidence 0..1, eeg_source_label) or None."""
        if not self.source or not self.applies_to(device_id, device_source):
            return None
        f = self.source.latest()
        return None if f is None else (f.evidence, f.source)

    def status(self) -> dict:
        if not self.source:
            return {"mode": "OFF", "available": False,
                    "label": "EEG input off - estimated attention uses head-motion evidence only",
                    "message": "Set EEG_MODE=DATASET_REPLAY in .env to enable dataset replay", "target_device": self.target}
        s = self.source.status()
        s["target_device"] = self.target or "all real devices"
        return s
