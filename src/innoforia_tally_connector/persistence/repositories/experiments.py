"""Atomic single-attempt write journal. No database transaction spans HTTP."""
from datetime import datetime, timezone
import json

from sqlalchemy import insert, select, update, literal_column
from sqlalchemy.exc import IntegrityError

from innoforia_tally_connector.domain.experiments import ActivityPage, ExperimentPreview, ExperimentResult, TargetIdentity
from innoforia_tally_connector.domain.masters import PartyObservation, Side, ConfirmedPartyLink, LinkConflict
from innoforia_tally_connector.domain.party_transfer import source_key
from innoforia_tally_connector.domain.party_changes import StateAcknowledgement, AcknowledgedField, FieldValue
from innoforia_tally_connector.domain.party_transfer import field_availability
from innoforia_tally_connector.persistence.migrations.versions.v0002_discovery import operations
from innoforia_tally_connector.persistence.migrations.versions.v0003_experiments import attempts
from innoforia_tally_connector.persistence.migrations.versions.v0004_party_transfers import experiments
from innoforia_tally_connector.persistence.migrations.versions.v0001_party_links import party_links
from innoforia_tally_connector.persistence.repositories.party_links import SqlPartyLinks


class ExperimentStore:
    def __init__(self, engine):
        self.engine = engine

    def save_preview(self, preview, replaces=None):
        key = f"{preview.binding.id}:{preview.binding.generation}"
        try:
            with self.engine.begin() as connection:
                if connection.exec_driver_sql("PRAGMA user_version").scalar_one() >= 5:
                    from innoforia_tally_connector.persistence.migrations.versions.v0005_batches import batches
                    if connection.execute(select(batches.c.id).where(batches.c.active_binding == key)).first():
                        raise ValueError("An executing or unresolved batch reserves this binding; inspect Activity")
                if replaces:
                    previous = connection.execute(update(experiments).where(experiments.c.id == replaces,
                        experiments.c.binding_id == preview.binding.id, experiments.c.state == "PENDING",
                        experiments.c.source_key == source_key(preview.binding, preview.source.side, preview.source.identity),
                        experiments.c.id.not_in(select(attempts.c.experiment_id))).values(
                            state="CANCELLED", active_binding=None, source_key=None, message="Replaced by a newly reviewed field selection"))
                    if previous.rowcount != 1:
                        raise ValueError("Previous preview is no longer replaceable; inspect activity")
                # Acquire the writer reservation before inspecting another active experiment.
                if preview.kind == "EXPERIMENT":
                    connection.execute(update(experiments).where(experiments.c.active_binding == key,
                        experiments.c.kind == "EXPERIMENT", experiments.c.id.not_in(select(attempts.c.experiment_id))).values(
                        active_binding=None, state="BLOCKED", message="Superseded unattempted preview"))
                if preview.kind == "UPDATE":
                    connection.execute(update(experiments).where(experiments.c.active_binding == key,
                        experiments.c.kind == "UPDATE", experiments.c.state == "PENDING",
                        experiments.c.id.not_in(select(attempts.c.experiment_id))).values(state="CANCELLED",
                            active_binding=None, source_key=None, message="Superseded unattempted state preview; renewed approval required"))
                connection.execute(insert(experiments).values(id=preview.id, binding_id=preview.binding.id,
                    preview_json=preview.model_dump_json(exclude_unset=True), state="PENDING", active_binding=key,
                    source_key=source_key(preview.binding, preview.source.side, preview.source.identity) if preview.source else None,
                    kind=preview.kind, created_at=preview.created_at.isoformat(), binding_generation=preview.binding.generation))
                if preview.kind == "UPDATE":
                    connection.execute(update(experiments).where(experiments.c.id == preview.id).values(
                        target_json=TargetIdentity(kind="TALLY_GUID" if preview.direction == "BAHI_TO_TALLY" else "BAHI_ID", identity=preview.update.before.identity).model_dump_json()))
                if preview.source:
                    self._require_unlinked(connection, preview)
        except IntegrityError:
            raise ValueError("An active or unresolved operation blocks another preview; inspect activity and cancel unattempted work") from None
        return self.get(preview.id, preview.binding)

    def get(self, identity, binding):
        with self.engine.connect() as connection:
            query = select(experiments).where(experiments.c.binding_id == binding.id,
                                               experiments.c.binding_generation == binding.generation)
            if identity:
                query = query.where(experiments.c.id == identity)
            else:
                query = query.order_by(literal_column("party_experiments.rowid").desc()).limit(1)
            row = connection.execute(query).mappings().one_or_none()
            if row is None:
                return None
            attempted = connection.execute(select(attempts.c.experiment_id).where(attempts.c.experiment_id == row["id"])).first() is not None
            native_after = None
            if row["kind"] == "UPDATE":
                from innoforia_tally_connector.persistence.migrations.versions.v0006_state_update_audit import verifications
                evidence = connection.execute(select(verifications.c.evidence_json).where(verifications.c.experiment_id == row["id"])
                    .order_by(literal_column("party_state_update_verifications.rowid").desc()).limit(1)).scalar_one_or_none()
                if evidence: native_after = json.loads(evidence)["native_after"]
        preview = ExperimentPreview.model_validate_json(row["preview_json"])
        if preview.binding != binding:
            raise ValueError("Experiment binding generation differs")
        return ExperimentResult(preview=preview, state=row["state"], attempted=attempted, native_after=native_after,
            source_normal_party_confirmed=bool(row["source_normal_party_confirmed"]),
            reviewer=row["reviewer"], message=row["message"] or "",
            target=TargetIdentity.model_validate_json(row["target_json"]) if row["target_json"] else None,
            comparisons=json.loads(row["comparisons_json"] or "{}"),
            observation=PartyObservation.model_validate_json(row["observation_json"]) if row["observation_json"] else None)

    def latest_update(self, binding, source_identity=None, direction=None):
        with self.engine.connect() as connection:
            query = select(experiments.c.id, experiments.c.preview_json).where(experiments.c.binding_id == binding.id,
                experiments.c.binding_generation == binding.generation, experiments.c.kind == "UPDATE").order_by(
                    literal_column("party_experiments.rowid").desc())
            if source_identity is None:
                row = next((r for r in connection.execute(query) if direction is None or ExperimentPreview.model_validate_json(r.preview_json).direction == direction), None)
            else:
                row = next((r for r in connection.execute(query) if
                    ExperimentPreview.model_validate_json(r.preview_json).source.identity == source_identity
                    and (direction is None or ExperimentPreview.model_validate_json(r.preview_json).direction == direction)), None)
            identity = row.id if row else None
        return self.get(identity, binding) if identity else None

    @staticmethod
    def _state_acknowledgement(connection, link):
        from innoforia_tally_connector.persistence.migrations.versions.v0007_repeatable_state_updates import audit
        rows = connection.execute(select(audit.c.operation_id, audit.c.evidence_json).where(audit.c.link_id == link.id)
            .order_by(literal_column("party_state_update_audit.rowid"))).all()
        if not rows: return None
        baselines = {}
        for row in rows:
            evidence = json.loads(row.evidence_json)
            source = PartyObservation.model_validate_json(json.dumps(evidence['source_after']))
            target = PartyObservation.model_validate_json(json.dumps(evidence['target_after']))
            fields = evidence.get('preview', {}).get('update', {}).get('fields', ('state',))
            for field in fields:
                def value(obs):
                    availability = field_availability(obs, field)
                    return FieldValue(availability=availability, value=getattr(obs.content,field)
                        if availability in {'present','empty','null'} else None)
                baselines[field] = AcknowledgedField(operation_id=row.operation_id, source=value(source), destination=value(target))
        return StateAcknowledgement(operation_id=rows[-1].operation_id, link_id=link.id,
            bahi=source if source.side == Side.BAHI else target, tally=target if target.side == Side.TALLY else source, field_baselines=baselines)

    def state_acknowledgement(self, link):
        with self.engine.connect() as connection:
            return self._state_acknowledgement(connection, link)

    def begin_attempt(self, preview, command, preflight):
        expected_kind = "UPDATE_APPLY" if preview.kind == "UPDATE" else "TRANSFER_CREATE" if preview.kind == "TRANSFER" else "EXP_CREATE"
        if command.kind != expected_kind or command.experiment_id != preview.id or command.direction != preview.direction:
            raise ValueError("Write command must identify the approved operation and direction")
        now = datetime.now(timezone.utc)
        preview.require_current(command.binding, command.generation, command.approval_digest, now)
        if not command.reviewer or not command.reviewer.strip():
            raise ValueError("A named write reviewer is required")
        if preview.kind in {"TRANSFER", "UPDATE"} and preview.source_confirmation_required and not command.source_normal_party_confirmed:
            raise ValueError("Reviewer must explicitly confirm a normal non-system source; the system flag is unavailable")
        if preflight.group_context != preview.preflight.group_context or preflight.destination != preview.preflight.destination:
            raise ValueError("Destination or group changed after preview; no creation sent")
        try:
            with self.engine.begin() as connection:
                if connection.exec_driver_sql("PRAGMA user_version").scalar_one() >= 5:
                    from innoforia_tally_connector.persistence.migrations.versions.v0005_batches import batches, members
                    active = connection.execute(select(batches.c.id).where(batches.c.active_binding == f"{preview.binding.id}:{preview.binding.generation}")).scalar_one_or_none()
                    if active and not connection.execute(select(members.c.child_id).where(members.c.child_id == preview.id, members.c.batch_id == active)).first():
                        raise ValueError("Another batch reserves this binding")
                connection.execute(insert(attempts).values(experiment_id=preview.id, operation_id=command.id,
                    started_at=now.isoformat(), payload_hash=preview.digest, preflight_json=preflight.model_dump_json()))
                preview.require_current(command.binding, command.generation, command.approval_digest, datetime.now(timezone.utc))
                changed = connection.execute(update(experiments).where(experiments.c.id == preview.id,
                    experiments.c.active_binding.is_not(None), experiments.c.state == "PENDING").values(
                    state="APPLYING", reviewer=command.reviewer, approved_at=now.isoformat(), approval_digest=preview.digest,
                    source_normal_party_confirmed=int(command.source_normal_party_confirmed)))
                if changed.rowcount != 1:
                    raise ValueError("Preview is no longer eligible; inspect the durable experiment")
                if preview.source:
                    self._require_unlinked(connection, preview)
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
            values["source_key"] = None
        with self.engine.begin() as connection:
            connection.execute(update(experiments).where(experiments.c.id == identity).values(**values))
            connection.execute(update(operations).where(operations.c.id == operation_id).values(state=state, coalesce_key=None))

    @staticmethod
    def _require_unlinked(connection, preview):
        if preview.kind == "UPDATE":
            raw = connection.execute(select(party_links.c.evidence_json).where(party_links.c.id == preview.update.link.id,
                party_links.c.binding_id == preview.binding.id, party_links.c.generation == preview.binding.generation)).scalar_one_or_none()
            if raw is None or ConfirmedPartyLink.model_validate_json(raw) != preview.update.link:
                raise LinkConflict("Confirmed link changed; no state update allowed")
            ack = ExperimentStore._state_acknowledgement(connection, preview.update.link)
            if (ack.operation_id if ack else None) != preview.update.acknowledged_operation_id:
                raise LinkConflict("The verified field baseline changed; refresh and approve a new preview")
            return
        column = party_links.c.bahi_id if preview.source.side == Side.BAHI else party_links.c.tally_guid
        if connection.execute(select(party_links.c.id).where(party_links.c.binding_id == preview.binding.id,
            party_links.c.generation == preview.binding.generation, column == preview.source.identity)).first():
            raise LinkConflict("Source is already linked; inspect saved-link details")

    def complete_state_update(self, record, command, source, destination, native_after, comparisons):
        from innoforia_tally_connector.persistence.migrations.versions.v0007_repeatable_state_updates import audit
        preview = record.preview
        if preview.kind != "UPDATE" or not comparisons or not all(comparisons.values()):
            raise ValueError("A verified state update is required")
        with self.engine.begin() as connection:
            changed = connection.execute(update(experiments).where(experiments.c.id == preview.id,
                experiments.c.source_key == source_key(preview.binding, source.side, source.identity)).values(state="RECONCILING"))
            if changed.rowcount != 1: raise ValueError("Update reservation is no longer held")
            self._require_unlinked(connection, preview)
            evidence = dict(preview=preview.model_dump(mode="json"), source_after=source.model_dump(mode="json"),
                target_after=destination.model_dump(mode="json"), native_after=native_after, comparisons=comparisons,
                reviewer=record.reviewer, normal_confirmed=record.source_normal_party_confirmed,
                completed_at=datetime.now(timezone.utc).isoformat())
            connection.execute(insert(audit).values(operation_id=preview.id, link_id=preview.update.link.id,
                evidence_json=json.dumps(evidence, ensure_ascii=False)))
            connection.execute(update(experiments).where(experiments.c.id == preview.id).values(state="SUCCEEDED",
                active_binding=None, source_key=None, comparisons_json=json.dumps(comparisons),
                observation_json=destination.model_dump_json(exclude_unset=True),
                message="Party fields verified; original link/audit preserved, selected field baselines and evidence saved"))
            connection.execute(update(operations).where(operations.c.id == command.id).values(state="SUCCEEDED", coalesce_key=None))
        return self.get(preview.id, preview.binding)

    def record_state_verification(self, record, command, destination, native_after, comparisons):
        from innoforia_tally_connector.persistence.migrations.versions.v0006_state_update_audit import verifications
        with self.engine.begin() as c:
            c.execute(insert(verifications).values(request_id=command.id, experiment_id=record.preview.id,
                evidence_json=json.dumps(dict(native_after=native_after,
                    observation=destination.model_dump(mode="json"), comparisons=comparisons,
                    observed_at=datetime.now(timezone.utc).isoformat()), ensure_ascii=False)))

    def close_unchanged_state_failure(self, record, command, destination, native_after):
        from innoforia_tally_connector.persistence.migrations.versions.v0006_state_update_audit import verifications
        p = record.preview
        with self.engine.begin() as c:
            changed = c.execute(update(experiments).where(experiments.c.id == p.id,
                experiments.c.state == 'BLOCKED', experiments.c.active_binding == f'{p.binding.id}:{p.binding.generation}',
                experiments.c.id.in_(select(attempts.c.experiment_id))).values(state='FAILED', active_binding=None,
                    source_key=None, message='Operator closed unchanged empty-mailing failure after fresh reads; original attempt retained, never resend it. A new dated preview requires new approval.'))
            if changed.rowcount != 1: raise ValueError('Failed update is no longer eligible for local closure')
            c.execute(insert(verifications).values(request_id=command.id, experiment_id=p.id,
                evidence_json=json.dumps(dict(native_after=native_after, observation=destination.model_dump(mode='json'),
                    comparisons=record.comparisons, closed_by=command.reviewer, acknowledgement='Normal parties and no competing editor; close unchanged failure without resending',
                    observed_at=datetime.now(timezone.utc).isoformat()), ensure_ascii=False)))
            c.execute(update(operations).where(operations.c.id == command.id).values(state='SUCCEEDED', coalesce_key=None))
        return self.get(p.id, p.binding)

    def complete_transfer(self, record, command, source, destination, comparisons, target):
        preview = record.preview
        a, b = (source, destination) if source.side == Side.BAHI else (destination, source)
        link = ConfirmedPartyLink(id=preview.id, binding=preview.binding, bahi=a, tally=b,
            confirmed_by=record.reviewer, confirmed_at=datetime.now(timezone.utc), review_reference=preview.id,
            transfer_fields=tuple(d.field for d in preview.decisions if d.status == "included"),
            transfer_exclusions={d.field: d.reason for d in preview.decisions if d.status == "excluded"},
            source_eligibility_evidence=("Named reviewer confirmed normal non-system source; source system flag unavailable from API"
                if preview.source_confirmation_required and record.source_normal_party_confirmed else "Source reader reported is_system=False"))
        with self.engine.begin() as connection:
            changed = connection.execute(update(experiments).where(experiments.c.id == preview.id,
                experiments.c.source_key == source_key(preview.binding, source.side, source.identity)).values(state="RECONCILING"))
            if changed.rowcount != 1:
                raise ValueError("Transfer reservation is no longer held")
            SqlPartyLinks.save_in_connection(connection, link, reservation_id=preview.id)
            connection.execute(update(experiments).where(experiments.c.id == preview.id).values(state="SUCCEEDED",
                active_binding=None, source_key=None, target_json=target.model_dump_json(),
                comparisons_json=json.dumps(comparisons, sort_keys=True), observation_json=destination.model_dump_json(exclude_unset=True),
                message="Transferred and linked; exclusions are recorded, no whole-record equality is claimed"))
            connection.execute(update(operations).where(operations.c.id == command.id).values(state="SUCCEEDED", coalesce_key=None))
        return self.get(preview.id, preview.binding)

    def cancel(self, identity, binding):
        if identity is None or self.get(identity, binding) is None:
            raise ValueError("Select a pending preview in the current binding generation")
        with self.engine.begin() as connection:
            changed = connection.execute(update(experiments).where(experiments.c.id == identity,
                experiments.c.binding_id == binding.id, experiments.c.binding_generation == binding.generation,
                experiments.c.state == "PENDING",
                experiments.c.id.not_in(select(attempts.c.experiment_id))).values(
                    state="CANCELLED", active_binding=None, source_key=None, message="Cancelled without a create attempt"))
            if changed.rowcount != 1:
                raise ValueError("Only an unattempted pending preview can be cancelled")
        return self.get(identity, binding)

    def history(self, binding, offset=0, status=None, kind=None):
        if offset < 0 or kind not in (None, "TRANSFER", "EXPERIMENT", "UPDATE"):
            raise ValueError("Invalid activity filters")
        with self.engine.connect() as connection:
            query = select(experiments.c.id).where(experiments.c.binding_id == binding.id,
                                                   experiments.c.binding_generation == binding.generation)
            if status:
                query = query.where(experiments.c.state == status)
            if kind:
                query = query.where(experiments.c.kind == kind)
            identities = connection.execute(query.order_by(experiments.c.created_at.desc(), experiments.c.id.desc())
                                            .offset(offset).limit(51)).scalars().all()
        return ActivityPage(records=tuple(self.get(identity, binding) for identity in identities[:50]),
                            offset=offset, has_more=len(identities) > 50)

    def recover(self):
        with self.engine.begin() as connection:
            connection.execute(update(experiments).where(experiments.c.state.in_(["APPLYING", "VERIFYING", "RECONCILING"])).values(
                state="OUTCOME_UNKNOWN", message="Interrupted create/verification; reconcile through reads only"))
            connection.execute(update(operations).where(operations.c.id.in_(select(attempts.c.operation_id)),
                operations.c.state.in_(["APPLYING", "VERIFYING", "RECONCILING", "VALIDATING", "PENDING"])).values(
                state="OUTCOME_UNKNOWN", coalesce_key=None, error="Interrupted write; read-only reconciliation required"))

    def reconciliation_candidates(self, binding):
        with self.engine.connect() as connection:
            ids = connection.execute(select(experiments.c.id).where(experiments.c.binding_id == binding.id,
                experiments.c.binding_generation == binding.generation, experiments.c.target_json.is_not(None),
                experiments.c.id.in_(select(attempts.c.experiment_id)),
                experiments.c.state.not_in(["SUCCEEDED", "FAILED", "CANCELLED"]))
                .order_by(literal_column("party_experiments.rowid")).limit(20)).scalars().all()
        return tuple(self.get(identity, binding) for identity in ids)
