"""In-process simulation of student headbands for demos (dashboard "Demo & Simulation" page).

Each simulated student calls the same core methods a real ESP32 reaches through the REST API, so the analytics,
connection tracking and WebSocket updates are exercised end to end. Devices are always named SIM-xx.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass

from ..schemas import DeviceRegisterIn, FeedbackIn, HeartbeatIn, TelemetryIn
from .behavior import SimStudentModel, class_mood

log = logging.getLogger("khorizon.sim")
PROFILE_MIX = ["focused"] * 4 + ["average"] * 4 + ["restless"] * 2


@dataclass
class SimStudent:
    model: SimStudentModel
    sending: bool = True
    next_hb: float = 0.0
    next_tel: float = 0.0
    last_step: float = 0.0


class SimulationManager:
    def __init__(self, core, settings):
        self.core, self.s = core, settings
        self.students: dict[str, SimStudent] = {}
        self.scenario: str = "natural"
        self.scenario_ids: set[str] = set()
        self._t0 = time.monotonic()
        self._rng = random.Random()

    # ---------------------------------------------------------------- controls
    def add(self, count: int) -> list[str]:
        added = []
        n = 1
        while len(added) < count and n <= 99:
            did = f"SIM-{n:02d}"
            if did not in self.students:
                m = SimStudentModel(did, profile=self._rng.choice(PROFILE_MIX), rng=random.Random(self._rng.random()))
                now = time.monotonic()
                self.students[did] = SimStudent(m, True, now + self._rng.uniform(0, 1.0), now + self._rng.uniform(0.5, 2.0), now)
                self.core.register_device(DeviceRegisterIn(device_id=did, firmware_version="simulator"))
                added.append(did)
            n += 1
        log.info("sim_added count=%d", len(added))
        return added

    def disconnect(self, device_id: str) -> bool:
        st = self.students.get(device_id)
        if not st:
            return False
        st.sending = False
        return True

    def reconnect(self, device_id: str) -> bool:
        st = self.students.get(device_id)
        if not st:
            return False
        st.sending, st.last_step = True, time.monotonic()
        st.next_hb = st.next_tel = time.monotonic()
        return True

    def disconnect_random(self, count: int = 1) -> list[str]:
        live = [i for i, s in self.students.items() if s.sending]
        picked = self._rng.sample(live, min(count, len(live)))
        for i in picked:
            self.students[i].sending = False
        return picked

    def reconnect_all(self) -> list[str]:
        ids = [i for i, s in self.students.items() if not s.sending]
        for i in ids:
            self.reconnect(i)
        return ids

    def clear(self) -> int:
        n = len(self.students)
        self.students.clear()
        self.scenario, self.scenario_ids = "natural", set()
        return n

    def set_scenario(self, scenario: str, fraction: float) -> list[str]:
        ids = [i for i, s in self.students.items() if s.sending]
        if scenario == "natural":
            self.scenario, self.scenario_ids = "natural", set()
            return ids
        k = max(1, round(len(ids) * fraction)) if ids else 0
        self.scenario, self.scenario_ids = scenario, set(self._rng.sample(ids, min(k, len(ids))))
        return sorted(self.scenario_ids)

    def status(self) -> dict:
        return {"label": "SIMULATION MODE - synthetic students, not real hardware",
                "count": len(self.students), "sending": sum(1 for s in self.students.values() if s.sending),
                "scenario": self.scenario, "scenario_devices": len(self.scenario_ids),
                "students": [{"device_id": i, "profile": s.model.profile, "sending": s.sending, "state": s.model.state}
                             for i, s in sorted(self.students.items())]}

    # ---------------------------------------------------------------- loop
    async def run(self) -> None:
        while True:
            await asyncio.sleep(1.0)
            try:
                self.tick()
            except Exception:  # never let the simulator kill the backend
                log.exception("sim tick failed")

    def tick(self) -> None:
        now = time.monotonic()
        mood = class_mood(now - self._t0, self._rng.gauss(0, 0.02))
        for did, st in list(self.students.items()):
            if not st.sending:
                continue
            try:
                if now >= st.next_hb:
                    self.core.heartbeat(HeartbeatIn(device_id=did))
                    st.next_hb = now + self.s.heartbeat_interval
                if now >= st.next_tel:
                    dt = max(0.1, now - st.last_step)
                    st.last_step = now
                    forced = self.scenario if did in self.scenario_ids else None
                    tel, fb = st.model.step(dt, mood, forced)
                    self.core.telemetry(TelemetryIn(device_id=did, **tel))
                    for e in fb:
                        self.core.feedback(FeedbackIn(device_id=did, event=e))
                    st.next_tel = now + self.s.sim_telemetry_interval
            except Exception as exc:
                log.warning("sim device %s error: %s", did, exc)
