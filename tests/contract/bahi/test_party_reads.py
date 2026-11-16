import httpx
import pytest

from innoforia_tally_connector.domain.errors import ContextMismatch, ReadError
from innoforia_tally_connector.integrations.bahi.client import Client
from innoforia_tally_connector.integrations.bahi.endpoints.parties import PartyReader


def party(identity=1, **changes):
    row = dict(account_id=identity, account_name=f"Synthetic {identity}", party_type="SUPPLIER", is_active=True)
    row.update(changes)
    return row


def client(handler):
    def guarded(request):
        assert request.method == "GET"
        assert "biz_id" not in request.url.params
        assert request.headers["Authorization"] == "Bearer synthetic-key"
        if request.url.path.endswith("check_api_biz_setup.php"):
            return httpx.Response(200, json={"success": True, "data": {"biz_id": 52, "biz_name": "Synthetic"}})
        return handler(request)
    return Client(lambda: "synthetic-key", httpx.Client(transport=httpx.MockTransport(guarded), follow_redirects=False))


def page(rows, number=1, total=None):
    total = len(rows) if total is None else total
    return {"success": True, "data": rows, "pagination": {"page": number, "limit": 200,
        "total": total, "total_pages": (total + 199) // 200}}


@pytest.fixture
def live_binding(binding):
    return binding.model_copy(update={"business_id": 52})


def test_paging_detail_and_string_values(live_binding):
    def response(request):
        if "id" in request.url.params:
            return httpx.Response(200, json={"success": True, "data": party(201, phone="0012", pincode="012345", email=None)})
        number = int(request.url.params["page"])
        rows = [party(n) for n in range(1, 201)] if number == 1 else [party(201, is_active=False)]
        return httpx.Response(200, json=page(rows, number, 201))
    api = client(response)
    try:
        reader = PartyReader(api)
        scan = reader.scan(live_binding)
        assert len(scan.records) == 201 and scan.coverage_complete and not scan.complete_baseline
        assert scan.records[-1].is_active is False
        detail = reader.detail(live_binding, "201")
        assert detail.content.phone == "0012" and detail.content.pincode == "012345"
        assert detail.content.email is None and "email" in detail.content.model_fields_set
        assert "gstin" not in detail.content.model_fields_set
    finally:
        api.close()


@pytest.mark.parametrize("mode", ["failed", "duplicate", "totals_changed", "malformed"])
def test_failed_later_page_keeps_prior_observations(mode, live_binding):
    def response(request):
        if request.url.params["page"] == "1":
            return httpx.Response(200, json=page([party(n) for n in range(1, 201)], 1, 201))
        if mode == "failed":
            return httpx.Response(503)
        if mode == "malformed":
            return httpx.Response(200, content=b"not-json")
        return httpx.Response(200, json=page([party(1 if mode == "duplicate" else 201)], 2,
                                             202 if mode == "totals_changed" else 201))
    api = client(response)
    try:
        scan = PartyReader(api).scan(live_binding)
        assert len(scan.records) == 200
        assert scan.pages_read == (1,) and scan.failed_pages == (2,)
        assert not scan.coverage_complete and scan.issues
    finally:
        api.close()


def test_page_cap_and_empty_list(live_binding):
    api = client(lambda request: httpx.Response(200, json=page([party(n) for n in range(1, 201)], 1, 201)))
    try:
        scan = PartyReader(api, max_pages=1).scan(live_binding)
        assert not scan.coverage_complete and scan.issues[0].code == "PAGE_LIMIT"
    finally:
        api.close()
    api = client(lambda request: httpx.Response(200, json=page([])))
    try:
        scan = PartyReader(api).scan(live_binding)
        assert scan.coverage_complete and scan.records == () and not scan.stable_snapshot
    finally:
        api.close()


@pytest.mark.parametrize("status", [301, 401, 403, 503])
def test_errors_never_follow_redirects(status, live_binding):
    api = client(lambda request: httpx.Response(status, headers={"Location": "https://example.com"}))
    try:
        with pytest.raises(ReadError):
            PartyReader(api).detail(live_binding, "1")
    finally:
        api.close()


def test_wrong_business_stops_before_party_request(binding):
    api = client(lambda request: pytest.fail("Party request must not run"))
    try:
        with pytest.raises(ContextMismatch):
            PartyReader(api).scan(binding)
    finally:
        api.close()


@pytest.mark.parametrize("route", ["check_api_biz_setup.php", "api-party.php"])
@pytest.mark.parametrize("mode,expected", [
    ("timeout", "timed out"), ("connect", "could not connect securely"),
    ("protocol", "transport failed"), ("json", "invalid JSON"),
    ("encoding", "invalid JSON"), ("http", "HTTP 503"),
])
def test_read_failures_identify_stage_without_leaking_remote_content(route, mode, expected):
    calls = []
    sensitive = "synthetic-secret-and-private-server-content"
    failing = True
    def handler(request):
        calls.append((request.method, request.url.path))
        assert request.method == "GET"
        if request.url.path.endswith(route) and failing:
            if mode == "timeout": raise httpx.ReadTimeout(sensitive, request=request)
            if mode == "connect": raise httpx.ConnectError(sensitive, request=request)
            if mode == "protocol": raise httpx.RemoteProtocolError(sensitive, request=request)
            if mode == "http": return httpx.Response(503, content=sensitive.encode())
            return httpx.Response(200, content=sensitive.encode() if mode == "json" else b'"\xff"')
        return httpx.Response(200, json={"success": True, "data": {"biz_id": 52, "biz_name": "Synthetic"}})
    api = Client(lambda: sensitive, httpx.Client(transport=httpx.MockTransport(handler)))
    try:
        with pytest.raises(ReadError) as caught:
            api.business()
            api.get("api-party.php", {"id": "123"})
        message = str(caught.value)
        assert route in message and expected in message
        assert sensitive not in message and "123" not in message
        # The explicit retry remains GET-only. No automatic retry is performed.
        assert len(calls) == (1 if route == "check_api_biz_setup.php" else 2)
        failing = False
        assert api.business()["biz_id"] == 52
        assert all(method == "GET" for method, _ in calls)
    finally:
        api.close()


def test_wrong_detail_identity(live_binding):
    api = client(lambda request: httpx.Response(200, json={"success": True, "data": party(2)}))
    try:
        with pytest.raises(ContextMismatch):
            PartyReader(api).detail(live_binding, "1")
    finally:
        api.close()


def test_credential_is_frozen_for_logical_scan(live_binding):
    credentials = iter(["first-key", "replaced-key"])
    headers = []
    def response(request):
        headers.append(request.headers["Authorization"])
        data = {"success": True, "data": {"biz_id": 52, "biz_name": "Synthetic"}}
        if request.url.path.endswith("api-party.php"):
            data = page([])
        return httpx.Response(200, json=data)
    api = Client(lambda: next(credentials), httpx.Client(transport=httpx.MockTransport(response)))
    try:
        assert PartyReader(api).scan(live_binding).coverage_complete
        assert headers == ["Bearer first-key", "Bearer first-key"]
    finally:
        api.close()


def test_oversized_response_is_rejected(live_binding):
    api = client(lambda request: httpx.Response(200, content=b" " * (8 * 1024 * 1024 + 1)))
    try:
        with pytest.raises(ReadError, match="limits"):
            PartyReader(api).detail(live_binding, "1")
    finally:
        api.close()


def test_invalid_detail_shape(live_binding):
    api = client(lambda request: httpx.Response(200, json={"success": True, "data": party(phone=123)}))
    try:
        with pytest.raises(ReadError):
            PartyReader(api).detail(live_binding, "1")
    finally:
        api.close()
