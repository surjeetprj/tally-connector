from datetime import datetime, timezone

import pytest

from innoforia_tally_connector.domain.masters import (
    Binding, PartyContent, PartyObservation, PartyScan, PartyType, Side,
)
from innoforia_tally_connector.persistence.database import metadata_engine
from innoforia_tally_connector.persistence.migrations.runner import migrate
from innoforia_tally_connector.persistence.repositories.party_links import SqlPartyLinks


@pytest.fixture
def binding():
    return Binding(id="synthetic-binding", business_id=100, company_guid="synthetic-company", generation=1)


@pytest.fixture
def observation(binding):
    def make(side=Side.BAHI, identity="1", name="Example Supplier", **changes):
        values = dict(binding=binding, side=side, identity=identity, party_type=PartyType.SUPPLIER,
                      classification_evidence="synthetic reviewed classification",
                      content=PartyContent(name=name), observed_at=datetime.now(timezone.utc))
        values.update(changes)
        return PartyObservation(**values)
    return make


@pytest.fixture
def reader():
    class Reader:
        """Deliberately has no write capability. Failure is explicit, never success."""
        def __init__(self, records, **scan_options):
            self.records = records
            self.scan_options = scan_options
            self.detail_calls = []

        def scan(self, binding):
            return PartyScan(binding=binding, side=self.records[0].side,
                             records=tuple(self.records), observed_at=datetime.now(timezone.utc),
                             pages_read=(1,), total_pages=1, **self.scan_options)

        def detail(self, binding, identity):
            self.detail_calls.append(identity)
            return next(r for r in self.records if r.identity == identity)
    return Reader


@pytest.fixture
def store(tmp_path, binding):
    engine = metadata_engine(tmp_path / "metadata.db")
    migrate(engine)
    links = SqlPartyLinks(engine)
    links.register_binding(binding)
    yield links
    engine.dispose()
