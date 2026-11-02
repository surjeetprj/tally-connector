"""Connection evidence and durable local commands/outbox; no remote write queue."""
from sqlalchemy import Column, ForeignKeyConstraint, Integer, MetaData, String, Table, UniqueConstraint

VERSION = 2
metadata = MetaData()
settings = Table("discovery_settings", metadata, Column("id", Integer, primary_key=True),
                 Column("binding_json", String, nullable=False),
                 Column("classification_json", String, nullable=False),
                 Column("connection_json", String, nullable=False),
                 Column("credential_reference", String, nullable=False))
operations = Table("sync_operations", metadata, Column("id", String, primary_key=True),
                   Column("command_json", String, nullable=False),
                   Column("coalesce_key", String, nullable=True, unique=True),
                   Column("state", String, nullable=False), Column("error", String))
outbox = Table("dispatch_outbox", metadata, Column("operation_id", String, primary_key=True),
               ForeignKeyConstraint(["operation_id"], ["sync_operations.id"]))


def upgrade(connection):
    metadata.create_all(connection)
