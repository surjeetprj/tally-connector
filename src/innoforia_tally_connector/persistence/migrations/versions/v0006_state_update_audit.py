"""One controlled state trial per confirmed link; original observations remain intact."""
from sqlalchemy import Column, ForeignKeyConstraint, MetaData, String, Table

VERSION = 6
metadata = MetaData()
audit = Table("party_state_update_audit", metadata,
    Column("operation_id", String, primary_key=True), Column("link_id", String, nullable=False, unique=True),
    Column("evidence_json", String, nullable=False),
    ForeignKeyConstraint(["operation_id"], ["party_experiments.id"]),
    ForeignKeyConstraint(["link_id"], ["party_links.id"]))
verifications = Table("party_state_update_verifications", metadata,
    Column("request_id", String, primary_key=True), Column("experiment_id", String, nullable=False),
    Column("evidence_json", String, nullable=False),
    ForeignKeyConstraint(["experiment_id"], ["party_experiments.id"]))


def upgrade(connection):
    # The referenced tables already exist; bind their metadata for FK resolution.
    from innoforia_tally_connector.persistence.migrations.versions.v0004_party_transfers import experiments
    from innoforia_tally_connector.persistence.migrations.versions.v0001_party_links import party_links
    if "party_experiments" not in metadata.tables: experiments.to_metadata(metadata)
    if "party_links" not in metadata.tables: party_links.to_metadata(metadata)
    audit.create(connection)
    verifications.create(connection)
