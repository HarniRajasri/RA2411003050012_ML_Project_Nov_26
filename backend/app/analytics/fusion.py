"""Hierarchical sensor-fusion engine.

Output: an *estimated* attention score in [0, 1] (1 = more estimated engagement), a two-state label and a
*model confidence* (how far from the decision boundary and how much the modalities agree). It is NOT a
statement about what a student is thinking, and it is not proof of listening or comprehension.

Hierarchy (all weights configurable):
    movement significant -> motion evidence weighted high, EEG-derived evidence low
    head stable          -> EEG-derived evidence weighted high, motion evidence low
    no EEG evidence      -> motion evidence only (fusion_mode = MOTION_ONLY)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..constants import ATTN_DRIFT, ATTN_ENGAGED


@dataclass
class FusionConfig:
    motion_threshold: float = 0.35      # motion_score at/above this counts as "significant movement"
    drift_threshold: float = 0.45       # attention_score below this -> possible attention drift
    hysteresis: float = 0.05            # leave drift only when score > drift_threshold + hysteresis
    smoothing: float = 0.5              # EMA weight of the newest observation (per device)
    w_motion_moving: float = 0.75
    w_eeg_moving: float = 0.25
    w_motion_stable: float = 0.30
    w_eeg_stable: float = 0.70
    state_blend: float = 0.7            # share of the firmware motion *state* in motion evidence
    state_evidence: dict = field(default_factory=lambda: {
        "NORMAL": 0.85, "MOVING": 0.50, "POSSIBLE_ATTENTION_DRIFT": 0.15, "FEEDBACK": 0.15,
    })

    @classmethod
    def from_settings(cls, s) -> "FusionConfig":
        return cls(
            motion_threshold=s.motion_threshold, drift_threshold=s.drift_threshold,
            w_motion_moving=s.fusion_w_motion_moving, w_eeg_moving=s.fusion_w_eeg_moving,
            w_motion_stable=s.fusion_w_motion_stable, w_eeg_stable=s.fusion_w_eeg_stable,
        )


@dataclass
class FusionResult:
    attention_score: float
    attention_state: str
    confidence: float             # model confidence, not certainty about a student's mental state
    fusion_mode: str              # MOTION_ONLY | MOTION_EEG
    movement_significant: bool
    motion_evidence: float
    eeg_evidence: float | None
    weights: tuple[float, float]  # (motion, eeg)


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


class FusionEngine:
    def __init__(self, cfg: FusionConfig):
        self.cfg = cfg
        self._score: dict[str, float] = {}
        self._state: dict[str, str] = {}

    def reset(self, device_id: str) -> None:
        self._score.pop(device_id, None)
        self._state.pop(device_id, None)

    def _weights(self, significant: bool) -> tuple[float, float]:
        c = self.cfg
        wm, we = (c.w_motion_moving, c.w_eeg_moving) if significant else (c.w_motion_stable, c.w_eeg_stable)
        total = wm + we
        return (wm / total, we / total) if total > 0 else (1.0, 0.0)

    def evaluate(self, device_id: str, motion_score: float, motion_state: str,
                 eeg_evidence: float | None = None) -> FusionResult:
        c = self.cfg
        state_ev = c.state_evidence.get(motion_state, 0.5)
        motion_ev = _clamp(c.state_blend * state_ev + (1 - c.state_blend) * (1.0 - motion_score))
        significant = motion_state in ("POSSIBLE_ATTENTION_DRIFT", "FEEDBACK") or motion_score >= c.motion_threshold

        if eeg_evidence is None:
            wm, we = 1.0, 0.0
            raw = motion_ev
            mode = "MOTION_ONLY"
            agreement, coverage = 0.5, 0.5
        else:
            wm, we = self._weights(significant)
            raw = wm * motion_ev + we * _clamp(eeg_evidence)
            mode = "MOTION_EEG"
            agreement, coverage = 1.0 - abs(motion_ev - eeg_evidence), 1.0

        prev = self._score.get(device_id)
        score = raw if prev is None else c.smoothing * raw + (1 - c.smoothing) * prev
        self._score[device_id] = score

        prev_state = self._state.get(device_id, ATTN_ENGAGED)
        if prev_state == ATTN_DRIFT:
            state = ATTN_ENGAGED if score > c.drift_threshold + c.hysteresis else ATTN_DRIFT
        else:
            state = ATTN_DRIFT if score < c.drift_threshold else ATTN_ENGAGED
        self._state[device_id] = state

        boundary = c.drift_threshold
        margin = min(1.0, abs(score - boundary) / max(boundary, 1.0 - boundary))
        confidence = _clamp(0.4 * margin + 0.4 * agreement + 0.2 * coverage)
        return FusionResult(round(score, 4), state, round(confidence, 3), mode, significant,
                            round(motion_ev, 4), None if eeg_evidence is None else round(eeg_evidence, 4), (wm, we))
