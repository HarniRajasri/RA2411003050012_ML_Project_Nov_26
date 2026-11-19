from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query, Request

from ..schemas import ClassStartIn
from .deps import core_of

router = APIRouter(prefix="/api/classes", tags=["classes"])


@router.post("/start", status_code=201)
async def start_class(payload: ClassStartIn, request: Request):
    return core_of(request).start_class(payload)


@router.post("/end")
async def end_class(request: Request):
    return core_of(request).end_class()


@router.get("/current")
async def current_class(request: Request):
    c = core_of(request).current_class()
    return {"active": c is not None, "class": c}


@router.get("")
async def list_classes(request: Request, limit: int = Query(50, ge=1, le=200)):
    return core_of(request).list_classes(limit)


@router.get("/{class_id}")
async def get_class(class_id: int, request: Request):
    core = core_of(request)
    return core.class_dict(core.get_class(class_id))


@router.get("/{class_id}/analytics")
async def class_analytics(class_id: int, request: Request, source: Literal["ALL", "REAL", "SIMULATED"] = "ALL"):
    return core_of(request).class_analytics(class_id, source)


@router.get("/{class_id}/timeline")
async def class_timeline(class_id: int, request: Request):
    return core_of(request).class_timeline(class_id)


@router.get("/{class_id}/events")
async def class_events(class_id: int, request: Request, limit: int = Query(500, ge=1, le=2000)):
    core = core_of(request)
    core.get_class(class_id)
    return {"log": list(reversed(core.list_events(limit, class_id))), "connection_events": core.connection_events(class_id)}
