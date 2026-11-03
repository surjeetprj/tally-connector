import json

import httpx
import pytest

from innoforia_tally_connector.domain.experiments import synthetic_supplier, UncertainWrite, WriteRejected
from innoforia_tally_connector.integrations.bahi.client import Client


@pytest.mark.parametrize("mode", ["ok", "denied", "redirect", "malformed", "counter", "timeout", "id_error"])
def test_narrow_create_contract(mode):
    calls = []
    party = synthetic_supplier()
    def handler(request):
        calls.append(request)
        assert "biz_id" not in request.url.params
        if request.method == "GET":
            assert request.url.path.endswith("check_api_biz_setup.php")
            return httpx.Response(200, json={"success": True, "data": {"biz_id": 52, "biz_name": "Synthetic"}})
        assert request.method == "POST" and request.url.path.endswith("api-party.php")
        assert json.loads(request.content) == {"party_type": "SUPPLIER", "account_name": party.name, "email": party.email}
        if mode == "denied": return httpx.Response(403, json={"success": False})
        if mode == "redirect": return httpx.Response(302, headers={"Location": "https://example.invalid"})
        if mode == "malformed": return httpx.Response(201, content=b"invalid")
        if mode == "counter": return httpx.Response(201, json={"success": True, "data": {"created": 1}})
        if mode == "timeout": raise httpx.ReadTimeout("synthetic")
        return httpx.Response(201, json={"success": mode != "id_error", "data": {"account_id": 700}})
    api = Client(lambda: "synthetic", httpx.Client(transport=httpx.MockTransport(handler)))
    try:
        if mode == "ok":
            assert api.create_test_supplier(party).identity == "700"
        else:
            with pytest.raises(WriteRejected if mode == "denied" else UncertainWrite) as caught:
                api.create_test_supplier(party)
            if mode == "id_error": assert caught.value.target.identity == "700"
        assert [r.method for r in calls] == ["GET", "POST"]
    finally:
        api.close()


def test_final_guard_prevents_transmission():
    calls = []
    def handler(request):
        calls.append(request.method)
        return httpx.Response(200, json={"success": True, "data": {"biz_id": 52, "biz_name": "Synthetic"}})
    api = Client(lambda: "synthetic", httpx.Client(transport=httpx.MockTransport(handler)))
    try:
        def expired(business): raise ValueError("expired approval")
        with pytest.raises(ValueError): api.create_test_supplier(synthetic_supplier(), expired)
        assert calls == ["GET"]
    finally:
        api.close()
