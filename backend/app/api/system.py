from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query, Request

from .. import __version__
from ..constants import SRC_SIM
from ..errors import ConflictError
from ..schemas import EEGFeaturesIn, SimAddIn, SimScenarioIn
from ..services.demo_seed import seed_demo_class
from ..utils import iso, utcnow
from .deps import core_of

router = APIRouter(tags=["system"])


@router.get("/api/health")
async def health(request: Request):
    core = core_of(request)
    db_ok = core.db.healthy()
    return {"backend": "OK", "database": "READY" if db_ok else "UNAVAILABLE", "version": __version__,
            "server_time": iso(utcnow()), "websocket_clients": len(request.app.state.hub.clients)}


@router.get("/api/settings")
async def settings(request: Request):
    return request.app.state.settings.public_dict()


@router.get("/api/events")
async def events(request: Request, limit: int = Query(100, ge=1, le=1000)):
    return core_of(request).list_events(limit)


@router.get("/api/live/history")
async def live_history(request: Request):
    return list(core_of(request).live_history)


# ---- EEG (software-in-the-loop) ------------------------------------------------------------
@router.get("/api/eeg/status")
async def eeg_status(request: Request):
    return request.app.state.eeg.status()


@router.post("/api/eeg/features")
async def eeg_push(payload: EEGFeaturesIn, request: Request):
    src = request.app.state.eeg.source
    if src is None or not hasattr(src, "ingest"):
        raise ConflictError("EEG feature push is only accepted when EEG_MODE=PHYSICAL_EEG.")
    f = src.ingest(payload.source, payload.delta, payload.theta, payload.alpha, payload.beta, payload.gamma,
                   payload.condition)
    return {"ok": True, "evidence": round(f.evidence, 3), "source": f.source}


# ---- demo & simulation ---------------------------------------------------------------------
@router.post("/api/demo/seed", status_code=201)
async def demo_seed(request: Request):
    return seed_demo_class(core_of(request))


@router.get("/api/sim/status")
async def sim_status(request: Request):
    return request.app.state.sim.status()


@router.post("/api/sim/add")
async def sim_add(payload: SimAddIn, request: Request):
    ids = request.app.state.sim.add(payload.count)
    return {"added": ids, **request.app.state.sim.status()}


@router.post("/api/sim/disconnect-random")
async def sim_disconnect_random(request: Request, count: int = Query(1, ge=1, le=60)):
    picked = request.app.state.sim.disconnect_random(count)
    if not picked:
        raise ConflictError("No connected simulated students to disconnect. Add simulated students first.")
    return {"disconnected": picked}


@router.post("/api/sim/reconnect-all")
async def sim_reconnect_all(request: Request):
    return {"reconnected": request.app.state.sim.reconnect_all()}


@router.post("/api/sim/scenario")
async def sim_scenario(payload: SimScenarioIn, request: Request):
    ids = request.app.state.sim.set_scenario(payload.scenario, payload.fraction)
    return {"scenario": payload.scenario, "devices": ids}


@router.post("/api/sim/clear")
async def sim_clear(request: Request):
    return {"removed": request.app.state.sim.clear()}


@router.post("/api/sim/{device_id}/disconnect")
async def sim_disconnect(device_id: str, request: Request):
    if not request.app.state.sim.disconnect(device_id):
        raise HTTPException(status_code=404, detail=f"Simulated student {device_id} is not running.")
    return {"disconnected": [device_id]}


@router.post("/api/sim/{device_id}/reconnect")
async def sim_reconnect(device_id: str, request: Request):
    if not request.app.state.sim.reconnect(device_id):
        raise HTTPException(status_code=404, detail=f"Simulated student {device_id} is not running.")
    return {"reconnected": [device_id]}
