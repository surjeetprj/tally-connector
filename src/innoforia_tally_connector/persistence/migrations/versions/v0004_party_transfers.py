"""Real source reservations and queryable history on the shared attempt journal."""
import json
from sqlalchemy import Column, Integer, MetaData, String, text
from innoforia_tally_connector.persistence.migrations.versions.v0003_experiments import experiments as legacy

VERSION = 4
metadata = MetaData()
experiments = legacy.to_metadata(metadata)
for column in (Column("source_key", String), Column("kind", String, nullable=False, server_default="EXPERIMENT"),
               Column("created_at", String, nullable=False, server_default=""),
               Column("binding_generation", Integer, nullable=False, server_default="1"),
               Column("source_normal_party_confirmed", Integer, nullable=False, server_default="0")):
    experiments.append_column(column)


def upgrade(connection):
    connection.exec_driver_sql("ALTER TABLE party_experiments ADD COLUMN source_key VARCHAR")
    connection.exec_driver_sql("ALTER TABLE party_experiments ADD COLUMN kind VARCHAR NOT NULL DEFAULT 'EXPERIMENT'")
    connection.exec_driver_sql("ALTER TABLE party_experiments ADD COLUMN created_at VARCHAR NOT NULL DEFAULT ''")
    connection.exec_driver_sql("ALTER TABLE party_experiments ADD COLUMN binding_generation INTEGER NOT NULL DEFAULT 1")
    connection.exec_driver_sql("ALTER TABLE party_experiments ADD COLUMN source_normal_party_confirmed INTEGER NOT NULL DEFAULT 0")
    connection.exec_driver_sql("CREATE UNIQUE INDEX uq_party_transfer_source ON party_experiments(source_key)")
    connection.exec_driver_sql("CREATE INDEX ix_party_activity ON party_experiments(binding_id, binding_generation, created_at, id)")
    for identity, raw in connection.exec_driver_sql("SELECT id, preview_json FROM party_experiments").all():
        preview = json.loads(raw)
        connection.execute(text("UPDATE party_experiments SET created_at=:stamp, binding_generation=:generation WHERE id=:id"),
                           {"stamp": preview["created_at"], "generation": preview["binding"]["generation"], "id": identity})
