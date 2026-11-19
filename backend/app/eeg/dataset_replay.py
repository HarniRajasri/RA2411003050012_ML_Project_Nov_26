"""DATASET_REPLAY source: replays pre-extracted EEG-derived features from a public dataset (software-in-the-loop).

The CSV is produced offline by `eeg/feature_extraction.py` from BDF recordings
(Brain, Body, and Behaviour dataset, Experiment 2). This module deliberately depends only on the standard library.
This is a replay of recorded data - it is NOT live EEG from a student.
"""
from __future__ import annotations

import asyncio
import csv
import logging
from pathlib import Path

from ..config import PROJECT_ROOT
from ..utils import utcnow
from .base import EEGFeatures, EEGSource, Normalizer

log = logging.getLogger("khorizon.eeg")


class DatasetReplaySource(EEGSource):
    source_type = "DATASET_REPLAY"

    def __init__(self, csv_path: str, step_seconds: float = 2.0):
        p = Path(csv_path)
        self.path = p if p.is_absolute() else PROJECT_ROOT / p
        self.step = max(0.2, step_seconds)
        self.rows: list[dict] = []
        self._i = -1
        self._latest: EEGFeatures | None = None
        self._task: asyncio.Task | None = None
        self.message = ""
        self.norm: Normalizer | None = None
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self.message = (f"Feature file not found: {self.path}. Run eeg/feature_extraction.py on a BDF file "
                            "(see docs/eeg.md). Fusion continues in MOTION_ONLY mode.")
            log.warning("eeg replay unavailable: %s", self.message)
            return
        try:
            with self.path.open(newline="", encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    self.rows.append({
                        "start": float(r["window_start_s"]), "delta": float(r["delta"]), "theta": float(r["theta"]),
                        "alpha": float(r["alpha"]), "beta": float(r["beta"]), "gamma": float(r["gamma"]),
                        "idx": float(r["engagement_index"]), "condition": r.get("condition") or None,
                    })
            self.norm = Normalizer([r["idx"] for r in self.rows])
            self.message = f"Replaying {len(self.rows)} feature windows from {self.path.name}"
        except Exception as exc:
            self.rows = []
            self.message = f"Could not read feature file: {exc}"
            log.error("eeg replay load failed: %s", exc)

    @property
    def available(self) -> bool:
        return bool(self.rows)

    def _advance(self) -> None:
        if not self.rows:
            return
        self._i = (self._i + 1) % len(self.rows)
        r = self.rows[self._i]
        self._latest = EEGFeatures(
            source=self.source_type, timestamp=utcnow(), delta=r["delta"], theta=r["theta"], alpha=r["alpha"],
            beta=r["beta"], gamma=r["gamma"], engagement_index=r["idx"], evidence=self.norm.evidence(r["idx"]),
            condition=r["condition"], position_seconds=r["start"])

    async def _run(self) -> None:
        while True:
            self._advance()
            await asyncio.sleep(self.step)

    async def start(self) -> None:
        if self.available and self._task is None:
            self._advance()
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

    def latest(self) -> EEGFeatures | None:
        return self._latest

    def status(self) -> dict:
        f = self._latest
        return {
            "mode": self.source_type, "available": self.available, "message": self.message,
            "label": "EEG dataset replay (software-in-the-loop) - not live EEG",
            "windows": len(self.rows),
            "condition": f.condition if f else None,
            "position_seconds": f.position_seconds if f else None,
            "engagement_index": round(f.engagement_index, 3) if f else None,
            "evidence": round(f.evidence, 3) if f else None,
            "bands": {k: round(getattr(f, k), 4) for k in ("delta", "theta", "alpha", "beta", "gamma")} if f else None,
        }
