"""Explicit ordered imports, including for frozen packaging."""
from innoforia_tally_connector.persistence.migrations.versions import v0001_party_links, v0002_discovery, v0003_experiments, v0004_party_transfers, v0005_batches
from innoforia_tally_connector.persistence.migrations.versions import v0006_state_update_audit, v0007_repeatable_state_updates

MIGRATIONS = (v0001_party_links, v0002_discovery, v0003_experiments, v0004_party_transfers, v0005_batches, v0006_state_update_audit, v0007_repeatable_state_updates)
