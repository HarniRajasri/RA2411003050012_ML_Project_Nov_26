import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings          # noqa: E402
from app.main import create_app          # noqa: E402

T0 = datetime(2026, 1, 12, 9, 0, 0)      # naive UTC, like the database


@pytest.fixture()
def settings(tmp_path):
    return Settings(database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}", run_monitor=False,
                    heartbeat_interval=5, device_timeout=15, join_grace_seconds=60, eeg_mode="OFF")


@pytest.fixture()
def app(settings):
    return create_app(settings)


@pytest.fixture()
def core(app):
    return app.state.core


@pytest.fixture()
def client(app):
    with TestClient(app) as c:
        yield c


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)
