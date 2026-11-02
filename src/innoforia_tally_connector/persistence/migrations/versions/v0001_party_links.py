"""Initial local identity links; no operation or queue schema yet."""
from sqlalchemy import Column, ForeignKeyConstraint, Integer, MetaData, String, Table, UniqueConstraint

VERSION = 1
metadata = MetaData()
bindings = Table(
    "company_bindings", metadata,
    Column("id", String, primary_key=True),
    Column("generation", Integer, primary_key=True),
    Column("business_id", Integer, nullable=False),
    Column("company_guid", String, nullable=False),
)
party_links = Table(
    "party_links", metadata,
    Column("id", String, primary_key=True),
    Column("binding_id", String, nullable=False),
    Column("generation", Integer, nullable=False),
    Column("bahi_id", String, nullable=False),
    Column("tally_guid", String, nullable=False),
    Column("evidence_json", String, nullable=False),
    ForeignKeyConstraint(["binding_id", "generation"],
                         ["company_bindings.id", "company_bindings.generation"]),
    UniqueConstraint("binding_id", "generation", "bahi_id"),
    UniqueConstraint("binding_id", "generation", "tally_guid"),
)
link_audit = Table(
    "party_link_audit", metadata,
    Column("link_id", String, primary_key=True),
    Column("evidence_json", String, nullable=False),
    ForeignKeyConstraint(["link_id"], ["party_links.id"]),
)


def upgrade(connection):
    metadata.create_all(connection)
