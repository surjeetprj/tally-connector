"""Saved context reopens only after fresh identity and ancestry verification."""
from types import SimpleNamespace
from uuid import uuid4
import pytest
from innoforia_tally_connector.application.masters.discovery import DiscoveryWorkflow, Verified, Bound
from innoforia_tally_connector.domain.commands import Command
from innoforia_tally_connector.domain.masters import Classification, ConnectionSnapshot, GroupObservation


@pytest.mark.parametrize("change", [None, "business", "company", "name", "group", "ancestor"])
def test_restore_verifies_saved_context(store, binding, change):
    from innoforia_tally_connector.persistence.repositories.discovery import DiscoveryStore
    journal = DiscoveryStore(store.engine)
    groups = (GroupObservation(identity="a", name="Customers", parent="Parent", version="1"),
        GroupObservation(identity="b", name="Suppliers", parent="Primary", version="1"),
        GroupObservation(identity="p", name="Parent", parent="Primary", version="1"))
    snapshot = ConnectionSnapshot(business_id=binding.business_id, business_name="Saved business",
        company_guid=binding.company_guid, company_name="Saved company", groups=groups)
    classification = Classification(customer_root="a", supplier_root="b")
    journal.bind(binding, classification, snapshot, "credential-reference-only")
    changes = {}
    if change == "business": changes["business_id"] = binding.business_id + 1
    if change == "company": changes["company_guid"] = "other"
    if change == "name": changes["business_name"] = "Renamed"
    if change in {"group", "ancestor"}:
        index = 0 if change == "group" else 2
        changed = list(groups)
        changed[index] = changed[index].model_copy(update={"parent": "Changed parent"})
        changes["groups"] = tuple(changed)
    workflow = DiscoveryWorkflow(lambda: snapshot.model_copy(update=changes), None, lambda *_: None,
        journal, store, "credential-reference-only")
    command = Command(id=str(uuid4()), kind="RESTORE", generation=10)
    if change:
        with pytest.raises(ValueError): workflow.handle(command)
        assert workflow.active is None
    else:
        restored = workflow.handle(command)
        assert isinstance(restored, Bound) and restored.binding == binding
        assert workflow.active == (binding, classification, 10)


def test_first_start_returns_setup_without_creating_binding(store, binding):
    from innoforia_tally_connector.persistence.repositories.discovery import DiscoveryStore
    workflow = DiscoveryWorkflow(lambda: "verified snapshot", None, None, DiscoveryStore(store.engine), store, "ref")
    assert isinstance(workflow.handle(Command(id="first", kind="RESTORE", generation=1)), Verified)
    assert workflow.active is None
