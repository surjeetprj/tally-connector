"""Atomic unique links and confirmation evidence; never an equal-content ack."""
from sqlalchemy import insert, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from innoforia_tally_connector.domain.masters import Binding, ConfirmedPartyLink, LinkConflict, Side
from innoforia_tally_connector.persistence.migrations.versions.v0001_party_links import (
    bindings, link_audit, party_links,
)


class SqlPartyLinks:
    def __init__(self, engine: Engine):
        self.engine = engine

    def register_binding(self, binding: Binding) -> None:
        # An explicit verified binding is required; saving a link cannot invent one.
        with self.engine.begin() as connection:
            connection.execute(insert(bindings).values(**binding.model_dump()))

    def save(self, link: ConfirmedPartyLink) -> None:
        evidence = link.model_dump_json(exclude_unset=True)
        try:
            with self.engine.begin() as connection:
                # Acquire SQLite's writer reservation before reading. Two
                # deferred read transactions must not race to upgrade snapshots.
                connection.execute(insert(party_links).values(
                    id=link.id, binding_id=link.binding.id, generation=link.binding.generation,
                    bahi_id=link.bahi.identity, tally_guid=link.tally.identity, evidence_json=evidence,
                ))
                row = connection.execute(select(bindings).where(
                    bindings.c.id == link.binding.id,
                    bindings.c.generation == link.binding.generation,
                )).mappings().one_or_none()
                if row is None or Binding.model_validate(dict(row)) != link.binding:
                    raise ValueError("Unknown or mismatched binding generation")
                connection.execute(insert(link_audit).values(link_id=link.id, evidence_json=evidence))
        except IntegrityError as error:
            if getattr(error.orig, "sqlite_errorname", "") == "SQLITE_CONSTRAINT_FOREIGNKEY":
                raise ValueError("Unknown binding generation") from error
            raise LinkConflict("An identity is already linked; review existing confirmation") from error

    def find(self, binding: Binding, side: Side, identity: str) -> ConfirmedPartyLink | None:
        identity_column = party_links.c.bahi_id if side == Side.BAHI else party_links.c.tally_guid
        with self.engine.connect() as connection:
            row = connection.execute(select(party_links.c.evidence_json).where(
                party_links.c.binding_id == binding.id,
                party_links.c.generation == binding.generation,
                identity_column == identity,
            )).scalar_one_or_none()
        if row is None:
            return None
        link = ConfirmedPartyLink.model_validate_json(row)
        if link.binding != binding:
            raise ValueError("Binding identities changed; investigate")
        return link
