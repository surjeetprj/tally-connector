"""Retain every verified State update instead of one trial per identity link."""
from sqlalchemy import Column, ForeignKeyConstraint, Index, MetaData, String, Table

VERSION = 7
metadata = MetaData()
audit = Table("party_state_update_audit", metadata,
    Column("operation_id", String, primary_key=True), Column("link_id", String, nullable=False),
    Column("evidence_json", String, nullable=False),
    ForeignKeyConstraint(["operation_id"], ["party_experiments.id"]),
    ForeignKeyConstraint(["link_id"], ["party_links.id"]))
Index("ix_state_update_link", audit.c.link_id)


def upgrade(connection):
    from innoforia_tally_connector.persistence.migrations.versions.v0004_party_transfers import experiments
    from innoforia_tally_connector.persistence.migrations.versions.v0001_party_links import party_links
    if "party_experiments" not in metadata.tables: experiments.to_metadata(metadata)
    if "party_links" not in metadata.tables: party_links.to_metadata(metadata)
    # No other table references the audit. Keep operations, links and their evidence intact.
    connection.exec_driver_sql("ALTER TABLE party_state_update_audit RENAME TO state_update_audit_v6")
    audit.create(connection)
    connection.exec_driver_sql("INSERT INTO party_state_update_audit (operation_id, link_id, evidence_json) "
        "SELECT operation_id, link_id, evidence_json FROM state_update_audit_v6 ORDER BY rowid")
    connection.exec_driver_sql("DROP TABLE state_update_audit_v6")
