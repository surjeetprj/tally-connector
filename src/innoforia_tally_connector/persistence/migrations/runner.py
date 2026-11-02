"""Transactional metadata initialization; refuses foreign/newer databases."""
from sqlalchemy.engine import Engine
from pathlib import Path
import sqlite3
from uuid import uuid4
from contextlib import closing

from innoforia_tally_connector.persistence.migrations.registry import MIGRATIONS

APPLICATION_ID = 0x49544331


def migrate(engine: Engine) -> None:
    # Caller holds the process lock before starting consumers.
    with engine.connect() as connection:
        current = connection.exec_driver_sql("PRAGMA user_version").scalar_one()
        owner = connection.exec_driver_sql("PRAGMA application_id").scalar_one()
    if 0 < current < MIGRATIONS[-1].VERSION and owner == APPLICATION_ID:
        source = Path(engine.url.database)
        backup = source.with_name(source.name + f".v{current}.{uuid4().hex}.backup")
        # sqlite3.backup includes committed WAL data; copying the main file does not.
        with closing(sqlite3.connect(source)) as original, closing(sqlite3.connect(backup)) as saved:
            original.backup(saved)
    with engine.begin() as connection:
        version = connection.exec_driver_sql("PRAGMA user_version").scalar_one()
        owner = connection.exec_driver_sql("PRAGMA application_id").scalar_one()
        if version > MIGRATIONS[-1].VERSION:
            raise ValueError("Metadata schema is newer than this application")
        if owner not in (0, APPLICATION_ID) or (version and owner != APPLICATION_ID):
            raise ValueError("Not a connector metadata database")
        if version == 0:
            tables = connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).all()
            if tables:
                raise ValueError("Refusing to migrate an existing unrecognized database")
        for migration in MIGRATIONS:
            if migration.VERSION > version:
                migration.upgrade(connection)
                connection.exec_driver_sql(f"PRAGMA user_version={migration.VERSION}")
        connection.exec_driver_sql(f"PRAGMA application_id={APPLICATION_ID}")
