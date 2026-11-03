"""One user-approved synthetic supplier creation; reconciliation never creates."""
from datetime import datetime, timezone

from innoforia_tally_connector.domain.errors import ReadError
from innoforia_tally_connector.domain.experiments import new_preview, synthetic_supplier, UncertainWrite, WriteRejected


class SupplierExperimentWorkflow:
    def __init__(self, store, destinations, verify, stopped=lambda: False):
        self.store, self.destinations, self.verify, self.stopped = store, destinations, verify, stopped

    def handle(self, command, binding, classification):
        if command.kind == "EXP_STATUS":
            return self.store.get(command.experiment_id, binding)
        if command.kind == "EXP_PREPARE":
            if command.direction is None:
                raise ValueError("Select the experiment direction explicitly")
            snapshot = self.verify()
            if snapshot.business_id != binding.business_id or snapshot.company_guid != binding.company_guid:
                raise ValueError("Connection identity changed; no experiment prepared")
            destination = self.destinations(command.direction, classification)
            party = synthetic_supplier()
            preflight = destination.preflight(binding, party)
            return self.store.save_preview(new_preview(binding, command.generation, command.direction, party, preflight))
        record = self.store.get(command.experiment_id, binding)
        if record is None:
            raise ValueError("Prepare an experiment before creating or reconciling")
        preview = record.preview
        destination = self.destinations(preview.direction, classification)
        if command.kind == "EXP_RECONCILE":
            if not record.attempted:
                raise ValueError("No create was attempted; prepare a fresh preview")
            if record.target is None:
                return record  # No authoritative identity: never resolve by names or send again.
            return self._verify(command, record, destination)
        if command.kind != "EXP_CREATE":
            raise ValueError("Unsupported experiment action")
        if record.attempted:
            return record  # Duplicate delivery/click cannot issue a second create.
        preview.require_current(binding, command.generation, command.approval_digest, datetime.now(timezone.utc))
        if command.direction != preview.direction:
            raise ValueError("Selected direction changed; prepare a new preview")
        current = destination.preflight(binding, preview.party)
        if self.stopped():
            raise ReadError("Shutdown started; no create attempted")
        self.store.begin_attempt(preview, command, current)
        try:
            target = destination.create(preview, current)
        except WriteRejected as error:
            self.store.result(preview.id, command.id, "FAILED", message=str(error))
        except UncertainWrite as error:
            self.store.result(preview.id, command.id, "OUTCOME_UNKNOWN", target=error.target,
                              message=str(error))
        except Exception:
            self.store.result(preview.id, command.id, "OUTCOME_UNKNOWN",
                              message="Create may have started; do not create again. Reconcile through reads only.")
        else:
            # Persist returned identifiers/receipt before performing any further IO.
            self.store.result(preview.id, command.id, "VERIFYING", target=target,
                              message="Create receipt saved; verification pending")
            record = self.store.get(preview.id, binding)
            return self._verify(command, record, destination)
        return self.store.get(preview.id, binding)

    def _verify(self, command, record, destination):
        preview = record.preview
        self.store.result(preview.id, command.id, "RECONCILING", message="Reading the saved target identity")
        try:
            observed, target, group_matches = destination.read_back(preview, record.target)
            comparisons = {"name": observed.content.name == preview.party.name,
                "supplier_type": observed.party_type == "SUPPLIER", "email": observed.content.email == preview.party.email,
                "group_semantics": group_matches, "active": observed.is_active is not False}
        except Exception:
            self.store.result(preview.id, command.id, "VERIFYING",
                              message="Target verification is incomplete. Use read-only reconciliation; no new creation is allowed.")
        else:
            state = "SUCCEEDED" if all(comparisons.values()) else "BLOCKED"
            self.store.result(preview.id, command.id, state, target=target, comparisons=comparisons, observation=observed,
                message="One synthetic destination supplier verified; no cross-system mapping created" if state == "SUCCEEDED"
                else "Created target differs from approved fields; no correction or recreation is enabled")
        return self.store.get(preview.id, preview.binding)
