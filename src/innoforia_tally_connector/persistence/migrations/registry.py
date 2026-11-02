"""Explicit ordered imports, including for frozen packaging."""
from innoforia_tally_connector.persistence.migrations.versions import v0001_party_links, v0002_discovery

MIGRATIONS = (v0001_party_links, v0002_discovery)
