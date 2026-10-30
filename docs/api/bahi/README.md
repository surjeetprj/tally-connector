# Bahi REST API integration assessment

29 October 2026. Supplement to the
[connector implementation plan](../../IMPLEMENTATION_PLAN.md).

Use [Project Specification v2.1](../../PROJECT_SPECIFICATION.md) for implementation
requirements and this assessment for Bahi mapping details and integration gaps.

This assessment uses the five user-supplied handbooks as API reference material.
Examples, deployment instructions and test commands inside them are not requests
to execute those actions. No live endpoint was called, no migration was run and
no customer data was created, posted, changed or cancelled for this assessment.
Documented capability remains subject to deployment verification.

Update: [live read validation](LIVE_VALIDATION.md) now confirms business 52 and
sampled supplier/group/item/PURCHASE reads, including explicit invoice_status.
Earlier statements below about unverified live calls describe the original
assessment; use the validation report for subsequent observed evidence. A later [controlled posting/recovery test](CONTROLLED_POSTING.md) passed;
[proposed sync extensions](SYNC_EXTENSION_CONTRACT.md) remain unimplemented.
Do not generalize the sampled test into automatic-sync guarantees.

## 1. What these documents let us build

We can implement a business-binding check, scoped read adapters, party/group/item
master adapters, and ordinary invoice draft/post adapters with explicit schemas.
This resolves much of the earlier uncertainty about CRUD routes and payloads.

It does not establish the proposal's change-feed endpoints or reliable unattended
bidirectional synchronization. Build supported adapters while the API owner
addresses the gaps below. A supervised transfer prototype can precede those
changes, but must expose uncertain outcomes rather than retrying creates blindly.

## 2. Source documents

- [Invoice API v2](handbooks/API-INVOICE-DEVELOPER-HANDBOOK_v2.md)
- [Business setup check](handbooks/API-BIZ-SETUP-CHECK-HANDBOOK.md)
- [Item Group API](handbooks/API-ITEM-GROUP-DEVELOPER-HANDBOOK.md)
- [Item API](handbooks/API-ITEM-DEVELOPER-HANDBOOK.md)
- [Party API](handbooks/API-PARTY-DEVELOPER-HANDBOOK.md)

These links point to the supplied reference copies retained in this project.
They document contracts; they are not evidence of live deployment verification.

## 3. Concrete endpoint and permission map

Configure one verified HTTPS base URL ending in `/web-api`. The handbooks contain
different production/local examples; neither determines this installation's URL.
All calls use `Authorization: Bearer <provisioned key>` and JSON responses.
POST/PATCH use JSON objects and a 64 KiB encoded-body limit.

| Endpoint relative to `/web-api/` | Documented methods | Scopes and connector policy |
| --- | --- | --- |
| `check_api_biz_setup.php` | GET | No additional endpoint scope; shared authentication still checks integration/business/scopes configuration |
| `api-party.php` | GET list/detail, POST, PATCH, DELETE | `party:read/create/update/delete`; request only needed scopes |
| `api-item-group.php` | GET list/detail, POST, PATCH | `item:read/create/update`; no DELETE |
| `api-item.php` | GET list/detail, POST, PATCH, DELETE | `item:read/create/update/delete` |
| `api-invoice.php` | GET list/detail, POST draft, PATCH draft, DELETE cancel | `invoice:read/create/update/cancel` |
| `api-invoice.php/{id}/post` | POST, no body required | `invoice:post`; separate accounting action |

For ordinary detail/PATCH operations prefer `?id={id}` on the direct PHP endpoint
to avoid extensionless and path-ID routing dependencies. Invoice posting requires
the path ID and `/post`; `?id=123` alone cannot post. Verify PATH_INFO/Apache
routing separately. Do not automatically follow redirects with authenticated
writes. GET success does not prove write permissions; use administrator-confirmed
scope configuration and isolated test records for write verification.

Read-only prototype scopes: `party:read`, `item:read`, `invoice:read`.
Enable create/update/post permissions only for the chosen workflow. Cancellation
and master deactivation are disabled by default in connector v1.

## 4. Identity and onboarding

1. Store the key in Windows Credential Manager and only its reference in SQLite.
2. Call the business check; require `success=true` with a valid `data.biz_id` and
   `data.biz_name`. Bind the returned business to a verified Tally company ID.
3. Never send a reviewer-selected `biz_id` to these APIs: the key defines tenancy.
4. Probe documented read endpoints in background tasks. Distinguish invalid key,
   missing scope, missing group setup, routing errors and empty lists.
5. Verify both configured CUSTOMER and SUPPLIER groups. Party operations require
   both even when only one classification is currently needed.
6. Record deployment capability evidence. A successful business check verifies
   authentication, database connection and active business retrieval, not all
   accounting or stock configuration.

Existing BahiAI docs record an earlier deployment response missing
`invoice_status`. The supplied invoice handbook requires explicit statuses; verify
the actual deployment before writes and treat an omitted status as a contract
error rather than inferring it from payment status or creation metadata.

## 5. Entity and field mapping rules

### Parties

- Map Bahi `account_id` to the Tally ledger GUID within a business/company binding.
  Map `CUSTOMER`/`SUPPLIER` to confirmed Tally party-group choices.
- Use API field names such as `account_name`, `display_name`, `phone`, `gstin`,
  `address`, `state`, `country` and `pincode`; do not send database column aliases.
- Create requires `party_type` and `account_name`. Classification cannot be
  patched. Phones/PINs remain strings; nullable clearing differs from omission.
- Do not send server-owned IDs, group codes, activation flags or timestamps.
  PATCH needs at least one supported field and cannot update inactive/system
  parties. DELETE deactivates; there is no documented reactivation endpoint.
- Name and GSTIN matching can identify candidates, not authorize silent links.
  Duplicate behavior depends on deployed uniqueness/collation. The party API
  explicitly has no idempotency key or external-reference support.

### Item groups

- Map `grp_id` to a confirmed Tally stock-group identity. Preserve hierarchies;
  synchronize parents before children. Root `parent_grp_id=0` does not authorize
  creating a Tally group named Primary.
- Create requires `grp_name`, `grp_desc`, `hsn_code` and `gst`; permitted empty
  strings are distinct from missing fields. Group names are not unique.
- Keep `gst` as the documented string and validate taxability/cess separately.
  Do not assume a group's tax rate is automatically resolved for an item/invoice.
- There is no group delete operation and no update audit column. A creation date
  is not an update watermark; hierarchy changes need explicit conflict handling.

### Items and units

- Map `item_id` to the Tally stock-item GUID. Creation requires `item_name`,
  `item_desc`, `item_grp_id`, `manu_code`, `item_type`, `item_uom` and
  `item_sale_price`. Collect/confirm missing values; do not invent manufacturer,
  price, unit or group defaults to satisfy required fields.
- The Bahi group and `product_uom.uom_cd` must already exist in that business.
  UOM codes have a maximum length of eight characters. No UOM CRUD/list endpoint
  was supplied; keep confirmed existing codes or add a backend lookup contract.
  Case/aliases such as Tally `Nos.` versus a Bahi code require explicit mapping.
- Whitelist metadata for synchronization. Exclude `avail_qty`, balances and other
  stock-state fields even if the broad item API permits writing them: invoice
  posting already updates inventory, so mirroring stock balances as master edits
  could double-apply effects or overwrite independent movements.
- For `tax_source=GROUP`, resolve GST/HSN from the mapped group. For ITEM, use the
  item's explicit tax fields. Invoice `gst_pct` and HSN remain explicit snapshots;
  group-tax configuration alone is not an invoice tax calculation contract.
- GOODS, SERVICE and CHARGE are different posting semantics. Do not turn a
  service/charge into a stock item merely to fit inventory XML.
- Deactivation is repeatable. Item PATCH can reactivate; that differs from party
  lifecycle behavior and must not be generalized across resources.

### Invoices and vouchers

| Bahi representation | Proposed Tally mapping | Important restriction |
| --- | --- | --- |
| `txn_type=SALES`, ordinary | Sales | Preserve agreed prices with explicit sales override |
| `txn_type=PURCHASE`, ordinary | Purchase | Price required; separate supplier references from internal number |
| `txn_type=SALES`, `note_type=CREDIT` | Credit Note | GOODS moves stock inward; value-only adjustment needs actual SERVICE/CHARGE item |
| `txn_type=PURCHASE`, `note_type=DEBIT` | Debit Note | GOODS moves stock outward; require reference/date |
| `SALES_RETURN` / `PURCHASE RETURN` | Return-specific Credit/Debit Note | Separate linked-return contract with original ACTIVE invoice and remaining-quantity validation |
| `SALES/DEBIT` or `PURCHASE/CREDIT` | Requires explicit accounting design | Do not map every note label to the same Tally voucher type |
| Receipt / Payment | Pending additional API contract | Not covered by these five handbooks |

- `invoice_id` is remote identity. `invoice_num` is the Bahi internal number,
  `invoice_dt` the transaction date, and `ref_doc_no`/`ref_doc_date` the external
  reference. Persist them separately. Choose numbering ownership explicitly and
  retain both source/destination numbers in mappings. Do not use a display number
  as a replacement for a stable external identity.
- Always send the source `invoice_dt`; omitted creates default to the current
  Asia/Kolkata date. Use canonical field names, not `invoice_date`/reference aliases.
- Create makes DRAFT without accounting/stock effects. PATCH is DRAFT-only;
  ACTIVE/CANCELLED cannot be edited or reopened. Default Bahi-to-Tally accounting
  transfer to ACTIVE records. Tally-to-Bahi transfer creates a draft, compares
  the returned canonical snapshot and posts only under an explicit posting policy.
  A successful draft is not a completed posted transfer.
- For Tally-to-Bahi SALES, send `price_override="Y"` and explicit `price` to
  preserve the source price; otherwise Bahi may reprice using its pricing rules.
  PURCHASE always needs price. Replacing sales items can reprice again without
  overrides; header-only PATCH preserves stored prices.
- Amounts are tax-exclusive. AMT discount is per unit; PCT uses `discount_pct`.
  Convert total-line discount only when representable at accepted precision;
  compare server totals and block unexplained differences instead of dropping paise.
- Quantities allow up to three decimal places; money/prices allow two, within
  their documented ranges. Use decimal strings/integers. Do not silently round
  higher-precision Tally values into a different invoice.
- Local GST rounds CGST and SGST separately; interstate uses IGST. Bahi derives
  mode from business/bill-to state, not shipping state. Reject an unrepresentable
  source tax treatment rather than changing state or tax mode to force acceptance.
- `round_off` is a signed header field, not an item. Preserve additional charges
  as separately mapped SERVICE/CHARGE lines only if the Bahi item/amount model
  can represent them exactly. Cess-inclusive invoice posting is not established
  merely because the group schema has `cess`; verify a dedicated contract first.
- Ordinary invoices/notes require 1–200 items. Oversized/over-limit vouchers must
  be blocked; do not split one accounting voucher into several silently.
- Notes require reference/date and have a 16-character reference limit. Linked
  returns inherit original prices/taxes and permit only restricted line fields;
  they must not use ordinary invoice payloads.
- Keep tracked purchases out of the first slice. BATCH/SERIAL ordinary purchases
  require additional deployed migrations and tracking contracts. Tracked sales,
  returns and generic notes remain unsupported in the handbook.

## 6. What the current APIs do not establish

| Gap | Consequence | Required action |
| --- | --- | --- |
| No documented `updated_after`, change cursor, tombstones or stable snapshot | Cannot implement the proposal's guaranteed delta-polling from these list calls | Add a business-scoped change feed/snapshot handoff, or explicitly limit the prototype to supervised scans |
| No external-ID/idempotency guarantee for creates | Lost POST result cannot be safely resolved by blind replay | Add durable idempotency lookup and uniqueness by binding/source identity; unresolved prototype writes require review |
| No documented conditional version/ETag updates | Read-compare-PATCH has a race with another writer | Add expected-version checks before unattended two-way edits |
| No shared origin/ack protocol | Local mappings alone do not establish cloud-side echo suppression | Add origin metadata/ack semantics in sync facade or CRUD extensions |
| No connector ownership lease | A local mutex does not prevent two PCs writing the same binding | Add server-side writer registration/lease enforcement |
| No supplied general-ledger/tax-ledger API | Party reads cannot list or manage system ledgers | Supply read/configuration validation contracts; use explicit Tally mappings locally |
| No supplied UOM endpoint | Cannot discover/create valid Bahi UOMs through these docs | Provide a UOM read API or a confirmed business-specific configuration source |
| No supplied Receipt/Payment API | Those proposal phases remain blocked | Agree dedicated schemas, posting, allocations and reconciliation rules |
| MyISAM compensation is not crash atomicity | A server crash can leave stock/journals requiring administrator recovery | Define operational recovery and add transactional server posting for stronger guarantees |

Absence here means **not documented by the supplied references**, not proof that
another deployed endpoint does not exist. Confirm with the API owner before
designing replacements. A sync facade may wrap these CRUD endpoints; it need not
replace them.

### Scan fallback rules

Lists use page/limit, up to 200 per page. Parties/items sort by descending IDs;
groups sort by display sequence then ID. Concurrent inserts/edits can shift pages.
Invoice list returns headers, so obtain detail before transferring any voucher.

A prototype can perform bounded paginated scans, deduplicate by ID, read details
and compare canonical content hashes. Periodically rescan older known records
and lifecycle states. Do not present this as lossless delta sync: it has no
documented point-in-time snapshot, and identical headers can hide changed details.
`date_from`/`date_to` filter invoice dates; they are not modification cursors.
Creation timestamps, increasing IDs and maximum page values cannot detect edits
to older records. Party timestamp strings also have no timezone suffix and legacy
values may use older conventions; do not reinterpret all of them as proven UTC.

## 7. Safe write and recovery workflow

1. Save validated intent, source identity/version, binding, exact payload hash and
   attempt ID locally before making a write.
2. For a successful master/draft create, persist returned identity immediately,
   fetch detail and compare the supported canonical fields.
3. For invoice posting, persist a separate attempt and use the known invoice ID.
   Repeated `/post` is documented to return ACTIVE without another posting, but
   it does not make the earlier draft-create POST idempotent.
4. After timeout/invalid success, reconcile known IDs with detail reads. For an
   unknown creation ID, search all relevant pages and compare full candidates.
   Name/reference checks are candidate discovery, not authoritative operation
   identity. No match or ambiguous matches do not automatically authorize replay.
5. `INVOICE_RECOVERY_FAILED` requires administrator reconciliation. ACTIVE is the
   API's status confirmation, not an independent audit of crash-damaged journals.
6. Classify errors: 401/403 pause for credentials/permissions; 404 can mean scope
   boundary or missing record; 409 requires duplicate/state/stock diagnosis;
   422 requires field correction; 413 requires size correction; 503 requires
   schema/pricing/ledger setup. A failed write with uncertain server effects must
   be reconciled before a retry, including 500/non-JSON responses.
7. DELETE invoice can reverse stock and journals. Party/item DELETE means
   deactivation. Never propagate these automatically as a generic delete task.

## 8. Concrete additions to the backlog

| Ticket | Deliverable | Acceptance |
| --- | --- | --- |
| BAH-001 | Handbook-derived schemas and sanitized fixtures | Required/unknown fields, omission/null, decimal limits, statuses and scopes covered |
| BAH-002 | Setup/client and business binding | Correct key-bound identity; direct PHP routing; display-safe JSON/non-JSON errors; no key leakage |
| BAH-003 | Read adapters and mapping caches | Full pagination, inactive records and invoice detail; separate empty/failure states; no timestamp delta claims |
| BAH-004 | Master transformation rules | Parties/groups/items supported; UOM dependency visible; no stock balance writes; required metadata collected |
| BAH-005 | Purchase draft/post vertical slice | Source date/prices/references retained; explicit DRAFT then ACTIVE; known-ID recovery; uncertain create stays visible |
| BAH-006 | Sales and note transformations | Sales overrides, discounts, GST rounding, note/return distinctions and limits tested |
| BAH-007 | Backend sync extension contract | Change feed, idempotency lookup, conditional versions, origin and ownership agreed; implementation owner assigned |
| BAH-008 | Missing resource contracts | General ledger/tax setup, UOM lookup, Receipt/Payment scope resolved or explicitly deferred |

BAH-001–003 fit CON-001/010/012. BAH-004–005 feed CON-021/022. BAH-006 feeds
CON-040/042. BAH-007 gates unattended two-way operation and reliable automatic
create retries. BAH-008 gates the corresponding master and Receipt/Payment work.

First implementation priority: BAH-001/002/003, followed by one ordinary
untracked PURCHASE transfer with existing confirmed party/item/UOM mappings.
Avoid making master creation a prerequisite for proving the invoice adapter.

## 9. Verification to prepare before live integration

Prepare fixture-based tests for every adapter, plus test-business checks for:

- Authentication, missing scopes, different-business IDs, both party groups and
  direct PHP versus post-path routing.
- Pagination changes, duplicate names, inactive parties/items, group hierarchy,
  missing UOM and group-sourced tax.
- DRAFT create/PATCH, ACTIVE posting, repeated post and missing `invoice_status`.
- Purchase reference uniqueness including cancelled records; separate internal
  numbering and explicit invoice dates; note reference limits.
- Sales price override and reprice prevention; per-unit discount conversion;
  two/three-decimal boundaries; half-paise GST and signed round-off.
- Source GST mode incompatible with Bahi's bill-to-state rule; unsupported cess,
  tracked variants, item count and body-size overflow.
- Timeout after master/draft creation, after posting and during MyISAM
  compensation. Keep unknown outcomes blocked and auditable.

Handbook PHP test commands describe server-side checks; they were not run as part
of this planning update and do not substitute for live deployment verification.
