import json
import httpx
import pytest

from innoforia_tally_connector.domain.party_transfer import PartyDraft
from innoforia_tally_connector.domain.masters import PartyType
from innoforia_tally_connector.integrations.bahi.client import Client
from innoforia_tally_connector.integrations.bahi.party_payload import validate, payload


@pytest.mark.parametrize("kind", list(PartyType))
def test_actual_customer_supplier_payload_exact_and_readback(kind):
    draft = PartyDraft(name="Real source & name", party_type=kind, email="a@example.invalid", phone="001234",
        address="Line one\nLine two", state="State", country="India", pincode="012345",
        gstin="27ABCDE1234F1Z5", pan="ABCDE1234F", gst_reg_type="Regular")
    calls = []
    def handler(request):
        calls.append(request)
        assert "biz_id" not in request.url.params
        if request.method == "GET":
            return httpx.Response(200, json={"success": True, "data": {"biz_id": 52, "biz_name": "Synthetic"}})
        assert request.method == "POST" and request.url.path.endswith("api-party.php")
        assert json.loads(request.content) == {**draft.model_dump(exclude={"name"}, exclude_unset=True), "account_name": draft.name}
        assert set(json.loads(request.content)) == {"party_type", "account_name", "email", "phone", "address", "state", "country", "pincode", "gstin", "pan", "gst_reg_type"}
        return httpx.Response(201, json={"success": True, "data": {"account_id": 123}})
    api = Client(lambda: "synthetic", httpx.Client(transport=httpx.MockTransport(handler)))
    try:
        assert api.create_party(draft, lambda business: None).identity == "123"
        assert len(calls) == 2
    finally:
        api.close()


@pytest.mark.parametrize("field,value", [("name", "n"*129), ("phone", "1"*17), ("address", "x"*256),
    ("email", "bad"), ("pincode", "123"), ("pan", "bad"), ("gstin", "bad"), ("country", None), ("gst_reg_type", None)])
def test_invalid_values_cannot_enter_payload(field, value):
    values = dict(name="Party", party_type=PartyType.CUSTOMER)
    values[field] = value
    draft = PartyDraft(**values)
    assert field in validate(draft)
    with pytest.raises(ValueError): payload(draft)


def test_missing_null_and_empty_are_not_conflated():
    draft = PartyDraft(name="Party", party_type=PartyType.SUPPLIER, email=None, phone="", pincode="012345")
    body = payload(draft)
    assert body["email"] is None and body["phone"] == "" and body["pincode"] == "012345"
    assert "address" not in body and "country" not in body
    assert "gstin" in validate(PartyDraft(name="Party", party_type=PartyType.SUPPLIER, gstin="27ABCDE1234F1Z5"))
    lowercase = PartyDraft(name="Party", party_type=PartyType.SUPPLIER, gstin="27abcde1234f1z5", gst_reg_type="Regular", pan="abcde1234f")
    assert payload(lowercase)["gstin"] == "27abcde1234f1z5" and payload(lowercase)["pan"] == "abcde1234f"
