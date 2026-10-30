# innoforia-tally-connector: actionable implementation plan

Prepared 29 October 2026. Delivery backlog supporting [Project Specification v2.1](PROJECT_SPECIFICATION.md).

Revised after reviewing the five supplied Bahi API handbooks. The
[Bahi REST integration assessment](api/bahi/README.md)
records actual routes, scopes, mapping rules and remaining contract gaps.
Handbook behavior is documented capability, not verified live deployment.

Status: proposed implementation backlog; no connector implementation has begun.
Use the [documentation index](README.md) for reading order and source authority.
Project Specification v2.1 governs architecture; this document owns delivery
phases, tasks, dependencies and acceptance gates.

## 1. Delivery recommendation

Build a standalone Windows PySide6 application with an outbound HTTPS Bahi
adapter, a serialized local Tally XML adapter, SQLite operation records, and
SqliteHuey for execution. Keep the Qt event loop responsive throughout.

Start with one explicitly bound Bahi business and Tally company per installation.
Keep all persisted identities scoped to that binding so later multi-company
support does not require rebuilding identity rules.

The first usable milestone should synchronize a customer/vendor master and one
ordinary purchase voucher in both directions, including a supported edit,
duplicate suppression, and recovery after an interrupted write. This is an
engineering milestone, not the full product release.

Do not defer all UI work until the engine is complete: provide connection setup,
status, pause, and operation visibility early so integration work is reviewable.

## 2. Scope and release boundaries

| Stage | Included | Boundary |
| --- | --- | --- |
| Engineering slice | Customer/vendor ledgers; ordinary purchase create/read-back; Tally-to-Bahi ingestion and supported edit; manual sync | Test companies only; simple single-currency examples |
| Pilot | Customer/vendor parties, item groups and untracked stock items; mapped existing UOM/tax ledgers; ordinary Sales and Purchase for supported fields | One active binding; confirmed mappings; manual or supervised transfer until sync guarantees exist; explicit enablement of accounting writes |
| v1 completion | Credit Note and Debit Note; supported entities in both directions; conflict resolution, recovery, installer and support tools | Receipts/Payments and general ledger/UOM synchronization require additional API contracts; unattended bidirectional release requires backend sync guarantees |
| Deferred | Multi-company UI, multiple active connectors for one binding, hard deletion, automatic overwriting of posted vouchers, advanced inventory/accounting features | Expose unsupported data as actionable blocked operations |

Define the exact supported accounting subset during discovery: inventory versus
ledger-only invoices, discounts, bill allocations, GST/cess, freight and other
charges, round-off, units, and decimal precision. Multi-currency, godowns,
batches, tracking numbers, manufacturing and payroll are deferred unless the
initial customer requirements explicitly bring them into scope.

## 3. Resolve these proposal gaps first

1. **CRUD is documented; sync endpoints remain proposed.** The supplied handbooks
   establish `/web-api/check_api_biz_setup.php`, `api-party.php`,
   `api-item-group.php`, `api-item.php` and `api-invoice.php`, including a separate
   invoice posting action. They do not establish `/v1/sync/pending`, `/ack`, or
   `/from-tally`, change cursors, external-ID creation or conditional updates.
   Verify deployed behavior and assign those backend gaps separately.
2. **Cursor safety.** Prefer a server-issued opaque change cursor. If timestamps
   are mandatory, use stable `(updated_at, id)` ordering, a server-bounded
   snapshot and overlap/deduplication. Never use the desktop clock as the next
   cursor or advance over records that were not durably captured.
3. **Durability exceeds Huey persistence.** Store business operations and an
   enqueue outbox in one metadata transaction. Huey executes operation IDs;
   startup redispatches unfinished durable operations. The metadata database and
   Huey database do not share an atomic transaction.
4. **Import responses require read-back.** Tally documents response counters and
   `LASTVCHID`; do not assume each import returns GUID, MASTERID and ALTERID.
   Verify identity and canonical content through a follow-up export query.
5. **Retries do not establish idempotency.** Prove how a namespaced ERP identity
   is stored and queried for each entity type. Test `REMOTEID` behavior rather
   than treating it as a universal duplicate-prevention guarantee.
6. **Embedded worker lifecycle is a spike.** Pin a Huey version and validate its
   signal handling, startup and shutdown alongside Qt on Windows. Do not assume
   the ordinary consumer can simply run inside an arbitrary daemon thread.
7. **Scheduling needs an explicit decision.** Start with 60-second cloud polls
   and 120-second Tally polls. Huey periodic tasks are checked once per minute;
   a 30-second option needs a separately validated scheduling mechanism. All
   triggers, including Sync Now, must coalesce through the same dispatcher.
8. **Company identity and restore handling.** Bind a verified stable Tally
   company identifier, not its display name. Prove AlterID scope and pagination
   on supported releases. Treat a changed identity or cursor regression after
   restore/rewrite as a reason to pause and rebaseline.
9. **Bidirectional conflicts and echoes.** Keep acknowledged source versions,
   canonical content hashes and origin metadata on both sides. Matching a local
   GUID/AlterID alone is insufficient to stop every cloud-to-Tally-to-cloud echo.
10. **Performance figures are hypotheses.** Benchmark the proposal's timings
    against representative test companies. Begin with one voucher per import;
    add batching only when per-record outcomes and uncertain results are safe.

Official references: [Huey API](https://huey.readthedocs.io/en/stable/api.html),
[Huey consumer](https://huey.readthedocs.io/en/stable/consumer.html),
[Tally sample XML and import responses](https://help.tallysolutions.com/sample-xml/).

## 4. Repository boundaries

Use the project layout in [Specification section 3](PROJECT_SPECIFICATION.md#3-project-layout).
Keep the layout defined there as the single source of truth. All package paths
below are relative to `src/innoforia_tally_connector/`.

| Responsibility | Module boundary |
| --- | --- |
| Bootstrap, single instance and shutdown | `__main__.py`, `bootstrap/`, `host/windows/single_instance.py` |
| Runtime paths and nonsecret preferences | `config/paths.py`, `config/settings.py` |
| Canonical entities and business rules | `domain/` |
| Cross-feature connection/operation services and interfaces | `application/services/`, `application/ports.py` |
| Purchase and supported purchase-note use cases | `application/purchases/` |
| Sales and supported sales-note use cases | `application/sales/` |
| Party/group/item use cases and confirmed master mappings | `application/masters/` |
| SQLAlchemy models, sessions and migrations | `persistence/` |
| Bahi wire contracts, endpoints and translation | `integrations/bahi/` |
| Serialized Tally gateway, XML and translation | `integrations/tally/` |
| Durable operation workflows, reconciliation and conflicts | `application/sync/` |
| Huey tasks, coalesced scheduling and redispatch | `execution/` |
| Native credential storage | `host/windows/credentials.py` |
| Qt views, models and event bridge | `ui/` |
| Redacted logging and support bundles | `diagnostics/` |

Purchase, sales and master feature ownership is defined in
[the specification](PROJECT_SPECIFICATION.md#feature-ownership-and-shared-execution).
Use those packages from the first applicable milestone instead of accumulating
business workflows in generic services. Keep operation states, retries, conflicts,
capture and reconciliation shared in `application/sync/`; feature modules supply
their specific rules through application contracts. Mirror these boundaries in
`tests/unit/application/`. Defining ownership now does not enable deferred Sales
or Note features or require empty source scaffolding.

Use SQLAlchemy as the sole ORM and Pydantic for wire/domain contracts. Add
versioned migrations and pin dependencies after the Windows compatibility spike.
Use separate persistent HTTPX clients for cloud and Tally, bounded network
timeouts and no authenticated write redirects. Require XML escaping and strict
undefined values in Jinja2; disable external entity/network resolution in lxml.
Reject or explicitly audit invalid XML characters instead of silently changing
business values.

All Tally requests, including connection checks and UI lookups, must go through
the serialized adapter. `workers=1` protects only work routed through that worker;
it does not prevent another installation, another Windows session, or unrelated
software from accessing Tally.

## 5. Documented Bahi APIs and remaining sync contracts

Use the actual CRUD adapters first. Business identity comes from the authenticated
key; verify `biz_id` using `GET /web-api/check_api_biz_setup.php` and do not send
it as a client-selected request scope. That check does not prove endpoint scopes,
party group configuration or accounting readiness.

| Documented endpoint under `/web-api` | Connector use |
| --- | --- |
| `check_api_biz_setup.php` | Authenticate and bind business identity |
| `api-party.php` | List/detail, create and patch CUSTOMER/SUPPLIER parties; DELETE deactivates |
| `api-item-group.php` | List/detail, create and patch groups; no deletion |
| `api-item.php` | List/detail, create, patch and deactivate items; preexisting group/UOM required |
| `api-invoice.php` | List headers, retrieve details, create/patch DRAFT, separate path-ID POST to `/post`; DELETE cancellation is an accounting action |

Prefer direct `.php` routes with query IDs for ordinary detail operations; verify
PATH_INFO routing for `api-invoice.php/{id}/post`. Configure the actual deployment
base URL rather than using either handbook's example URL. Start with read scopes;
provision create/update/post scopes only for enabled directions and actions.

Important limitations: no documented delta filters or stable snapshot paging;
party API explicitly lacks idempotency/external-reference support; general
ledger, UOM and Receipt/Payment APIs are not supplied. Invoice imports must use
explicit dates, preserve prices with sales overrides, and distinguish DRAFT from
ACTIVE. See the linked assessment for field-level constraints and recovery rules.

### Backend sync extensions still to agree

The following route names are proposals, not existing APIs:

| Operation | Required contract |
| --- | --- |
| Connection/capabilities | Authenticated business identity, permissions, API/schema version and supported entity operations |
| `GET /v1/sync/pending` | Business scope, ordered change events, opaque cursor, pagination, stable page boundary, event ID, entity ID/type/version, operation and origin |
| `POST /v1/sync/ack` | Idempotent per-event outcome; confirmed target identity/version; partial acknowledgment; distinguish retryable failure from applied change |
| `POST /v1/sync/from-tally` | Idempotency key, connector/binding identity, Tally GUID/version, base cloud version, origin and canonical entity payload |
| Reconciliation lookup | Retrieve write result by idempotency key or external identity after a timeout |
| Conflict handling | Conditional updates, explicit version conflict response, current remote snapshot |
| Connector ownership | Server-enforced registration/lease or equivalent rejection of a second writer for the same business/company binding |
| Initial baseline | Bounded snapshot plus incremental handoff with no missing changes; defined historical date range |

Agree on decimal-string money/quantities, dates/time zones, nullable versus absent
fields, deletion/cancellation events, idempotency retention, cursor expiry,
`Retry-After`, error codes and payload size limits. Imported Tally changes must
retain their origin so they are not immediately republished back to the same
connector as new outbound work.

Deliver versioned OpenAPI/JSON schemas, sanitized examples and a mock server.
Do not hide missing cloud capabilities behind client-side guesses.

## 6. Local state and execution rules

Store runtime data under `%LOCALAPPDATA%\InnoforaiTallySync\` as proposed.
Use local-disk SQLite, WAL, foreign keys, short transactions, bounded busy waits,
and one database session per thread. Choose durability settings explicitly and
test process termination; WAL alone is not a recovery design.

| Table | Purpose and essential invariants |
| --- | --- |
| `company_bindings` | Cloud business ID, Tally stable company ID, display snapshots, connector identity and enabled direction/policies |
| `sync_cursors` | Binding + direction + verified stream scope; durable capture cursor and baseline/generation information |
| `entity_mappings` | Binding + entity type + ERP ID; Tally GUID/master ID; last acknowledged versions and canonical hashes; uniqueness on both identities |
| `sync_operations` | Event/version, direction, entity, idempotency key, validated snapshot/hash, state, attempts, next attempt and error |
| `dispatch_outbox` | Operation IDs awaiting Huey dispatch; safe to dispatch repeatedly |
| `sync_attempts` | One record per external write attempt, recorded before sending; response and reconciliation evidence |
| `sync_conflicts` | Baseline, local and remote versions; field differences and explicit resolution audit |
| `sync_audit_log` | Append-only operation and administrative events |

Suggested operation lifecycle:

```text
PENDING -> VALIDATING -> APPLYING -> VERIFYING -> ACK_PENDING -> SUCCEEDED
                |           |           |
                v           v           v
             BLOCKED   OUTCOME_UNKNOWN  RECONCILING

Transient, known-safe failures -> RETRY_WAIT -> PENDING
Concurrent changes            -> CONFLICT
Exhausted recovery policy      -> FAILED (visible and retained)
```

- Advance a poll cursor only after every event in its page is durably recorded
  or recorded as an intentional unsupported/blocking outcome. Application may
  finish later; do not confuse a capture cursor with completed synchronization.
- Persist intent before a remote write. After a successful write, verify target
  identity/content, persist the mapping and queue the acknowledgment.
- A failed acknowledgment retries the acknowledgment, never the voucher create.
- A timeout, disconnect or crash during a write produces an uncertain outcome.
  Reconcile first; retry creation only after authoritative evidence establishes
  that it was not applied. An unresolved lookup stays visible and blocked.
- Order dependent operations: groups/units and mapped ledgers, then stock items,
  then vouchers. A blocked dependency must not stop unrelated captured events.
- Use bounded backoff with jitter for safe transient retries. Authentication,
  missing mappings, invalid amounts and accounting validation errors need action,
  not repeated network attempts. Show an offline state without multiplying jobs.
- Expired execution ownership is recoverable; an expired lease for an APPLYING
  operation is not proof that its external write failed.

## 7. Conflict, mapping and accounting policy

Create an entity-by-field ownership matrix with the accounting/product owner.
Permit automatic propagation only for supported fields whose destination has
not changed since the last acknowledged baseline. Default simultaneous edits
to CONFLICT; do not implement silent last-write-wins for accounting records.

For an unchanged read-back of an ERP write, update observation metadata without
creating a new cloud business change. For a later accountant edit, preserve it
as a new inbound version. Use canonical business content that excludes volatile
transport fields, and keep history so old echoes are not confused with new edits.

Initial sync must offer explicit history start dates and existing-record linking.
Names and document numbers alone do not establish identity. Ambiguous matches
require a confirmed link; renamed entities retain identity. Queue work retains
the company binding captured when it was created, even after UI selection changes.

Require explicit ledger/unit/stock mappings and creation policies. Do not invent
party, purchase/sales, tax, round-off or additional-charge ledgers. Restrict GST
ledger mappings to Duties & Taxes or descendants. Preserve additional charges
separately from inventory and use decimal arithmetic with a defined 0.01 money
tolerance. Keep supplier state separate from Place of Supply and retain required
GST metadata. Never alter an existing stock item's unit/group implicitly.

Treat locked, cancelled, deleted or already posted vouchers according to a
documented business policy. Detect and surface unsupported cancellations/deletions
in v1; automatic destructive propagation remains disabled. Corrections to posted
accounting entries require an approved adjustment/reversal workflow.

## 8. Implementation backlog and acceptance gates

Progress is tracked by completed tasks and verified phase gates. Each phase
defines its scope, responsible roles and acceptance criteria; no duration or
calendar schedule is assigned.

| Phase | Tasks | Owner | Deliverables and acceptance gate |
| --- | --- | --- | --- |
| **0 — Validate the integration** | CON-001 contracts/scope; CON-002 Tally capability spike; CON-003 worker/package spike | Connector + cloud + accounting | Signed scope/field matrix; API capability gap list; reproducible Tally queries for company identity, GUID/AlterID, create/read-back and incremental reads; tested Qt/Huey lifecycle and tiny packaged executable. No production writes. |
| **1 — Establish the foundation** | CON-010 scaffold/CI; CON-011 schema/outbox; CON-012 credentials/clients; CON-013 minimal UI | Connector | Installable source project, migrations, operation store, isolated fake adapters, Credential Manager, setup/status/pause. Test second-instance rejection, migration recovery, private-transport boundaries, concurrent gateway serialization, a local operation-ID task, frozen resources and recovery of an undispatched operation. |
| **2 — Prove one bidirectional slice** | CON-020 baseline/binding; CON-021 master dependency; CON-022 purchase flow; CON-023 reconciliation/ack | Connector + cloud | One test purchase each way with confirmed mappings and target read-back; supported edit returns once. Repeat event, restart after target commit, lost ack and repeated Sync Now produce one business effect. Cloud prerequisite: idempotent ingestion and reconciliation contracts work. |
| **3 — Complete master synchronization** | CON-030 parties/groups/tax mappings; CON-031 existing UOM mappings/stock; CON-032 mapping/conflict UI | Connector + accounting | Supported masters both ways; stable rename handling; existing stock not silently altered; balance fields excluded from master updates; missing mappings block affected operations. General ledger/UOM CRUD depends on additional contracts. |
| **4 — Expand voucher coverage** | CON-040 Sales/Purchase variants; CON-041 Receipts/Payments (backend-dependent); CON-042 Credit/Debit Notes | Connector + accounting + cloud | Supported invoice/note types have both-direction fixtures, draft/post separation, signs, discounts and GST validation. Receipt/Payment work cannot pass its gate without dedicated contracts. Unsupported variants produce precise errors. |
| **5 — Finish desktop operations and resilience** | CON-050 tray/dashboard; CON-051 retries/conflicts; CON-052 diagnostics/fault tests | Connector + QA | Nonblocking logs, counts, last successful sync, company identity, pause/resume, safe retry/reconcile, conflict resolution and redacted support bundle. Fault suite and baseline/restore detection pass. |
| **6 — Package and pilot** | CON-060 installer/upgrades; CON-061 clean-machine checks; CON-062 pilot/runbook | Connector + QA + support | Versioned PyInstaller/Inno artifacts; signature plan for distribution; standard-user install, opt-in startup, upgrade migration/backup and rollback tested; pilot reconciled and approved. |

Dependencies: `0 -> 1 -> 2 -> 3 -> 4 -> 5 -> 6`. Cloud contract work runs
alongside the connector foundation; UI grows in each phase. Contract mocks enable
local work but cannot satisfy the live integration gate.

Assign a Bahi API owner for backend contracts, an accounting reviewer for
voucher gates, QA for fault/recovery checks, and support for the pilot runbook.
Complete the pilot when record counts, accounting totals and exceptions reconcile
and the release criteria pass. Track unresolved dependencies at task level;
existing CRUD endpoints alone do not establish unattended bidirectional behavior.

## 9. Verification and release criteria

Use sanitized golden JSON/XML fixtures, HTTP mocks, temporary SQLite databases,
offscreen Qt tests, and a disposable Tally company for opt-in integration tests.
Never use real customer books as the automated test target.

Mandatory evidence:

- Each supported voucher type works in both directions, with one accounting
  reviewer checking signed totals, tax treatment, references and allocations.
- Test same timestamps across pages, concurrent source edits, cursor expiration,
  interrupted baseline, dependency failures and unsupported entities.
- Kill the process before send, after target commit/before local commit, and
  before/after acknowledgment. Recover without lost durable operations or
  duplicate business effects in these tested cases.
- Test cloud 401/403/429/5xx, Tally closed/busy, invalid XML, explicit LINEERROR,
  counter-only rejection, malformed success, disk-full and SQLite contention.
- Test simultaneous changes, repeated echo events, company rename/switch,
  restored data/AlterID regression and a second connector claiming the binding.
- Sleep/resume and reconnect trigger one coalesced catch-up cycle. No overlapping
  connector Tally calls; busy workers do not freeze or misreport the UI.
- For batching, require per-record verification and partial-failure recovery
  before enabling more than one voucher per import.
- Run fresh install, startup/login, tray close versus Quit, upgrade with pending
  work, migration failure/backup restore, and uninstall-with-data-retained checks
  on supported Windows/Tally versions without a separately installed Python.

Benchmark representative 1/100/1,000-record workloads and capture queue lag,
throughput, Tally response time, memory and UI responsiveness. Set customer-facing
performance targets from those measurements, not the proposal estimates.

Release gate: no unresolved critical accounting or duplicate-write defect; all
supported-direction tests pass; pilot record counts, taxable/tax/gross totals and
outstanding exceptions reconcile; recovery/support instructions have been exercised.

## 10. Security and support requirements

Store API keys in Windows Credential Manager and only a reference locally.
Keep tokens out of queued arguments, URLs, logs and support exports. Cloud uses
verified HTTPS; the default Tally endpoint remains loopback. Do not open a new
local HTTP server or change firewall rules for this architecture.

The proposal's full XML/JSON audit storage should become sanitized summaries and
hashes by default. Persist necessary operation snapshots under restricted local
file permissions; make diagnostic payload capture time-bounded with an agreed
retention policy. Support export is an explicit user action and redacts secrets
and unnecessary personal/financial details. Do not automatically purge invoice
history or unresolved operation evidence during upgrades.

On Quit, stop scheduling, allow bounded network work to finish, record unfinished
operations for reconciliation and close resources. A daemon thread being killed
at process exit is not the shutdown policy. Windows login startup is opt-in;
the agent operates in the signed-in user's session, not as a Windows service.

## 11. Reuse assessment from BahiAI-Desktop

Use the current desktop project as a source of proven behavior and regression
fixtures, not as a runtime dependency of the connector:

- `desktop_app/erp/tally/responses.py`: counters, LINEERROR parsing and friendly
  errors; extend with reconciliation rather than assuming counters prove identity.
- `desktop_app/erp/tally/lookup.py`, `masters.py`, `preflight.py` and `vouchers/`:
  company/master lookup and existing Purchase/Debit Note/bank XML behavior.
- `desktop_app/services/workflow/tally_posting.py`: selected-company guards.
- `desktop_app/services/bahi_credentials.py`: Credential Manager pattern.
- `desktop_app/db/bahi_drafts.py` and related workflow: persisted write attempts
  and uncertain-result recovery patterns.

Review and port the necessary behavior into connector-owned modules with tests;
do not import desktop UI/workflow objects or historical backend/ui folders. Sales
Order support in BahiAI is not Sales Invoice support. The current desktop's
purchase-draft integration is not an existing bidirectional sync API.

## 12. Phase 0 tasks and progression

### CON-001 — Confirm scope and Bahi contracts

- Define the first purchase slice, supported fields, numbering ownership and
  accounting rules, with named product/accounting/backend responsibilities.
- Compare supplied handbooks with observed Bahi behavior; prepare sanitized
  contracts/fixtures and identify missing API guarantees.
- Record backend deliverables and unresolved decisions in the
  [capability checklist](phase0/CONTRACT_VALIDATION.md) and
  [sync-extension proposal](api/bahi/SYNC_EXTENSION_CONTRACT.md).

### CON-002 — Validate Tally capabilities

- Verify test-company identity, source-identity lookup, GUID/AlterID fields and
  company-scoped query behavior.
- Exercise controlled create/read-back and incremental capture, including the
  applicable recovery, date-range and restore limitations.
- Retain sanitized request/response evidence and separate proven behavior from
  assumptions in the [Tally findings](api/tally/README.md).

### CON-003 — Validate worker lifecycle and packaging

- Prove Qt/Huey startup, serialized execution, retry, signal delivery and shutdown.
- Build/run the packaged experiment and verify templates/icons independently of
  the current working directory; record the tested dependency/build recipe.
- Track remaining lifecycle/platform checks in the
  [compatibility report](phase0/QT_HUEY_COMPATIBILITY.md).

### Phase completion and next task

Review evidence against each task's acceptance gate. Keep unresolved prerequisites
visible and do not mark a phase complete because a prototype or one test passed.
Use [STATE_AND_PROGRESS](STATE_AND_PROGRESS.md) for the current completed work,
checks, blockers and next concrete action; this plan owns the task definitions.

After the Phase 0 gates are satisfied, proceed to Phase 1 tasks CON-010 through
CON-013, then the Phase 2 purchase slice. Select a bounded task with explicit
inputs, deliverables and checks instead of requesting the whole connector in one
pass. Advance through later phases according to the dependency and backend
capability gates in section 8.
