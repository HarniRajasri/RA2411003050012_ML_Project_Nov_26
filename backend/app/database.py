"""SQLAlchemy engine/session management. The SQLite file is created automatically on first run."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

log = logging.getLogger("khorizon.db")


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(self, url: str):
        self.url = url
        is_sqlite = url.startswith("sqlite")
        if is_sqlite and ":memory:" not in url:
            file_part = url.split("sqlite:///", 1)[-1]
            if file_part:
                Path(file_part).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(url, connect_args={"check_same_thread": False} if is_sqlite else {}, future=True)
        if is_sqlite:
            @event.listens_for(self.engine, "connect")
            def _pragmas(dbapi_conn, _):  # pragma: no cover - trivial
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA synchronous=NORMAL")
                cur.execute("PRAGMA busy_timeout=5000")
                cur.close()
        self._factory = sessionmaker(self.engine, expire_on_commit=False, future=True)

    def init(self) -> None:
        from . import models  # noqa: F401  (register tables)
        Base.metadata.create_all(self.engine)
        log.info("database ready url=%s", self.url)

    @contextmanager
    def session(self) -> Iterator[Session]:
        s = self._factory()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    def healthy(self) -> bool:
        try:
            with self.engine.connect() as c:
                c.execute(text("SELECT 1"))
            return True
        except Exception as exc:  # database unavailable
            log.error("database health check failed error=%s", exc)
            return False
