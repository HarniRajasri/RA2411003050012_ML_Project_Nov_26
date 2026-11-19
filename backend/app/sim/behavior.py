"""Behaviour model for SIMULATED students. Pure Python (no dependencies).

Everything produced here is synthetic and is always sent under a `SIM-xx` device ID so the backend and the
dashboard label it SIMULATED. It never pretends to be real hardware or real EEG.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

# per-profile baseline "distraction pressure" 0..1 (higher -> more head movement / drift episodes)
PROFILES = {"focused": 0.12, "average": 0.30, "restless": 0.55}


@dataclass
class SimStudentModel:
    device_id: str
    profile: str = "average"
    rng: random.Random = field(default_factory=random.Random)
    state: str = "NORMAL"
    timer: float = 0.0            # seconds left in the current state
    recent_moves: float = 0.0
    cooldown: float = 0.0
    feedback_open: bool = False
    ack_in: float | None = None

    def pressure(self, mood: float, forced: str | None) -> float:
        if forced == "drift_wave":
            return 0.95
        if forced == "focus_wave":
            return 0.0
        return min(1.0, PROFILES.get(self.profile, 0.3) + mood)

    def step(self, dt: float, mood: float = 0.0, forced: str | None = None):
        """Advance the model by dt seconds. Returns (telemetry_dict, [feedback_events])."""
        r = self.rng
        p = self.pressure(mood, forced)
        events: list[str] = []
        self.timer -= dt
        self.recent_moves = max(0.0, self.recent_moves - dt / 25.0)
        self.cooldown = max(0.0, self.cooldown - dt)

        if self.state == "NORMAL":
            if forced == "focus_wave":
                pass
            elif r.random() < (0.02 + 0.14 * p) * dt:
                self.state, self.timer = "MOVING", r.uniform(2.0, 6.0)
                self.recent_moves += 1.0
        elif self.state == "MOVING" and self.timer <= 0:
            go_drift = self.cooldown <= 0 and (self.recent_moves >= 3 or r.random() < 0.1 + 0.8 * p)
            if forced == "focus_wave":
                go_drift = False
            if go_drift:
                self.state, self.timer = "POSSIBLE_ATTENTION_DRIFT", r.uniform(1.5, 3.0)
            else:
                self.state = "NORMAL"
        elif self.state == "POSSIBLE_ATTENTION_DRIFT" and self.timer <= 0:
            self.state, self.timer = "FEEDBACK", r.uniform(12.0, 25.0)
            self.feedback_open = True
            events.append("FEEDBACK_TRIGGERED")
            self.ack_in = r.uniform(3.0, 12.0) if r.random() < 0.7 else None
        elif self.state == "FEEDBACK":
            if self.ack_in is not None:
                self.ack_in -= dt
            if (self.ack_in is not None and self.ack_in <= 0) or self.timer <= 0 or forced == "focus_wave":
                if self.feedback_open and self.ack_in is not None and self.ack_in <= 0:
                    events.append("FEEDBACK_ACKNOWLEDGED")
                self.feedback_open, self.ack_in = False, None
                self.state, self.cooldown = "NORMAL", 30.0
                self.recent_moves = 0.0

        return self._telemetry(), events

    def _telemetry(self) -> dict:
        r = self.rng
        clamp = lambda x, lo, hi: max(lo, min(hi, x))
        if self.state == "NORMAL":
            score, ang, ori = r.gauss(0.08, 0.04), r.gauss(0.15, 0.07), r.gauss(3.0, 1.5)
        elif self.state == "MOVING":
            score, ang, ori = r.uniform(0.35, 0.65), r.uniform(0.8, 2.0), r.uniform(8, 20)
        else:
            score, ang, ori = r.uniform(0.55, 0.9), r.uniform(0.6, 1.8), r.uniform(20, 45)
        return {
            "motion_score": round(clamp(score, 0.0, 1.0), 3),
            "motion_state": self.state,
            "acceleration_magnitude": round(clamp(r.gauss(1.0, 0.03 + 0.1 * score), 0.7, 2.5), 3),
            "angular_velocity": round(clamp(ang, 0.0, 6.0), 3),
            "orientation_change": round(clamp(ori, 0.0, 90.0), 2),
        }


def class_mood(t_seconds: float, rng_noise: float = 0.0) -> float:
    """Slowly varying class-wide distraction pressure (0..~0.4) so interval analytics are not flat."""
    return max(0.0, 0.15 + 0.12 * math.sin(t_seconds / 240.0) + 0.05 * math.sin(t_seconds / 61.0) + rng_noise)
