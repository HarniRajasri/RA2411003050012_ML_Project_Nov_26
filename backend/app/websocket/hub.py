"""WebSocket fan-out to dashboard clients, plus the background loops that feed it."""
from __future__ import annotations

import asyncio
import json
import logging
import time

from fastapi import WebSocket

log = logging.getLogger("khorizon.ws")


class Hub:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.add(ws)
        log.info("ws_client_connected clients=%d", len(self.clients))

    def disconnect(self, ws: WebSocket) -> None:
        self.clients.discard(ws)
        log.info("ws_client_disconnected clients=%d", len(self.clients))

    async def broadcast(self, message: dict) -> None:
        if not self.clients:
            return
        data = json.dumps(message, default=str)
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send_text(data)
            except Exception as exc:
                log.warning("ws_send_failed error=%s", exc)
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)


async def publisher_loop(core, hub: Hub, interval: float) -> None:
    """Drains queued events immediately (<=0.25 s) and pushes a fresh snapshot on change or every `interval` s."""
    last = 0.0
    while True:
        await asyncio.sleep(0.25)
        try:
            for msg in core.drain():
                await hub.broadcast(msg)
            now = time.monotonic()
            if core.dirty or now - last >= interval:
                core.dirty = False
                last = now
                await hub.broadcast(core.snapshot())
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("publisher loop error")


async def monitor_loop(core, interval: float, persist_every: float) -> None:
    """Heartbeat supervision + periodic persistence of the running analytics windows."""
    last_persist = time.monotonic()
    while True:
        await asyncio.sleep(interval)
        try:
            core.check_timeouts()
            if time.monotonic() - last_persist >= persist_every:
                last_persist = time.monotonic()
                core.persist_active_windows()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("monitor loop error")
