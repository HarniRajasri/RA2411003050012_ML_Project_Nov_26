"""Standalone student simulator: many synthetic headbands talking to a running KHorizon backend over HTTP.

    python student_simulator.py --url http://localhost:8000 --students 25 --duration 600 --flaky

Every student is named SIM-01, SIM-02 ... so the backend and dashboard always label the data SIMULATED.
Simulated data is only for demonstrating and load-testing the software. It is not real hardware, real students
or real EEG. (The dashboard's Demo & Simulation page runs the same behaviour model inside the backend.)
"""
from __future__ import annotations

import argparse
import asyncio
import random
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:                                   # pragma: no cover
    sys.exit("httpx is required: pip install httpx   (or install the backend requirements.txt)")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.sim.behavior import SimStudentModel, class_mood   # noqa: E402  (pure-Python behaviour model)

PROFILE_MIX = ["focused"] * 4 + ["average"] * 4 + ["restless"] * 2


class Stats:
    def __init__(self) -> None:
        self.ok = self.fail = self.telemetry = self.feedback = self.disconnects = 0


async def student(idx: int, a: argparse.Namespace, client: httpx.AsyncClient, stats: Stats, t0: float, stop: asyncio.Event):
    did = f"SIM-{idx:02d}"
    rnd = random.Random(a.seed + idx)
    model = SimStudentModel(did, profile=rnd.choice(PROFILE_MIX), rng=random.Random(a.seed * 31 + idx))
    headers = {"X-KH-Key": a.key} if a.key else {}

    async def post(path: str, body: dict) -> dict | None:
        try:
            r = await client.post(a.url.rstrip("/") + path, json=body, headers=headers, timeout=5)
            if r.status_code < 300:
                stats.ok += 1
                return r.json()
            stats.fail += 1
            print(f"[{did}] {path} -> HTTP {r.status_code}: {r.text[:120]}", file=sys.stderr)
        except httpx.HTTPError as exc:
            stats.fail += 1
            print(f"[{did}] {path} failed: {exc.__class__.__name__}", file=sys.stderr)
        return None

    await asyncio.sleep(rnd.uniform(0, min(3.0, a.students * 0.1)))
    await post("/api/device/register", {"device_id": did, "firmware_version": "simulator"})
    last_hb = 0.0
    last = time.monotonic()
    offline_until = 0.0
    while not stop.is_set():
        now = time.monotonic()
        if now < offline_until:
            await asyncio.sleep(0.5)
            last = time.monotonic()
            continue
        if a.flaky and rnd.random() < a.disconnect_rate * a.interval:
            offline_until = now + rnd.uniform(20, 60)
            stats.disconnects += 1
            print(f"[{did}] going offline for {offline_until - now:.0f}s")
            continue
        if now - last_hb >= a.heartbeat:
            await post("/api/device/heartbeat", {"device_id": did, "uptime_ms": int((now - t0) * 1000), "rssi": rnd.randint(-75, -45), "sensor_ok": True})
            last_hb = now
        tel, events = model.step(max(0.1, now - last), class_mood(now - t0, rnd.gauss(0, 0.02)))
        last = now
        if await post("/api/device/telemetry", {"device_id": did, **tel}):
            stats.telemetry += 1
        for e in events:
            if await post("/api/device/feedback", {"device_id": did, "event": e, "feedback_type": "LED_VIBRATION"}):
                stats.feedback += 1
        try:
            await asyncio.wait_for(stop.wait(), timeout=a.interval)
        except asyncio.TimeoutError:
            pass


async def main_async(a: argparse.Namespace) -> int:
    stats, stop, t0 = Stats(), asyncio.Event(), time.monotonic()
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=max(10, a.students))) as client:
        try:
            h = await client.get(a.url.rstrip("/") + "/api/health", timeout=5)
            h.raise_for_status()
        except Exception as exc:
            print(f"ERROR: cannot reach the backend at {a.url} ({exc.__class__.__name__}). Start it first (see README).", file=sys.stderr)
            return 2
        print(f"SIMULATION MODE - {a.students} synthetic students -> {a.url}   (Ctrl+C to stop)")
        tasks = [asyncio.create_task(student(i, a, client, stats, t0, stop)) for i in range(1, a.students + 1)]
        try:
            if a.duration > 0:
                await asyncio.sleep(a.duration)
            else:
                await asyncio.Event().wait()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            stop.set()
            await asyncio.gather(*tasks, return_exceptions=True)
    print(f"stopped. requests ok={stats.ok} failed={stats.fail} telemetry={stats.telemetry} "
          f"feedback_events={stats.feedback} simulated_disconnects={stats.disconnects}")
    return 0 if stats.fail == 0 else 1


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default="http://localhost:8000")
    p.add_argument("--students", "-n", type=int, default=20)
    p.add_argument("--duration", type=float, default=0, help="seconds to run (0 = until Ctrl+C)")
    p.add_argument("--interval", type=float, default=2.0, help="telemetry interval in seconds")
    p.add_argument("--heartbeat", type=float, default=5.0, help="heartbeat interval in seconds")
    p.add_argument("--flaky", action="store_true", help="randomly disconnect and reconnect students")
    p.add_argument("--disconnect-rate", type=float, default=0.004, help="per-second disconnect probability when --flaky")
    p.add_argument("--key", default="", help="X-KH-Key value when the backend has DEVICE_API_KEY set")
    p.add_argument("--seed", type=int, default=7)
    a = p.parse_args()
    if not 1 <= a.students <= 99:
        p.error("--students must be between 1 and 99")
    try:
        return asyncio.run(main_async(a))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
