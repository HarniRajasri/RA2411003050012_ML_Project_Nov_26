"""EEG input abstraction.

The rest of the system only ever sees `EEGFeatures` (EEG-derived features + a 0..1 evidence value) from an
`EEGSource`. Today the source is a public dataset replayed in software (software-in-the-loop). A physical EEG
sensor can replace it later by implementing the same interface - the fusion engine does not change.

EEG-derived features are NOT proof of listening or comprehension.
"""
from __future__ import annotations

import math
import statistics
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class EEGFeatures:
    source: str                    # DATASET_REPLAY | PHYSICAL_EEG
    timestamp: datetime            # server time the features became current
    delta: float
    theta: float
    alpha: float
    beta: float
    gamma: float
    engagement_index: float        # beta / (alpha + theta)   (Pope et al., 1995 style index)
    evidence: float                # 0..1 - normalised, higher = more estimated engagement evidence
    condition: str | None = None   # dataset session label, e.g. "ses-01 attentive"
    position_seconds: float | None = None


def engagement_index(alpha: float, beta: float, theta: float) -> float:
    return beta / max(alpha + theta, 1e-12)


class Normalizer:
    """Maps log(engagement index) to a 0..1 evidence value using a robust z-score (median / MAD)."""

    def __init__(self, indices: list[float]):
        logs = [math.log(max(i, 1e-9)) for i in indices] or [0.0]
        self.median = statistics.median(logs)
        mad = statistics.median([abs(x - self.median) for x in logs]) or 0.0
        self.scale = max(1.4826 * mad, 1e-6)

    def evidence(self, idx: float) -> float:
        z = (math.log(max(idx, 1e-9)) - self.median) / self.scale
        return 0.5 * (1.0 + math.tanh(z / 2.0))


class EEGSource(ABC):
    source_type: str = "UNKNOWN"

    async def start(self) -> None:  # pragma: no cover - default no-op
        return None

    async def stop(self) -> None:  # pragma: no cover - default no-op
        return None

    @abstractmethod
    def latest(self) -> EEGFeatures | None: ...

    @abstractmethod
    def status(self) -> dict: ...
