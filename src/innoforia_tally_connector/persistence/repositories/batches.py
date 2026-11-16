"""Batch approvals and dispatch gaps share the existing SQLite operation outbox."""
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import insert, select, update, literal_column, case
from sqlalchemy.exc import IntegrityError
from innoforia_tally_connector.domain.batches import TransferBatch, TransferPolicy, BatchPage
from innoforia_tally_connector.domain.commands import Command
from innoforia_tally_connector.domain.party_transfer import source_key
from innoforia_tally_connector.persistence.migrations.versions.v0005_batches import batches, policies, members
from innoforia_tally_connector.persistence.migrations.versions.v0004_party_transfers import experiments
from innoforia_tally_connector.persistence.migrations.versions.v0003_experiments import attempts
from innoforia_tally_connector.persistence.migrations.versions.v0002_discovery import operations, outbox
from innoforia_tally_connector.persistence.repositories.experiments import ExperimentStore


def binding_key(binding):
    return f"{binding.id}:{binding.generation}"


class BatchStore:
    def __init__(self, engine):
        self.engine = engine
        self.records = ExperimentStore(engine)

    def policy(self, binding):
        with self.engine.connect() as c:
            return self._policy(c, binding)

    @staticmethod
    def _policy(c, binding):
        raw = c.execute(select(policies.c.evidence).where(policies.c.binding_key == binding_key(binding))
            .order_by(policies.c.version.desc()).limit(1)).scalar_one_or_none()
        policy = TransferPolicy.model_validate_json(raw) if raw else None
        if policy and policy.binding != binding:
            raise ValueError("Saved policy binding changed")
        return policy

    def save_policy(self, policy):
        with self.engine.begin() as c:
            # First statement obtains the SQLite writer before the version check.
            c.execute(update(batches).where(batches.c.binding_key == binding_key(policy.binding),
                batches.c.state == "PENDING").values(state="CANCELLED"))
            current = self._policy(c, policy.binding)
            if policy.version != (current.version if current else 1):
                raise ValueError("Policy changed; reload settings")
            saved = policy.model_copy(update={"version": current.version + 1 if current else 1})
            c.execute(insert(policies).values(binding_key=binding_key(saved.binding), version=saved.version,
                evidence=saved.model_dump_json()))
        return saved

    def save_draft(self, batch):
        with self.engine.begin() as c:
            c.execute(update(batches).where(batches.c.binding_key == binding_key(batch.binding),
                batches.c.state == "PENDING").values(state="CANCELLED"))
            self._supersede(c, batch.binding)
            if self._policy(c, batch.binding) != batch.policy:
                raise ValueError("Policy changed; prepare again")
            c.execute(insert(batches).values(id=batch.id, binding_key=binding_key(batch.binding),
                evidence=batch.model_dump_json(exclude_unset=True), state="PENDING"))
        return batch

    @staticmethod
    def _supersede(c, binding):
        c.execute(update(experiments).where(experiments.c.binding_id == binding.id,
            experiments.c.binding_generation == binding.generation, experiments.c.state == "PENDING",
            experiments.c.id.not_in(select(attempts.c.experiment_id)),
            experiments.c.id.not_in(select(members.c.child_id))).values(state="CANCELLED",
                active_binding=None, source_key=None, message="Unapproved draft superseded by batch preparation"))

    def get(self, identity, binding):
        with self.engine.connect() as c:
            row = c.execute(select(batches).where(batches.c.id == identity,
                batches.c.binding_key == binding_key(binding))).mappings().one_or_none()
        if not row:
            raise ValueError("Batch not found in this binding")
        batch = TransferBatch.model_validate_json(row["evidence"])
        if batch.binding != binding:
            raise ValueError("Batch binding changed")
        items = []
        for item in batch.items:
            result = self.records.get(item.preview.id, binding) if item.preview else None
            items.append(item.model_copy(update={"result": result, "status": result.state,
                "message": result.message}) if result else item)
        return batch.model_copy(update={"state": row["state"], "items": tuple(items)})

    def history(self, binding, offset=0):
        if offset < 0: raise ValueError("Invalid activity offset")
        with self.engine.connect() as c:
            ids = c.execute(select(batches.c.id).where(batches.c.binding_key == binding_key(binding))
                .order_by(literal_column("party_batches.rowid").desc()).offset(offset).limit(51)).scalars().all()
        return BatchPage(records=tuple(self.get(identity, binding) for identity in ids[:50]), offset=offset, has_more=len(ids) > 50)

    def approve(self, command):
        approval = command.approval
        if approval is None:
            raise ValueError("Batch approval required")
        try:
            with self.engine.begin() as c:
                changed = c.execute(update(batches).where(batches.c.id == approval.batch_id,
                    batches.c.binding_key == binding_key(command.binding), batches.c.state == "PENDING", batches.c.cancel_requested == 0)
                    .values(active_binding=binding_key(command.binding), state="APPLYING"))
                if changed.rowcount != 1:
                    raise ValueError("Batch already approved or changed; inspect its result")
                raw = c.execute(select(batches.c.evidence).where(batches.c.id == approval.batch_id)).scalar_one()
                batch = TransferBatch.model_validate_json(raw)
                ready = tuple(i.preview.id for i in batch.items if i.status == "Ready")
                if (batch.binding != command.binding or batch.generation != command.generation
                    or approval.digest != batch.digest or not ready or ready != approval.ready_ids
                    or self._policy(c, command.binding) != batch.policy):
                    raise ValueError("Batch summary or policy changed; prepare and review again")
                now = datetime.now(timezone.utc)
                for item in batch.items:
                    if item.status == "Ready":
                        item.preview.require_current(command.binding, command.generation, item.preview.digest, now)
                        if item.preview.source_confirmation_required and not approval.normal_confirmed:
                            raise ValueError("Confirm selected sources are normal non-system business parties")
                self._supersede(c, command.binding)
                if c.execute(select(experiments.c.id).where(experiments.c.active_binding == binding_key(command.binding))).first():
                    raise ValueError("An earlier attempted or unresolved operation needs reconciliation")
                for position, item in enumerate(batch.items):
                    if item.status != "Ready":
                        continue
                    preview = item.preview
                    c.execute(insert(experiments).values(id=preview.id, binding_id=batch.binding.id,
                        preview_json=preview.model_dump_json(exclude_unset=True), state="PENDING", active_binding=None,
                        source_key=source_key(batch.binding, item.source.side, item.source.identity), kind="TRANSFER",
                        created_at=preview.created_at.isoformat(), binding_generation=batch.binding.generation))
                    self.records._require_unlinked(c, preview)
                    c.execute(insert(members).values(child_id=preview.id, batch_id=batch.id, position=position))
                batch = batch.model_copy(update={"approved_ids": ready, "normal_confirmed": approval.normal_confirmed})
                c.execute(update(batches).where(batches.c.id == batch.id).values(evidence=batch.model_dump_json(exclude_unset=True)))
                self._enqueue(c, batch, ready[0])
        except IntegrityError:
            raise ValueError("Another batch or transfer reserves this binding/source; inspect Activity") from None
        return self.get(batch.id, batch.binding)

    @staticmethod
    def _enqueue(c, batch, child_id):
        command = Command(id=str(uuid4()), kind="BATCH_STEP", generation=batch.generation,
            binding=batch.binding, batch_id=batch.id, experiment_id=child_id)
        c.execute(insert(operations).values(id=command.id, command_json=command.model_dump_json(exclude_unset=True), state="PENDING"))
        c.execute(insert(outbox).values(operation_id=command.id))

    def activate(self, command):
        with self.engine.begin() as c:
            row = c.execute(update(batches).where(batches.c.id == command.batch_id,
                batches.c.binding_key == binding_key(command.binding), batches.c.state == "APPLYING",
                batches.c.cancel_requested == 0).values(state="APPLYING"))
            if row.rowcount != 1:
                return False
            batch = TransferBatch.model_validate_json(c.execute(select(batches.c.evidence)
                .where(batches.c.id == command.batch_id)).scalar_one())
            if command.experiment_id not in batch.approved_ids or batch.generation != command.generation:
                raise ValueError("Child is outside this approval")
            changed = c.execute(update(experiments).where(experiments.c.id == command.experiment_id,
                experiments.c.state == "PENDING", experiments.c.id.not_in(select(attempts.c.experiment_id)))
                .values(active_binding=binding_key(command.binding)))
            return changed.rowcount == 1

    def finish_step(self, command, pause=False):
        batch = self.get(command.batch_id, command.binding)
        if batch.state not in {"PENDING", "APPLYING"}:
            return
        with self.engine.begin() as c:
            cancelled = c.execute(select(batches.c.cancel_requested).where(batches.c.id == batch.id)).scalar_one()
            remaining = [i.preview.id for i in batch.items if i.preview and i.preview.id in batch.approved_ids
                         and i.result is not None and i.result.state == "PENDING"]
            if pause or cancelled:
                state = "CANCELLED" if cancelled and not pause else "BLOCKED"
            elif remaining:
                self._enqueue(c, batch, remaining[0])
                return
            else:
                state = "FAILED" if any(i.result and i.result.state == "FAILED" for i in batch.items) else "SUCCEEDED"
            # Retain attempted uncertainty; release only never-attempted children.
            c.execute(update(experiments).where(experiments.c.id.in_(batch.approved_ids),
                experiments.c.state == "PENDING", experiments.c.id.not_in(select(attempts.c.experiment_id)))
                .values(state="CANCELLED", active_binding=None, source_key=None,
                    message=case((experiments.c.message != "", experiments.c.message),
                        else_="Unsent batch work requires a new reviewed summary")))
            unresolved = c.execute(select(experiments.c.id).where(experiments.c.id.in_(batch.approved_ids),
                experiments.c.state.not_in(["SUCCEEDED", "FAILED", "CANCELLED"]))).first()
            c.execute(update(batches).where(batches.c.id == batch.id).values(state=state,
                active_binding=binding_key(batch.binding) if unresolved else None))

    def request_cancel(self, identity, binding):
        with self.engine.begin() as c:
            c.execute(update(batches).where(batches.c.id == identity, batches.c.binding_key == binding_key(binding),
                batches.c.state.in_(["PENDING", "APPLYING"])).values(cancel_requested=1))

    def cancel(self, identity, binding):
        self.request_cancel(identity, binding)
        self.finish_step(Command(id="cancel", kind="BATCH_CANCEL", generation=0, binding=binding, batch_id=identity))
        return self.get(identity, binding)

    def recover(self):
        with self.engine.connect() as c:
            raw = c.execute(select(batches.c.evidence).where(batches.c.state == "APPLYING")).scalars().all()
        for evidence in raw:
            batch = TransferBatch.model_validate_json(evidence)
            self.finish_step(Command(id="recovery", kind="BATCH_CANCEL", generation=0,
                binding=batch.binding, batch_id=batch.id), pause=True)

    def release_resolved(self, binding):
        with self.engine.connect() as c:
            ids = c.execute(select(batches.c.id).where(batches.c.binding_key == binding_key(binding), batches.c.active_binding.is_not(None))).scalars().all()
        for identity in ids:
            batch = self.get(identity, binding)
            if batch.state == "BLOCKED" and all(not i.result or i.result.state in {"SUCCEEDED", "FAILED", "CANCELLED"} for i in batch.items):
                with self.engine.begin() as c:
                    c.execute(update(batches).where(batches.c.id == batch.id).values(active_binding=None))
