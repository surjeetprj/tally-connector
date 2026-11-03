"""Atomic single-attempt journal. No database transaction spans HTTP."""
from datetime import datetime, timezone
import json

from sqlalchemy import insert, select, update, literal_column
from sqlalchemy.exc import IntegrityError

from innoforia_tally_connector.domain.experiments import ExperimentPreview, ExperimentResult, TargetIdentity
from innoforia_tally_connector.domain.masters import PartyObservation
from innoforia_tally_connector.persistence.migrations.versions.v0002_discovery import operations
from innoforia_tally_connector.persistence.migrations.versions.v0003_experiments import experiments, attempts


class ExperimentStore:
    def __init__(self, engine):
        self.engine = engine

    def save_preview(self, preview):
        key = f"{preview.binding.id}:{preview.binding.generation}"
        try:
            with self.engine.begin() as connection:
                # Acquire the writer reservation before inspecting another active experiment.
                connection.execute(update(experiments).where(experiments.c.active_binding == key,
                    experiments.c.id.not_in(select(attempts.c.experiment_id))).values(
                    active_binding=None, state="BLOCKED", message="Superseded unattempted preview"))
                connection.execute(insert(experiments).values(id=preview.id, binding_id=preview.binding.id,
                    preview_json=preview.model_dump_json(), state="PENDING", active_binding=key))
        except IntegrityError:
            raise ValueError("An unresolved experiment blocks another creation; inspect its result") from None
        return self.get(preview.id, preview.binding)

    def get(self, identity, binding):
        with self.engine.connect() as connection:
            query = select(experiments).where(experiments.c.binding_id == binding.id)
            if identity:
                query = query.where(experiments.c.id == identity)
            else:
                query = query.order_by(literal_column("party_experiments.rowid").desc()).limit(1)
            row = connection.execute(query).mappings().one_or_none()
            if row is None:
                return None
            attempted = connection.execute(select(attempts.c.experiment_id).where(attempts.c.experiment_id == row["id"])).first() is not None
        preview = ExperimentPreview.model_validate_json(row["preview_json"])
        if preview.binding != binding:
            raise ValueError("Experiment binding generation differs")
        return ExperimentResult(preview=preview, state=row["state"], attempted=attempted,
            reviewer=row["reviewer"], message=row["message"] or "",
            target=TargetIdentity.model_validate_json(row["target_json"]) if row["target_json"] else None,
            comparisons=json.loads(row["comparisons_json"] or "{}"),
            observation=PartyObservation.model_validate_json(row["observation_json"]) if row["observation_json"] else None)

    def begin_attempt(self, preview, command, preflight):
        if command.kind != "EXP_CREATE" or command.experiment_id != preview.id or command.direction != preview.direction:
            raise ValueError("Creation command must identify the approved experiment and direction")
        now = datetime.now(timezone.utc)
        preview.require_current(command.binding, command.generation, command.approval_digest, now)
        if not command.reviewer or not command.reviewer.strip():
            raise ValueError("A named creation reviewer is required")
        if preflight.group_context != preview.preflight.group_context or preflight.destination != preview.preflight.destination:
            raise ValueError("Destination or group changed after preview; no creation sent")
        try:
            with self.engine.begin() as connection:
                connection.execute(insert(attempts).values(experiment_id=preview.id, operation_id=command.id,
                    started_at=now.isoformat(), payload_hash=preview.digest, preflight_json=preflight.model_dump_json()))
                preview.require_current(command.binding, command.generation, command.approval_digest, datetime.now(timezone.utc))
                changed = connection.execute(update(experiments).where(experiments.c.id == preview.id,
                    experiments.c.active_binding.is_not(None), experiments.c.state == "PENDING").values(
                    state="APPLYING", reviewer=command.reviewer, approved_at=now.isoformat(), approval_digest=preview.digest))
                if changed.rowcount != 1:
                    raise ValueError("Preview is no longer eligible; inspect the durable experiment")
                operation = connection.execute(update(operations).where(operations.c.id == command.id,
                    operations.c.state == "VALIDATING").values(state="APPLYING"))
                if operation.rowcount != 1:
                    raise ValueError("A claimed durable creation command is required")
        except IntegrityError:
            raise ValueError("This experiment already has a create attempt; only read-only reconciliation is allowed") from None

    def result(self, identity, operation_id, state, *, target=None, comparisons=None, message="", observation=None):
        values = dict(state=state, message=message)
        if target is not None:
            values["target_json"] = target.model_dump_json()
        if comparisons is not None:
            values["comparisons_json"] = json.dumps(comparisons, sort_keys=True)
        if observation is not None:
            values["observation_json"] = observation.model_dump_json(exclude_unset=True)
        if state in {"SUCCEEDED", "FAILED"}:
            values["active_binding"] = None
        with self.engine.begin() as connection:
            connection.execute(update(experiments).where(experiments.c.id == identity).values(**values))
            connection.execute(update(operations).where(operations.c.id == operation_id).values(state=state, coalesce_key=None))

    def recover(self):
        with self.engine.begin() as connection:
            connection.execute(update(experiments).where(experiments.c.state.in_(["APPLYING", "VERIFYING", "RECONCILING"])).values(
                state="OUTCOME_UNKNOWN", message="Interrupted create/verification; reconcile through reads only"))
            connection.execute(update(operations).where(operations.c.id.in_(select(attempts.c.operation_id)),
                operations.c.state.in_(["APPLYING", "VERIFYING", "RECONCILING", "VALIDATING", "PENDING"])).values(
                state="OUTCOME_UNKNOWN", coalesce_key=None, error="Interrupted write; read-only reconciliation required"))
