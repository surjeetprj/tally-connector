# Phase 0: purchase contract and capability checklist

29 October 2026. CON-001 analysis draft with live Bahi read evidence;
accounting/product sign-off and broader write validation remain pending.
Subsequent controlled posting and packaged-runtime results are linked below. This is an evidence/gap checklist, not an implemented
API or authorization to change live accounting records.

## Scope under evaluation

First transfer: ordinary untracked PURCHASE, initially with existing confirmed
supplier, item and UOM mappings. Support both directions as separate operations:

- Tally -> canonical purchase -> Bahi DRAFT -> compare -> separately authorized
  Bahi posting -> confirmed ACTIVE result.
- Bahi ACTIVE purchase -> canonical purchase -> Tally preflight/import -> target
  read-back -> confirmed mapping and result.

Start with tax-exclusive, representable two-decimal prices/money, three-decimal
quantities, explicit GST, fixed mapped charges and header round-off. Unsupported
tracking, cess, currencies, precision and tax-state combinations block transfer.
Master creation, Sales/Notes and Receipt/Payment are later milestones. No source
record is overwritten merely because a mapping exists.

## Evidence levels

- **Documented:** supplied handbook specifies behavior; not deployment proof.
- **Source reviewed:** existing BahiAI-Desktop code/test definitions inspected;
  tests were not rerun in this task.
- **Live read:** a read-only Bahi/Tally request ran and its sanitized result is saved.
- **Pending:** no supporting test has been executed for the required guarantee.

## Capability checklist

| Capability | Current evidence | Next acceptance check | Responsible role |
| --- | --- | --- | --- |
| Bahi authentication/business identity | Live business check returned expected biz_id 52 | Verify test-business write permission; endpoint-specific read scopes worked | Bahi API + connector |
| Supplier/item/group reads | Live one-page lists/details returned one supplier/group/item each | Confirm selected mappings; test larger datasets and inactive semantics | Connector |
| Existing UOM mapping | Item API requires business-specific existing code, max 8 characters | Obtain authoritative lookup/configuration; verify each selected unit | Bahi API + accounting |
| Purchase create/update | Live purchase list/detail returned explicit ACTIVE and one detail item; DRAFT writes documented only | Verify controlled DRAFT create/update and canonical amount comparison | Bahi API + connector |
| Separate posting | Documented path-ID `/post`, repeated known-ID post; desktop reference | Confirm DRAFT -> ACTIVE, permissions and matching stock/journal behavior in test data | Bahi API + accounting |
| Duplicate/uncertain create | Supplier/reference/date purchase check documented; desktop attempt/reconciliation pattern | Add authoritative external identity/idempotency lookup; no blind retry after timeout | Bahi API + connector |
| Tally connection/company | Live read on 6.2; SIS Dummy GUID and company number returned | Verify identity on each workflow; later test mismatch/rename/restore | Connector |
| Tally master/voucher identities | Live read: Unit/Ledger/StockItem/Voucher GUID and AlterID fields populated | Verify per-entity detail lookup and required payload fields | Connector |
| Tally incremental query | Live empty-above-max and populated max-minus-one filters passed for four entity types | Prove create/edit capture, ties, date scope and bounded paging | Connector |
| Tally import and read-back | Desktop implementation reference only for this connector | Controlled creates and read-back, then ambiguous-write reconciliation | Connector + accounting |
| Backend change capture | Not documented by supplied CRUD contracts | Agree feed/snapshot/cursor and write-event atomicity | Bahi API |
| Conflict/origin/ownership | Not documented by supplied CRUD contracts | Conditional versions, origin/ack semantics and exclusive writer registration | Bahi API + connector |
| Qt/Huey/frozen build | Source and fresh frozen Qt/Huey spike passed after ICU search-path fix | Test clean Windows, in-flight lifecycle and production gateway | Connector |

Roles are proposed responsibilities, not named assignees or completed sign-offs.

## Purchase field matrix

| Business value | Bahi contract | Tally validation required |
| --- | --- | --- |
| Business/company | Key-derived biz_id; never a client-selected write field | Exact stable company binding; name remains an XML/display snapshot |
| Entity identity | Returned invoice_id; no documented external-ID create field | GUID/master ID lookup and source identity semantics per entity |
| Voucher date | Explicit invoice_dt | Extract source date; determine permitted educational-mode test dates |
| Internal number | invoice_num; server numbering if omitted | Preserve source/destination numbers separately; agree numbering ownership |
| Supplier reference | ref_doc_no + ref_doc_date; documented 16-character limit | Extract actual reference/date; block truncation and missing essential values |
| Supplier | invoice_cust_id referencing an active supplier | Confirm party ledger -> account_id mapping |
| Item/unit | Active item_id and authoritative master UOM | Confirm stock item -> item_id and exact unit mapping; no inferred conversions |
| Quantity/price | Positive quantity, up to 3 decimal places; price up to 2 | Confirm Tally values fit bounds and preserve economics |
| Discount | NONE, per-unit AMT or PCT | Convert only when exactly representable under validated tolerance |
| GST/HSN | Explicit snapshots; business/bill-to-state GST mode | Validate rates/component rounding and compatible source tax treatment |
| Charges | Real SERVICE/CHARGE items | Explicit mappings and exact amounts; no artificial inventory rows |
| Round-off | Signed header round_off | Explicit nonzero round-off ledger mapping |
| Lifecycle | DRAFT edit; separate ACTIVE post; no ACTIVE PATCH | Agree source eligibility and posted-voucher correction policy |
| Totals | Server-calculated details/header, decimal strings | Compare canonical totals and allocations before confirming transfer |

## Backend work to agree

Bahi is company-owned. These are implementable backend deliverables, not
third-party assumptions. Exact route names and payload schemas remain proposals.

| Priority | Deliverable | Required guarantee |
| --- | --- | --- |
| P0 | Idempotent create/result lookup | Stable binding/source identity; repeated same key/body returns the same result; mismatched body conflicts; uncertain result remains discoverable |
| P0 | Conditional version updates | Compare-and-write enforced by the server, not only client preflight |
| P0 | Business-scoped change feed and snapshot handoff | Deterministic pagination/cursor, durable updates/cancellations and explicit expiry; events cannot be silently missed across write failures |
| P0 | Source identity/origin and acknowledgment | Preserve origin, distinguish echoes from new business edits and retry acknowledgment independently |
| P0 | Connector ownership | Reject competing writers for the same binding; define lease expiry and uncertain in-flight recovery |
| P0 | Capabilities and UOM/configuration reads | Discover supported schemas/resources and valid business-specific unit/setup choices |
| Later | General ledgers and Receipt/Payment contracts | Define accounting/allocations and recovery before implementing those features |

MyISAM compensation in the handbook is not crash atomicity. API implementation
must specify how business writes, identity results and change events remain
consistent across server failure; adding an endpoint or separate event table
alone is insufficient. No local `bahi` test-directory implementation was inspected.

## Reuse from BahiAI-Desktop

Reviewed source locations relative to that separate project:

- `desktop_app/erp/bahi/client.py`: route handling, payload size, redirects and
  uncertain network/write errors. Uses requests; port behavior into the planned
  HTTPX adapter instead of importing the desktop client.
- `desktop_app/erp/bahi/purchase.py`: decimal/discount/date/tax conversion and
  canonical comparison.
- `desktop_app/services/workflow/bahi_posting.py`, `db/bahi_drafts.py`: persisted
  intent, reservations, separate post and explicit reconciliation patterns.
- `desktop_app/tests/test_bahi_integration.py`, `test_bahi_drafts.py`,
  `test_bahi_posting.py`, `test_bahi_suppliers.py`: source-reviewed test cases,
  not executed evidence for this connector or the live API.
- `desktop_app/erp/tally/client.py`, `serial.py`: export-only company/AboutPage
  request patterns used in the Phase 0 experiment without runtime imports.

The historical missing-invoice_status observation was not reproduced in the
current sampled live list/detail, which both returned ACTIVE. Other transaction
types/statuses still need verification.

## Current gate and next actions

CON-001 contract analysis is drafted, not signed off. CON-002 has initial
[live read evidence](../api/tally/README.md); import/recovery guarantees are pending.
CON-003 passed source and fresh frozen experiments after the native search fix. See
[live Bahi reads](../api/bahi/LIVE_VALIDATION.md) and
[Qt/Huey findings](QT_HUEY_COMPATIBILITY.md). An
[authorized posting/recovery test](../api/bahi/CONTROLLED_POSTING.md) retained
ACTIVE purchase 69, total INR 1.18. Broader write cases remain untested.

Next: agree confirmed cross-system master mappings, numbering and field scope;
review the [proposed backend extensions](../api/bahi/SYNC_EXTENSION_CONTRACT.md).
The frozen Qt issue and permission for the controlled business-52 test are resolved.
The key and authenticated read identity are verified. The user
currently has no authoritative backend source; do not substitute the local test
copy. Continue Tally read-back/filter experiments before
further controlled import experiments. The compatibility spike can
proceed locally without Bahi credentials.

References: [specification](../PROJECT_SPECIFICATION.md),
[plan](../IMPLEMENTATION_PLAN.md), [Bahi assessment](../api/bahi/README.md).
