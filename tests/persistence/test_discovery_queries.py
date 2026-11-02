"""Count real mapping queries; no timing or live-service assumptions."""
import pytest
from sqlalchemy import event

from innoforia_tally_connector.application.masters.parties import discover
from innoforia_tally_connector.domain.masters import PartyContent, Side


@pytest.mark.parametrize("size", [1, 100, 1000])
def test_discovery_mapping_queries_are_linear(size, binding, observation, reader, store):
    left = [observation(identity=str(n), content=PartyContent(
        name=f"Bahi example {n}", gstin=f"BAHI-{n}")) for n in range(size)]
    right = [observation(Side.TALLY, str(n), content=PartyContent(
        name=f"Tally example {n}", gstin=f"TALLY-{n}")) for n in range(size)]
    statements = []

    def record_sql(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    # Register only after disposable schema/binding setup, so this measures
    # discovery itself and catches any accidental persistence writes.
    event.listen(store.engine, "before_cursor_execute", record_sql)
    try:
        result = discover(binding, reader(left), reader(right), store)
    finally:
        event.remove(store.engine, "before_cursor_execute", record_sql)

    mapping_selects = [sql for sql in statements
                       if sql.lstrip().upper().startswith("SELECT")
                       and "FROM PARTY_LINKS" in sql.upper()]
    assert len(mapping_selects) == 2 * size
    assert len(statements) == len(mapping_selects), "Discovery must only read mappings"
    assert result.candidates == ()
