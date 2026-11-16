"""Policies and batch membership extend the existing operation/attempt journal."""
from sqlalchemy import Column, Integer, MetaData, String, Table

VERSION = 5
metadata = MetaData()
policies = Table("party_policies", metadata, Column("binding_key", String, primary_key=True),
    Column("version", Integer, primary_key=True), Column("evidence", String, nullable=False))
batches = Table("party_batches", metadata, Column("id", String, primary_key=True),
    Column("binding_key", String, nullable=False), Column("evidence", String, nullable=False),
    Column("state", String, nullable=False), Column("active_binding", String, unique=True),
    Column("cancel_requested", Integer, nullable=False, server_default="0"))
members = Table("party_batch_members", metadata, Column("child_id", String, primary_key=True),
    Column("batch_id", String, nullable=False), Column("position", Integer, nullable=False))


def upgrade(connection):
    metadata.create_all(connection)
