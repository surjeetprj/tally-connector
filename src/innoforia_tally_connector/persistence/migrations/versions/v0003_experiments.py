"""Explicit approvals and one external create attempt per synthetic experiment."""
from sqlalchemy import Column, ForeignKeyConstraint, MetaData, String, Table

VERSION = 3
metadata = MetaData()
experiments = Table("party_experiments", metadata,
    Column("id", String, primary_key=True), Column("binding_id", String, nullable=False),
    Column("preview_json", String, nullable=False), Column("state", String, nullable=False),
    Column("active_binding", String, unique=True), Column("reviewer", String),
    Column("approved_at", String), Column("approval_digest", String),
    Column("target_json", String), Column("comparisons_json", String), Column("message", String),
    Column("observation_json", String))
attempts = Table("sync_attempts", metadata,
    Column("experiment_id", String, primary_key=True), Column("operation_id", String, unique=True, nullable=False),
    Column("started_at", String, nullable=False), Column("payload_hash", String, nullable=False),
    Column("preflight_json", String, nullable=False),
    ForeignKeyConstraint(["experiment_id"], ["party_experiments.id"]))


def upgrade(connection):
    metadata.create_all(connection)
