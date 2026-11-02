"""Dedicated metadata engines. Startup ownership belongs to the caller."""
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, URL


def metadata_engine(path: Path) -> Engine:
    engine = create_engine(URL.create("sqlite+pysqlite", database=str(path.resolve())),
                           connect_args={"autocommit": False, "timeout": 5})

    @event.listens_for(engine, "connect")
    def configure(connection, _record):
        previous = connection.autocommit
        connection.autocommit = True
        try:
            cursor = connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA synchronous=FULL")
            cursor.close()
        finally:
            connection.autocommit = previous

    return engine
