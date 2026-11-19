from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .. import __version__
from ..utils import iso, utcnow

router = APIRouter()
log = logging.getLogger("khorizon.ws")


@router.websocket("/ws/dashboard")
async def dashboard_ws(ws: WebSocket):
    hub, core = ws.app.state.hub, ws.app.state.core
    await hub.connect(ws)
    try:
        await ws.send_text(json.dumps({"type": "hello", "server_time": iso(utcnow()), "version": __version__}))
        await ws.send_text(json.dumps(core.snapshot(), default=str))
        while True:
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        log.warning("ws_error error=%s", exc)
    finally:
        hub.disconnect(ws)
