from __future__ import annotations

from fastapi import HTTPException, Request


def core_of(request: Request):
    return request.app.state.core


def device_auth(request: Request) -> None:
    """Optional shared key (DEVICE_API_KEY). Disabled when the variable is empty."""
    key = request.app.state.settings.device_api_key
    if key and request.headers.get("x-kh-key") != key:
        raise HTTPException(status_code=401, detail="Missing or invalid device key (header X-KH-Key).")
