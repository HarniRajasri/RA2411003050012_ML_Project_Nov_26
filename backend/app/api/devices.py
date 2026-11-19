from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..schemas import DeviceRegisterIn, FeedbackIn, HeartbeatIn, LabelIn, TelemetryIn
from .deps import core_of, device_auth

router = APIRouter(tags=["devices"])


@router.post("/api/device/register", dependencies=[Depends(device_auth)])
async def register(payload: DeviceRegisterIn, request: Request):
    return core_of(request).register_device(payload)


@router.post("/api/device/heartbeat", dependencies=[Depends(device_auth)])
async def heartbeat(payload: HeartbeatIn, request: Request):
    return core_of(request).heartbeat(payload)


@router.post("/api/device/telemetry", dependencies=[Depends(device_auth)])
async def telemetry(payload: TelemetryIn, request: Request):
    return core_of(request).telemetry(payload)


@router.post("/api/device/feedback", dependencies=[Depends(device_auth)])
async def feedback(payload: FeedbackIn, request: Request):
    return core_of(request).feedback(payload)


@router.get("/api/devices")
async def list_devices(request: Request):
    return core_of(request).list_devices()


@router.get("/api/devices/{device_id}")
async def get_device(device_id: str, request: Request):
    return core_of(request).get_device(device_id)


@router.patch("/api/devices/{device_id}")
async def patch_device(device_id: str, payload: LabelIn, request: Request):
    return core_of(request).set_label(device_id, payload.student_label)
