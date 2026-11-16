import pytest
from innoforia_tally_connector.application.masters.transfer_fields import select_fields
from innoforia_tally_connector.domain.masters import PartyContent
from innoforia_tally_connector.integrations.bahi.party_payload import validate


def test_legacy_observations_do_not_invent_new_field_absence(observation):
    source = observation()
    draft, decisions = select_fields(source, type("Destination", (), {"validate": staticmethod(validate)})(), {})
    assert {d.field for d in decisions if d.status == "unavailable"} == {"country", "pan", "gst_reg_type"}
    assert "country" not in draft.model_fields_set


def test_each_exclusion_is_explicit_and_keeps_other_values_exact(observation):
    source = observation(content=PartyContent(name="Original  name", phone="00123", email=None, country="", pincode="012345"), content_schema=2)
    target = type("Destination", (), {"validate": staticmethod(validate)})()
    draft, decisions = select_fields(source, target, {"email": "No contact supplied"})
    assert draft.name == "Original  name" and draft.phone == "00123" and draft.pincode == "012345" and draft.country == ""
    assert "email" not in draft.model_fields_set
    assert next(d for d in decisions if d.field == "email").reason == "No contact supplied"
    for exclusions in ({"email": ""}, {"name": "omit"}, {"party_type": "omit"}, {"unknown": "omit"}):
        with pytest.raises(ValueError): select_fields(source, target, exclusions)
