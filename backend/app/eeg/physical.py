"""PHYSICAL_EEG source: receives EEG-derived band powers pushed by an external process/sensor driver.

There is currently NO physical EEG sensor in this project. This adapter exists so that a future headset driver can
POST band powers to /api/eeg/features (same schema, `source: PHYSICAL_EEG`) without touching the fusion engine.
Normalisation uses a rolling window of the most recent indices.
"""
from __future__ import annotations

from collections import deque

from ..utils import utcnow
from .base import EEGFeatures, EEGSource, Normalizer, engagement_index

FRESH_SECONDS = 10.0


class PushEEGSource(EEGSource):
    source_type = "PHYSICAL_EEG"

    def __init__(self):
        self._latest: EEGFeatures | None = None
        self._history: deque[float] = deque(maxlen=300)

    def ingest(self, source: str, delta: float, theta: float, alpha: float, beta: float, gamma: float,
               condition: str | None = None) -> EEGFeatures:
        idx = engagement_index(alpha, beta, theta)
        self._history.append(idx)
        ev = Normalizer(list(self._history)).evidence(idx) if len(self._history) >= 5 else 0.5
        self._latest = EEGFeatures(source=source, timestamp=utcnow(), delta=delta, theta=theta, alpha=alpha,
                                   beta=beta, gamma=gamma, engagement_index=idx, evidence=ev, condition=condition)
        return self._latest

    def latest(self) -> EEGFeatures | None:
        f = self._latest
        if f is None or (utcnow() - f.timestamp).total_seconds() > FRESH_SECONDS:
            return None
        return f

    def status(self) -> dict:
        f = self.latest()
        return {
            "mode": self.source_type, "available": f is not None,
            "label": "External EEG feature feed (no physical EEG sensor is connected in this prototype)",
            "message": "Waiting for features on POST /api/eeg/features" if f is None else "Receiving features",
            "engagement_index": round(f.engagement_index, 3) if f else None,
            "evidence": round(f.evidence, 3) if f else None,
            "feed_source": f.source if f else None,
        }
