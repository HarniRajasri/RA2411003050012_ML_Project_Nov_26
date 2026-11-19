"""KHorizon backend entry point.

Run:  uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000   (from the backend/ folder)
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from . import __version__
from .analytics.fusion import FusionConfig, FusionEngine
from .api import classes, devices, system, ws
from .config import Settings
from .database import Database
from .eeg import EEGManager
from .errors import DomainError
from .services import KHorizonCore
from .sim.manager import SimulationManager
from .websocket.hub import Hub, monitor_loop, publisher_loop

log = logging.getLogger("khorizon")


def configure_logging(level: str) -> None:
    logging.basicConfig(level=getattr(logging, level, logging.INFO),
                        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)   # heartbeats would flood the console


def _humanise(errors: list[dict]) -> str:
    parts = []
    for e in errors[:4]:
        loc = ".".join(str(x) for x in e.get("loc", []) if x != "body")
        parts.append(f"{loc or 'request'}: {e.get('msg', 'invalid value')}")
    return "; ".join(parts)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    configure_logging(settings.log_level)
    database = Database(settings.database_url)
    database.init()
    eeg = EEGManager(settings)
    core = KHorizonCore(settings, database, FusionEngine(FusionConfig.from_settings(settings)), eeg)
    hub = Hub()
    sim = SimulationManager(core, settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        tasks = [asyncio.create_task(publisher_loop(core, hub, settings.snapshot_interval)),
                 asyncio.create_task(sim.run())]
        if settings.run_monitor:
            tasks.append(asyncio.create_task(monitor_loop(core, settings.monitor_interval, settings.persist_interval)))
        await eeg.start()
        log.info("KHorizon backend %s ready (eeg_mode=%s)", __version__, settings.eeg_mode)
        try:
            yield
        finally:
            await eeg.stop()
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    app = FastAPI(title="KHorizon Smart Headband API", version=__version__, lifespan=lifespan,
                  description="Classroom estimated-engagement analytics. Estimates only - not proof of attention.")
    app.state.settings, app.state.core, app.state.hub = settings, core, hub
    app.state.sim, app.state.eeg, app.state.database = sim, eeg, database

    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                       allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message, "code": exc.code})

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        msg = _humanise(exc.errors())
        if request.url.path.startswith("/api/device/"):
            log.warning("invalid_device_payload path=%s error=%s", request.url.path, msg)
        return JSONResponse(status_code=422, content={"detail": f"Invalid request - {msg}", "code": "validation_error"})

    @app.exception_handler(SQLAlchemyError)
    async def _db(_: Request, exc: SQLAlchemyError):
        log.error("database_error error=%s", exc)
        return JSONResponse(status_code=503, content={"detail": "Database is unavailable. Check the backend log.", "code": "database_error"})

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("unhandled_error")
        return JSONResponse(status_code=500, content={"detail": "Unexpected server error. See the backend log.", "code": "internal_error"})

    for r in (classes.router, devices.router, system.router, ws.router):
        app.include_router(r)

    dist = Path(settings.frontend_dist)
    if (dist / "index.html").exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="dashboard")
    else:
        @app.get("/", include_in_schema=False)
        async def _root():
            return {"service": "KHorizon backend", "version": __version__, "docs": "/docs",
                    "dashboard": "Frontend build not found. Run `npm run build` in frontend/ or start the Vite dev server (see README)."}
    return app
