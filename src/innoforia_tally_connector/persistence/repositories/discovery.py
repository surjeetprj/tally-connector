"""Bounded command capture/claim/outbox and explicitly confirmed setup."""
from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError

from innoforia_tally_connector.domain.commands import Command
from innoforia_tally_connector.domain.masters import Binding, Classification, ConnectionSnapshot
from innoforia_tally_connector.persistence.migrations.versions.v0001_party_links import bindings
from innoforia_tally_connector.persistence.migrations.versions.v0002_discovery import operations, outbox, settings


class DiscoveryStore:
    def __init__(self, engine):
        self.engine = engine

    def capture(self, command):
        key = None if command.kind == "LINK" else f"{command.generation}:{command.kind}"
        try:
            with self.engine.begin() as connection:
                connection.execute(insert(operations).values(id=command.id, command_json=command.model_dump_json(exclude_unset=True),
                                                             coalesce_key=key, state="PENDING"))
                connection.execute(insert(outbox).values(operation_id=command.id))
            return command.id
        except IntegrityError:
            with self.engine.connect() as connection:
                row = connection.execute(select(operations.c.id).where(operations.c.coalesce_key == key)).scalar_one_or_none()
            if row:
                with self.engine.begin() as connection:
                    connection.execute(insert(outbox).prefix_with("OR IGNORE").values(operation_id=row))
                return row
            raise

    def pending(self):
        with self.engine.connect() as connection:
            return list(connection.execute(select(outbox.c.operation_id)).scalars())

    def dispatched(self, identity):
        with self.engine.begin() as connection:
            connection.execute(delete(outbox).where(outbox.c.operation_id == identity))

    def claim(self, identity):
        with self.engine.begin() as connection:
            claimed = connection.execute(update(operations).where(operations.c.id == identity, operations.c.state == "PENDING")
                                          .values(state="VALIDATING"))
            if claimed.rowcount != 1:
                return None
            return Command.model_validate_json(connection.execute(select(operations.c.command_json)
                                                                   .where(operations.c.id == identity)).scalar_one())

    def finish(self, identity, error=None):
        with self.engine.begin() as connection:
            connection.execute(update(operations).where(operations.c.id == identity).values(
                state="BLOCKED" if error else "SUCCEEDED", error=error, coalesce_key=None))

    def recover(self, links):
        with self.engine.connect() as connection:
            rows = connection.execute(select(operations).where(operations.c.state.in_(["PENDING", "VALIDATING"]))).mappings().all()
        for row in rows:
            command = Command.model_validate_json(row["command_json"])
            if command.kind in {"LINK", "BIND"}:
                applied = command.kind == "LINK" and links.by_id(command.id) is not None
                self.finish(command.id, None if applied else "Interrupted confirmation requires renewed review")
                self.dispatched(command.id)
            else:
                with self.engine.begin() as connection:
                    connection.execute(update(operations).where(operations.c.id == command.id).values(state="PENDING"))
                    connection.execute(insert(outbox).prefix_with("OR IGNORE").values(operation_id=command.id))

    def setup(self):
        with self.engine.connect() as connection:
            row = connection.execute(select(settings).where(settings.c.id == 1)).mappings().one_or_none()
        if not row:
            return None
        return (Binding.model_validate_json(row["binding_json"]),
                Classification.model_validate_json(row["classification_json"]),
                ConnectionSnapshot.model_validate_json(row["connection_json"]))

    def bind(self, binding, classification, snapshot, credential_reference):
        existing = self.setup()
        if existing and (existing[0] != binding or existing[1] != classification):
            raise ValueError("Changing the confirmed binding/group policy requires a separate reviewed migration")
        with self.engine.begin() as connection:
            # Idempotent reopening is allowed; links never invent a binding.
            connection.execute(insert(bindings).prefix_with("OR IGNORE").values(**binding.model_dump()))
            stored = connection.execute(select(bindings).where(bindings.c.id == binding.id,
                                                                bindings.c.generation == binding.generation)).mappings().one()
            if Binding.model_validate(dict(stored)) != binding:
                raise ValueError("Existing binding identity differs")
            connection.execute(delete(settings).where(settings.c.id == 1))
            connection.execute(insert(settings).values(id=1, binding_json=binding.model_dump_json(),
                classification_json=classification.model_dump_json(), connection_json=snapshot.model_dump_json(),
                credential_reference=credential_reference))
