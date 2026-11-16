# Live Bahi read validation

## Runtime party reader update — 2 November 2026

The [runtime adapter probe](../../../scripts/phase0/probe_discovery_live.py)
rechecked business 52, traversed its unfiltered party list (one page, one party)
and matched the selected detail against its observation. The native application
also verified the authenticated business and displayed the live party. Only GETs
were sent; no invoice route or write scope was exercised. See
[sanitized adapter evidence](../../master-sync/evidence/live-discovery-reads.json)
and [the implemented desktop workflow](../../master-sync/READ_ONLY_DISCOVERY.md).
Multi-page failures/duplicates/limits are tested offline, not certified as a
stable live snapshot. The following sections retain the original read baseline.

29 October 2026, approximately 20:13 IST. CON-001 read evidence; no write or
posting permissions were exercised in that initial read-only run. Subsequent
[authorized posting/recovery evidence](CONTROLLED_POSTING.md) now verifies the
controlled test in the same business; the pending list below describes the
read-only baseline, not the latest task outcome. The authoritative backend source
is not available. The excluded local test implementation was not consulted.

## Environment and credential handling

Application base: `https://innoforia.com/201/h-bahi/bahi/`.
Verified API base: `https://innoforia.com/201/h-bahi/bahi/web-api/`.
The locally saved Windows Credential Manager key was used only in the
Authorization header. The probe never prints or saves the key, raw responses,
supplier/item names, addresses, tax identifiers, prices or financial totals.

The identity endpoint returned biz_id **52**, matching the expected dashboard
business. These requests do not independently establish that the business is
disposable or that accounting writes are authorized.

## Results

All nine GET requests returned HTTP 200 and `success=true`:

| Resource | Calls | Observed result |
| --- | --- | --- |
| Business check | 1 | Expected biz_id 52 matched |
| Suppliers | List + one detail | One supplier returned; account_id integer, is_active boolean |
| Item groups | List + one detail | One group returned; GST/cess represented as strings |
| Items | List + one detail | One item returned; prices, stock quantity and GST rate represented as strings |
| PURCHASE invoices | List + one detail | One purchase returned, explicit ACTIVE status, one detail item |

Lists reported one page and were fully traversed for this dataset. This verifies
the observed one-page pagination contract, not multi-page consistency during
concurrent edits. The purchase list contained headers; items appeared in detail.

**The historical missing-invoice_status issue was not reproduced:** both sampled
list and detail included the field and returned ACTIVE. This is evidence for the
sampled record/deployment only, not every transaction type or status.

Additional observations for schema implementation:

- `invoice_cust_id` was a decimal string in the response, while invoice_id/item_id
  were integers. Validate positive-ID representations explicitly; do not assume
  every identifier is encoded with the same JSON type.
- Some fields, including payment status, were null. Do not infer lifecycle from
  payment fields; use explicit invoice_status.
- Invoice detail contains tracking/pricing fields beyond the first slice. Their
  presence does not authorize sending them in create/update requests.
- Item responses expose avail_qty. Exclude it from master synchronization; stock
  effects belong to supported invoice posting workflows.
- No confirmed cross-system supplier/item/UOM mappings were created. Bahi and
  Tally data differ, as reported by the user.

## Reproduction and evidence

[Read-only probe](../../../scripts/phase0/probe_bahi.py):

```powershell
python scripts/phase0/probe_bahi.py
python -m unittest discover -s tests/phase0 -v
```

The probe reads the existing Credential Manager entry locally and checks biz_id
52 before requesting other resources. It follows no redirects, uses bounded
reads/timeouts/page counts, and performs GET requests only. It retains
[sanitized contract evidence](evidence/read-only-probes.json): endpoint/query,
timestamps, response hashes/sizes, field names/types, pagination, counts and
allowlisted lifecycle values. Record IDs used for detail requests are retained;
business payload values are not. Do not use these shapes as fabricated success
payloads or assume that a returned schema grants write capability.

## Still pending

On 3 November the actual-source customer/supplier feature generalized guarded
party creation with contact/mailing/PAN/GST payload validation, per-field exclusions
and atomic local mapping. Its automated evidence is mocked/offline only; this
update made no live requests. The earlier supplier-275 result below does not
certify the generalized fields or four transfer combinations. See
[feature limits](../../master-sync/PARTY_TRANSFER.md) and
[owner checks](../../master-sync/MANUAL_PARTY_TRANSFER_CHECKLIST.md).

The party handbook states that system flags are not exposed in responses. The
feature does not treat absence as is_system=False. The owner selected an explicit,
separate named-reviewer confirmation of normal non-system source status when
unavailable, retained with the API limitation in the operation and mapping audit.
This is owner evidence, not verified backend system-flag support.

Subsequent MST-004 evidence: the owner approved one exact synthetic SUPPLIER in
business 52. POST api-party.php accepted party_type/account_name/email with HTTP
201 and returned account ID 275. ID-based detail read-back matched enabled fields.
This verifies party:create for this credential/deployment/trial only; it does not
establish backend idempotency, external-reference lookup or mutation safety.
The server-configured supplier group's code/ID remains unavailable. See
[sanitized experiment evidence](../../master-sync/evidence/supplier-create-bahi.json)
and [workflow/remaining gates](../../master-sync/CONTROLLED_SUPPLIER_EXPERIMENT.md).

- Broader write permissions and master update/recovery capabilities; purchase
  posting evidence is documented separately in [controlled posting](CONTROLLED_POSTING.md).
- Numbering ownership and confirmed party/item/unit/tax/charge mappings.
- Server idempotency/external identity, expected versions, change feed/origin and
  cross-PC ownership contracts. No unprovided `/sync/*` endpoint was probed.
- UOM/general-ledger/Receipt/Payment API discovery through authoritative contracts.
- Production server crash/compensation guarantees and test-business write approval.

See [integration assessment](README.md),
[Phase 0 checklist](../../phase0/CONTRACT_VALIDATION.md) and
[current progress](../../STATE_AND_PROGRESS.md).
