# Project Specification v2.1: Innoforia Bahi <-> TallyPrime Desktop Connector

Updated: 29 October 2026.

Status: implementation specification; application not yet implemented. This
revision incorporates the supplied project specification, five Bahi API
handbooks, [implementation plan](IMPLEMENTATION_PLAN.md)
and [API assessment](api/bahi/README.md).
Documented API behavior must still be verified against the selected deployment.

## 1. Objective and delivery scope

Build a standalone native Windows application in Python for controlled
bidirectional transfer between Innoforia Bahi REST APIs and TallyPrime's local
or explicitly configured LAN HTTP/XML endpoint, defaulting to
`http://localhost:9000`.

The production objective is reliable bidirectional synchronization. The existing
handbooks document CRUD and invoice posting, but not all synchronization
guarantees. Distinguish the following operating modes in implementation and UI:

| Mode | Behavior | Availability gate |
| --- | --- | --- |
| Read-only | Verify connections, inspect source data and configure mappings | Documented read APIs and verified Tally queries |
| Supervised transfer | User selects supported records, validates mappings and confirms writes; unresolved outcomes remain visible | Verified CRUD/draft/post contracts and recovery workflow |
| Automatic bidirectional sync | Scheduled transfer of supported changes with origin, version and ownership controls | Verified backend change feed, idempotency/reconciliation, conditional versions and writer ownership |

Initial scope is one active Bahi business/Tally company binding, CUSTOMER and
SUPPLIER parties, item groups, untracked items and ordinary PURCHASE. Add ordinary
SALES and supported CREDIT/DEBIT notes after the purchase flow passes accounting
and recovery gates. Receipt/Payment and general ledger/UOM synchronization require
additional API contracts. Do not present them as implemented or infer routes.

Linked returns, tracked inventory, multi-currency, godowns, batches, serials,
cost centres and automatic cancellation propagation are outside the first slice.
Recognize unsupported source records and display precise blocking issues.

### Core constraints

1. No FastAPI, Flask, Uvicorn, local web server, WebSockets or SSE.
2. All connector-originated Tally HTTP calls run with concurrency one, including
   connection checks, company lists, master lookups, reads and writes.
3. Closing the main window hides it to the system tray when the tray is available.
   Only explicit Quit ends execution. If no usable tray exists, keep the window
   accessible instead of hiding the only UI.
4. Acquire a single-instance lock before starting scheduling or workers. A local
   lock does not establish exclusive ownership across computers/Windows users.
5. No network calls or lengthy SQLite work on the GUI thread. Workers never
   directly mutate Qt widgets.
6. Bind stable business/company identities; company names are display snapshots.
   Every queued operation retains its submitted binding.
7. Never invent missing ledger, unit, stock-group, item, price or reference values.
8. Do not retry a write with an uncertain result until reconciliation proves a
   retry safe. Preserve history, mappings, attempts and unresolved work on upgrade.

## 2. Technology stack and dependency management

Use the requested libraries, with SQLAlchemy as the ORM and Pydantic for domain
and API validation. Do not introduce SQLModel alongside SQLAlchemy.

```text
# requirements.txt: compatibility floors from the supplied specification.
# Validate and record a tested, exactly pinned lock before release.
PySide6>=6.7.0
huey>=2.5.0
SQLAlchemy>=2.0.0
httpx>=0.27.0
Jinja2>=3.1.4
lxml>=5.2.0
pydantic>=2.7.0
```

```text
# requirements-build.txt
pyinstaller>=6.6.0
```

Add pytest and the chosen Qt test integration to development dependencies.
PyInstaller and Inno Setup are build tools, not requirements for users of the
packaged executable. Choose and document a tested Python/Windows/TallyPrime
version matrix during the initial compatibility spike. Minimum versions above
do not prove compatibility with every later release or every Huey API example.

Pin the tested dependency set and verify it in a clean environment. If the
selected Huey version lacks a required retry/lifecycle feature, implement a
tested compatible wrapper or revise the pin; do not assume a newer API exists
at the minimum version.

## 3. Project layout

Use one installable Python package under `src/`, separating business rules,
application workflows and external adapters. The target layout below defines
ownership; create modules as their milestone needs them, not as empty scaffolding.
Package directories use `__init__.py` files, omitted below except at the root.
The source package directories, ownership markers and root project metadata are
established. Executable application modules below remain planned until their
milestones are implemented. Isolated Phase 0 probes/tests remain under
`scripts/phase0/` and `tests/phase0/`; they do not replace runtime adapters.

```text
innoforia-tally-connector/
  README.md
  AGENTS.md                         # Agent rules and navigation
  pyproject.toml                    # Package/build metadata and tool configuration
  requirements.txt                  # Runtime dependency declarations
  requirements-dev.txt              # Test and development dependencies
  requirements-build.txt            # Packaging dependencies
  requirements-lock.txt             # Tested exact dependency resolution
  .gitignore
  src/
    innoforia_tally_connector/
      __init__.py
      __main__.py                   # Thin entry point delegating to bootstrap
      bootstrap/
        application.py              # Construct Qt app and start lifecycle
        lifecycle.py                # Startup, pause, shutdown and startup recovery
        dependencies.py             # Construct adapters and inject shared instances
      config/
        paths.py                    # Runtime locations and packaged resource access
        settings.py                 # Typed nonsecret preferences and defaults
      domain/
        entities.py                 # Canonical party, group, item and invoice data
        identity.py                 # Business/company binding and entity identity
        mappings.py                 # Confirmed party/item/unit/tax/charge mappings
        operations.py               # Operation states and permitted transitions
        money.py                    # Decimal precision, rounding and validation
        validation.py               # Cross-system business constraints
        errors.py                   # Business errors and blocking issues
      application/
        ports.py                    # Interfaces required by application services
        commands.py                 # Inputs to user and worker actions
        events.py                   # Framework-independent application events
        services/
          connections.py            # Verify connections and bind identities
          operations.py             # Inspect operations and request retry/reconcile
        purchases/
          transfer.py               # Purchase use cases in both directions
          validation.py             # Purchase-specific application preflight
          notes.py                  # Supported purchase-note use cases, when added
        sales/
          transfer.py               # Sales use cases in both directions
          validation.py             # Sales-specific application preflight
          notes.py                  # Supported sales-note use cases, when added
        masters/
          parties.py                # Customer/vendor master use cases
          item_groups.py            # Stock-group master use cases
          items.py                  # Item master use cases
          mappings.py               # Confirm/retrieve all scoped master mappings
        sync/
          capture.py                # Source capture and durable checkpoints
          planning.py               # Dependencies and durable operation creation
          execution.py              # Apply, verify and complete business operations
          reconciliation.py         # Resolve uncertain external write outcomes
          conflicts.py              # Baseline comparison and explicit resolution
          policies.py               # Eligibility, origin and automatic-write rules
      integrations/
        bahi/
          client.py                 # HTTP transport, authentication and envelopes
          errors.py                 # Bahi error classification
          endpoints/
            business.py
            parties.py
            item_groups.py
            items.py
            invoices.py
          schemas/                  # Exact Bahi request/response contracts
          mappers/                  # Bahi payloads <-> canonical domain entities
        tally/
          gateway.py                # Shared serialized access boundary
          _transport.py             # Private HTTP transport used by gateway only
          companies.py              # Company discovery and identity verification
          queries.py                # Master, read-back and incremental query logic
          responses.py              # Import counters, errors and export parsing
          xml_codec.py              # Strict XML parsing, escaping and rendering
          errors.py
          mappers/                  # Tally records <-> canonical domain entities
          builders/
            masters.py
            purchase.py
            sales.py
            notes.py
          templates/
            queries/
            masters/
            vouchers/
      persistence/
        database.py                 # SQLAlchemy engines and session management
        unit_of_work.py             # Local transaction boundaries
        models/                     # SQLAlchemy models, separate from domain/API
        repositories/               # Bindings, mappings, operations, attempts, logs
        migrations/
          runner.py                 # Execute ordered migrations and version checks
          registry.py               # Explicit imports of migration implementations
          versions/                 # Numbered Python migrations and required assets
      execution/
        queue.py                    # SqliteHuey configuration
        tasks.py                    # Thin tasks accepting durable operation IDs
        consumer.py                 # Embedded worker lifecycle
        scheduler.py                # Coalesced poll/manual/health triggers
        recovery.py                 # Redispatch and expired-owner recovery
      host/
        windows/
          credentials.py            # Windows Credential Manager
          single_instance.py        # Process instance lock
          startup.py                # Opt-in Windows login startup
      diagnostics/
        log_setup.py                # Structured logging configuration and rotation
        redaction.py                # Secret/customer-data filtering
        support_bundle.py
      ui/
        main_window.py              # Window shell and navigation
        tray.py
        bridge.py                   # Application events -> queued Qt signals
        controllers/                # Dispatch commands and handle async results
        pages/                      # Dashboard, operations, mappings, conflicts
        dialogs/                    # Settings, confirmation and operation details
        models/                     # Qt table/list models
        widgets/                    # Reusable presentation components
      resources/
        icons/
        styles/
  tests/
    unit/                           # Domain rules and isolated application flows
      domain/
      application/
        purchases/
        sales/
        masters/
        sync/
    architecture/                   # Dependency and private-transport boundaries
    contract/
      bahi/
      tally/
    persistence/                    # Transactions, constraints and migrations
    recovery/                       # Crash boundaries and uncertain writes
    ui/                             # Qt models, actions and lifecycle
    integration/                    # Opt-in disposable live environments
    packaging/                      # Frozen asset/import smoke checks
    fakes/                          # Controllable adapters and in-memory ports
    fixtures/
      bahi/                         # Sanitized JSON
      tally/                        # Sanitized XML
  scripts/
    build_exe.py
  packaging/
    pyinstaller/
      connector.spec
    inno_setup/
      installer.iss
  docs/
    README.md
    STATE_AND_PROGRESS.md           # Current state, evidence and next task
    PROJECT_SPECIFICATION.md
    IMPLEMENTATION_PLAN.md
    api/bahi/
      README.md
      handbooks/
```

### Dependency and ownership rules

- `domain/` owns canonical business entities, mapping values and validation. It
  must not import Qt, HTTPX, SQLAlchemy, Huey or concrete integration adapters.
- `application/` owns transfer workflows and recovery decisions, depending on
  domain types and interfaces in `application/ports.py`. It must not import UI,
  concrete persistence, concrete integrations or Huey. Keep interfaces limited to
  capabilities needed by actual use cases; avoid speculative abstraction layers.
- `integrations/` owns external protocols, wire schemas, XML and translation to
  canonical domain entities. Bahi and Tally adapters do not import each other.
- `persistence/` implements repository/transaction interfaces. ORM rows are not
  passed to the UI or reused as Bahi response schemas. `execution/` adapts Huey
  and scheduling to application services; business state transitions stay in
  `domain/` and `application/`, not queue decorators.
- `ui/` dispatches commands and presents read snapshots through controllers and
  `bridge.py`; it has no direct HTTP, ORM sessions or queue-backend access.
  `bootstrap/` connects concrete components and owns process lifecycle.
- Use absolute package imports. `host/windows/` and `log_setup.py` make intent
  explicit; do not modify `sys.path` to expose internal package directories.
  `pyproject.toml` owns package/build/tool metadata; requirements files remain
  the dependency source, avoiding independently maintained duplicate lists.
- Keep the canonical project/package spelling `innoforia`:
  `innoforia-tally-connector` and `innoforia_tally_connector`. The executable and
  runtime-directory identifier `InnoforaiTallySync` remains the explicit identifier
  selected by this specification; handle any future rename as a migration.

### Shared gateway and mapping boundaries

`bootstrap/dependencies.py` constructs one Tally gateway for the process and
injects it into consumers of the Tally port. Use dependency injection rather than
requiring a Singleton class. Route every request through serialized background
execution, including Verify Connection and Fetch Companies. The gateway also
owns a normal process-local lock with bounded acquisition; use reentrancy only
if a demonstrated call pattern needs it. Busy/deferred lock acquisition must
never trigger a second request, mark Tally offline by assumption or classify a
write as failed. Do not acquire/wait for this lock on the GUI thread.

Only `integrations/tally/gateway.py` imports `_transport.py` in production code.
Other Tally modules use gateway calls or produce/parse data. Tests may exercise
private transport behavior directly. Enforce this boundary with an architecture
test and verify concurrency under competing worker/health/manual triggers.
Cross-PC ownership still requires the separate backend lease contract.

Mapping models and `application/masters/mappings.py` explicitly cover party,
item, unit, stock group, purchase/sales ledger, GST component, charge and round-off
ledgers. Persist binding context and confirmation evidence; free-text name
similarity is a suggestion, not permission to export. Money rules validate source
values and explain mismatches; they never silently insert balancing adjustments.

### Feature ownership and shared execution

The application feature subdivisions above are decided now and must be used
when implementing their milestones. Do not collect purchase/sales/master business
workflows in a generic `application/services/transfers.py` module.

| Package | Owns | Delegates to shared components |
| --- | --- | --- |
| `application/purchases/` | Purchase preflight and transfer orchestration in either direction; supported purchase-note rules | Durable planning/execution, reconciliation, conflicts, mappings and external ports |
| `application/sales/` | Sales preflight and transfer orchestration in either direction; source-price preservation and supported sales-note rules | The same shared operation engine and adapter ports |
| `application/masters/` | Party, item-group and item use cases; confirmation/retrieval of party, unit, tax, charge and other master mappings | Shared operation engine, domain mapping types and repository/adapter ports |
| `application/sync/` | Capture/checkpoints, dependency scheduling, durable execution, uncertain outcomes, conflicts and origin/retry policy | Feature-specific decisions supplied through explicit contracts |
| `application/services/` | Cross-feature connection/binding checks and operation inspection/action requests | Feature use cases and the shared operation engine |

Purchase and sales feature validation applies workflow context; reusable money,
identity and accounting invariants remain in `domain/`. Wire-field validation and
XML construction remain in their integration adapters. Feature modules must not
contain SQLAlchemy sessions, HTTP clients, Huey decorators or Qt widgets.

Keep one durable operation state machine and recovery implementation. Features
must not create separate queues, retry loops, reconciliation stores or independent
echo rules. Feature-specific read-back comparisons can be supplied to the shared
engine through typed contracts; `bootstrap/dependencies.py` registers the concrete
handlers. Avoid circular imports between features and the shared engine, and
avoid direct imports between sibling feature packages. Request master mappings
through application ports rather than importing another feature's implementation.

Organize feature tests under `tests/unit/application/{purchases,sales,masters}/`
and shared engine tests under `tests/unit/application/sync/`. Add architecture
checks for these boundaries. The package ownership is fixed in this layout;
create executable modules only when their milestone is implemented. In
particular, Sales and Notes remain deferred capabilities until their contracts
and accounting gates pass.

### First foundation milestone

After Phase 0 selects a supported worker lifecycle, implement only the subset
needed for business verification, company discovery, secure settings, persistence,
a responsive window/tray and serialized execution. Start with domain identity/
operations/errors, connection services and ports, business endpoint schemas,
Bahi client, Tally gateway/transport/company query, Windows credentials/lock,
logging/redaction, database/binding/operation repositories and migration runner.

Include bootstrap, the event bridge and minimal UI, Huey queue/consumer plus a
real durable operation-ID task that exercises local execution without accounting
writes. Add dispatch outbox/attempt storage when needed for that task's recovery;
they are mandatory before external writes. Do not build every later entity,
mapper, voucher template or dialog as empty scaffolding.

Acceptance includes contract fixtures, transaction/migration recovery tests,
private-import/concurrent-gateway checks, a working local queue round trip,
shutdown/restart handling and a frozen build that can locate its query template
and icon. Purchase transfer follows after these foundation checks pass.

## 4. Storage, credentials and local database

Resolve the Windows user's Local AppData directory and store runtime data under
`%LOCALAPPDATA%\InnoforaiTallySync\`. This is the runtime directory name used
throughout the development documents. If a previous installation has data in a
different directory, require a tested migration/selection rule rather than
silently starting a second workspace.

- `sync_metadata.db`: application state, operations, attempts, mappings and audit.
- `huey_queue.db`: Huey-owned execution queue.
- `logs/`: bounded, rotating, redacted application logs.
- `app.lock`: QLockFile instance lock.

Create missing application directories. Fail with an actionable message when
the runtime path is unavailable/unwritable; do not fall back to Program Files or
the working directory. Store API secrets in Windows Credential Manager and only
a credential reference in local configuration. Tokens must never be queued,
logged or stored as an `erp_api_token` database column.

### SQLite requirements

Enable WAL, foreign keys and bounded busy waits; establish the settings on the
appropriate connections for both databases. Use one SQLAlchemy session per
thread/unit of work and short transactions; never keep a transaction open over
HTTP. WAL improves read/write coexistence but does not eliminate lock contention.

Use these as an explicit starting policy, tested during the recovery spike:

```sql
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;
PRAGMA synchronous=FULL;
```

FULL is the proposed metadata durability setting. Any weaker queue/metadata
setting needs documented recovery tradeoffs. Handle disk-full and lock failures
without losing evidence or reporting unconfirmed success. Add versioned schema
migrations and SQLite-consistent backups; do not copy a live WAL database file
alone and assume it is a complete backup.

Implement application metadata migrations in `persistence/migrations/runner.py`
with an explicit ordered registry and numbered migration modules. Use SQLite
`PRAGMA user_version` as the authoritative metadata-schema version, not a second
independently updated version in settings. The runner must reject newer schemas,
advance the version only after successful migration, and test actual transaction
and restart behavior. Huey's schema remains owned by Huey; never apply application
migrations to its queue database.

Run metadata migrations under exclusive application startup ownership before
starting workers or other database consumers. A startup/progress window may be
shown, with lengthy work off the GUI thread. On failure, preserve evidence,
prevent writes and offer documented recovery from a consistent backup.

### Required logical tables

| Table | Essential fields and invariants |
| --- | --- |
| `app_config` | Singleton ID; verified deployment URL; credential reference; Tally endpoint; intervals; startup/tray preferences. No fabricated API default. Startup opt-in, default false. |
| `company_bindings` | Local ID, Bahi business ID, verified Tally company ID, display snapshots, connector installation ID, operating mode and enabled directions |
| `sync_state` | Binding + direction + verified entity/stream scope; capture checkpoint; baseline/generation metadata. Company name is not a primary key. |
| `id_mapping` | Binding + entity type + ERP ID; Tally GUID/master ID; acknowledged source/destination versions and canonical hashes. Unique identities scoped by binding and type. |
| `sync_operations` | Immutable operation ID; source event/version; binding/direction/entity; idempotency key; payload snapshot/hash; state; next attempt; attempts; error |
| `dispatch_outbox` | Operation IDs pending Huey dispatch; committed with captured operations/checkpoint |
| `sync_attempts` | Recorded before each external write; owner/lease, request hash, result, uncertainty and reconciliation evidence |
| `sync_conflicts` | Baseline/source/target snapshots, differing fields and explicit resolution |
| `sync_logs` | UTC timestamp; operation ID; direction/type/reference; state; redacted message; evidence references. Not the retry authority. |

Use entity types that distinguish PARTY, ITEM_GROUP, ITEM and INVOICE locally.
Tally LEDGER/STOCK_GROUP/STOCK_ITEM/VOUCHER categories are adapter mappings.
Master balance/opening-stock synchronization is excluded unless separately scoped.

## 5. Actual Bahi REST contracts

Configure a verified HTTPS deployment URL ending in `/web-api`. Do not default
to the invented `https://api.innoforai.com/v1` route. Local HTTP is permitted only
for explicitly configured local development. Business scope comes from the key;
do not submit a client-selected `biz_id`.

Maintain a persistent HTTPX client for Bahi and a separate one for Tally, with
explicit bounded timeouts and connection limits. Disable authenticated redirect
following, validate response envelopes, and parse JSON error messages before
falling back to generic HTTP errors. A 15-second timeout is an initial configurable
setting, not a claim that a timed-out write failed.

### Documented route map

Routes below are relative to `/web-api/`:

| Route | Methods/actions | Required scopes |
| --- | --- | --- |
| `check_api_biz_setup.php` | GET authenticated business identity | No additional endpoint scope; shared authentication/scopes configuration applies |
| `api-party.php` | GET list/detail; POST; PATCH; DELETE deactivation | `party:read`, `party:create`, `party:update`, `party:delete` respectively |
| `api-item-group.php` | GET list/detail; POST; PATCH | `item:read`, `item:create`, `item:update` |
| `api-item.php` | GET list/detail; POST; PATCH; DELETE deactivation | `item:read`, `item:create`, `item:update`, `item:delete` |
| `api-invoice.php` | GET list/detail; POST DRAFT; PATCH DRAFT; DELETE cancellation | `invoice:read`, `invoice:create`, `invoice:update`, `invoice:cancel` |
| `api-invoice.php/{id}/post` | POST separate accounting/stock posting | `invoice:post` |

Use `?id={id}` for ordinary detail/update calls on direct PHP routes. Invoice
posting requires the path ID plus `/post`; verify Apache/PATH_INFO support.
Extensionless routes require verified server routing. Start with read scopes;
enable write/post scopes only for explicitly enabled actions. The setup check
confirms business/authentication, not all endpoint permissions or posting setup.

### Payload rules

1. POST/PATCH accept JSON objects within the 64 KiB encoded-body limit. Reject
   unsupported fields; do not attach arbitrary sync metadata to CRUD payloads.
2. Party create requires `party_type` and `account_name`. Preserve omitted versus
   null values, API-specific names, and string phone/PIN fields. Classification
   cannot be patched; inactive/system accounts have restrictions.
3. Item-group create requires `grp_name`, `grp_desc`, `hsn_code` and `gst`.
   Names are not guaranteed unique. Keep hierarchy and taxability explicit.
4. Item create requires `item_name`, `item_desc`, `item_grp_id`, `manu_code`,
   `item_type`, `item_uom` and `item_sale_price`. Bahi group and UOM must exist.
   No UOM endpoint is supplied. Never invent required manufacturer/price fields.
5. Whitelist item metadata; never mirror `avail_qty` or running balances.
   Invoice posting changes stock separately. Resolve group-sourced tax explicitly.
6. Invoice create produces DRAFT without accounting/stock effects. PATCH is
   DRAFT-only. Require explicit `invoice_status` in reads and write recovery.
7. Send `invoice_dt`, `invoice_num` when required by the numbering policy,
   `ref_doc_no` and `ref_doc_date` as separate values. Preserve both source and
   destination numbering. Dates/reference aliases are not interchangeable.
8. Ordinary purchases require price. SALES imports preserving Tally prices must
   send `price_override="Y"` and explicit price. Replacing sales lines without
   overrides can reprice them. AMT discount is per unit; PCT uses `discount_pct`.
9. Use decimal strings/integers and Decimal calculations, not floating-point
   money. Invoice quantity supports up to three fractional digits; price/money
   two, within documented bounds. Block unrepresentable source precision.
10. Bahi calculates local/interstate GST from business/bill-to state. Preserve
    source tax treatment and block incompatible cases. Validate separate CGST/
    SGST rounding, explicit GST/HSN and signed header `round_off`.
11. Additional charges require actual mapped SERVICE/CHARGE items and exact
    representation; do not masquerade them as inventory. Cess support in an item
    group does not establish invoice cess-posting support.
12. Ordinary invoices/notes support 1–200 items. Block overflow rather than
    silently splitting one voucher. Notes require references and a 16-character
    reference-number limit. Linked returns have a different inherited-price and
    remaining-quantity contract; do not use ordinary invoice payloads.
13. Map ordinary PURCHASE/SALES explicitly. Initially support PURCHASE/DEBIT and
    SALES/CREDIT notes only after their accounting gates. Other combinations need
    explicit treatment; a note label alone does not determine a Tally voucher.
14. Treat DELETE as a resource-specific business action: party/item deactivation
    differs from invoice cancellation/reversal. Automatic propagation is disabled.

### Synchronization API gaps

`/sync/pending`, `/sync/ack` and `/sync/from-tally` from the earlier specification
are proposed extensions, not documented existing endpoints. Do not call them or
implement a fake production success response. Agree contracts for:

- Stable business-scoped change feed, bounded snapshot handoff, pagination,
  update/cancellation events and cursor expiry.
- Idempotent creates with durable external identity and result lookup.
- Conditional version updates and conflict responses.
- Change origin, acknowledgments and echo suppression.
- Connector registration/lease enforcing one writer per binding across PCs.
- Missing UOM/general-ledger and Receipt/Payment resource APIs.

Where a backend feed is unavailable, supervised scans can enumerate pages,
deduplicate by ID, fetch invoice details and compare canonical hashes. They are
best-effort scans, not lossless incremental sync. Date filters are invoice-date
filters, not update cursors. Item groups have no update audit column; ID maxima
and creation timestamps cannot detect old edits. Do not enable unattended
two-way mutation on assumptions about absent guarantees.

## 6. Tally XML engine requirements

### Company and identity guards

Discover and verify stable company identity; send the correct company context
with every request and verify it before writes. Persist names for display/XML
selection, not as workspace keys. Pause on identity mismatch, company restore/
rewrite evidence or cursor regression; require a controlled rebaseline.

Test namespaced source identity storage/query for every supported master and
voucher type. Do not assume `REMOTEID` is supported identically everywhere or
guarantees idempotency. A local mapping permits lookup, not unconditional Alter:
verify target identity, baseline version, supported edits and business policy.
Existing stock items must not be altered implicitly, particularly unit/group.
Tally's built-in Primary group must not be created as a new group.

### XML construction and amounts

Use Jinja2 with explicit XML escaping, strict missing-variable failures and
type-specific voucher templates. Model amounts as Decimal; validate a balanced
effective journal including inventory accounting allocations exactly once.
Ordinary debit ledger entries use negative Tally amounts with
`ISDEEMEDPOSITIVE=Yes`; credit ledger entries use positive amounts with
`ISDEEMEDPOSITIVE=No`. Validate inventory direction and voucher-specific
allocations separately using round-trip fixtures for every supported type.

Require confirmed party, purchase/sales, applicable GST, nonzero round-off and
charge ledger mappings. GST tax choices must come from Duties & Taxes or its
descendants. Missing business values block XML generation. Use 0.01 as the stated
money tolerance while still surfacing discrepancies; do not silently rebalance a
voucher or use fallback ledgers. Preserve required GST metadata and source
descriptions without changing persisted business content during rendering.

### Response handling

Parse supported response envelopes, counters and detailed error text. Nonempty
LINEERROR/LASTIMPORTERROR, positive error/exception counters, cancellation,
malformed XML and ambiguous counters must not be treated as confirmed success.
Show actionable text, not raw RESPONSE XML, in user-facing errors.

Import responses do not guarantee GUID/MASTERID/ALTERID for every entity.
LASTVCHID is a possible voucher lookup hint, not a full identity result. Follow a
successful-looking import with a company-scoped read-back of identity, version
and canonical supported content. Do not synthesize missing IDs or advance an
application-success state before verification. Begin with one voucher per
request; batch imports require safe per-record outcome attribution.

Configure lxml without external entity resolution, network fetching or DTD
loading. Keep strict parsing. A narrow compatibility filter may remove only
proven invalid XML control characters/references, including decimal and hex
forms, with redacted audit evidence. Do not broadly strip all low-numbered
references, enable silent recovery, or rewrite meaningful names/descriptions.
Outbound invalid business strings must be rejected or explicitly corrected.

### Incremental Tally reads

Validate TDL collections and AlterID semantics on supported Tally releases.
Use company-scoped streams for masters/vouchers or finer scopes as verified;
do not assume a common global cursor. Define deterministic ordering, tie handling
and a bounded high-water mark before advancing capture checkpoints. Capture every
record in the interval durably, including blocked/unsupported outcomes. Advancing
to the largest observed ID without proving interval coverage is forbidden.
Deletion/cancellation detection needs a separate verified strategy; absence from
an ordinary collection is not proof of deletion.

## 7. Queue, scheduling and recovery

Use SqliteHuey with one thread worker and persistent storage. All Tally access
must use the same serialized execution path. Pin and test Huey's embedded
consumer lifecycle and signal handling with Qt on Windows; do not assume calling
`Consumer.run()` in an arbitrary daemon thread works safely. The compatibility
spike must select a supported embedding method before application construction.

Cloud polls default to 60 seconds; Tally capture defaults to 120 seconds in modes
that support polling. Huey periodic checks are minute-based; any 30-second option
requires a separately tested trigger. Sync Now and health-check timers enqueue
work only. Coalesce repeated triggers and avoid accumulating offline cycles.
Keep tasks bounded so bulk work does not indefinitely starve checks/manual work.

Huey executes durable operation IDs, not credentials or arbitrary raw-log replay.
Capture operations, outbox entries and checkpoints in one metadata transaction;
the Huey database is not part of that transaction. Recover missed dispatches and
expired operation ownership on startup. Duplicate queue messages must be harmless.

### Operation lifecycle

```text
PENDING -> VALIDATING -> APPLYING -> VERIFYING -> SUCCEEDED
               |            |           |
               v            v           v
            BLOCKED   OUTCOME_UNKNOWN -> RECONCILING

Known-safe transient failure -> RETRY_WAIT -> PENDING
Concurrent edit              -> CONFLICT
Exhausted policy              -> FAILED
Backend acknowledgment       -> ACK_PENDING -> SUCCEEDED (when supported)
```

Record every write attempt before sending. Save returned target identity
immediately, verify by read-back and record completion. Acknowledgment failures
retry only acknowledgment, never voucher creation. Distinguish completed capture
from completed target application.

For Tally-to-Bahi invoices, DRAFT creation and accounting posting are separate
operations with separate attempts. A draft-stage success is not posted success.
The known-ID `/post` action is documented as repeatable; draft creation is not
therefore idempotent. On a lost create result, search and inspect candidates, but
do not treat no match or name equality as proof that another create is safe.

Read/reconcile before replaying uncertain writes. Remain visibly blocked if
authoritative resolution is unavailable. Preserve server recovery failures for
administrator investigation: MyISAM compensation does not provide crash atomicity.

Configure bounded exponential backoff/jitter for known-safe transient retries,
compatible with the selected Huey version. Authentication, missing mappings,
accounting validation, version conflicts and configuration failures need action.
Do not implement unconditional retries around all POST/PATCH requests or a bulk
Retry Failed button that bypasses eligibility checks.

## 8. Echo suppression, conflicts and initial baseline

Keep acknowledged source/target versions and normalized business-content hashes.
Compare supported canonical fields, excluding transport/audit volatility. A
GUID/AlterID equality check can help classify an observed version but is not the
complete cross-system echo protocol. Propagate verified origin metadata only
through a documented backend extension, not unknown CRUD fields.

Before updating a mapped entity, compare both sides with their acknowledged
baseline. Concurrent changes enter CONFLICT; default to explicit resolution,
never silent last-write-wins. With no server conditional version API, disable
unattended two-way PATCH rather than claiming read-compare-write is race-free.

Baseline setup requires a chosen historical period, confirmed entity links and
mapping review. Existing names/GSTIN/document references are candidate matches;
ambiguous results need an explicit link. Do not bulk-create against an existing
company without a matching strategy. Posted accounting vouchers are not silently
overwritten; corrections require an agreed adjustment/reversal policy.

## 9. Desktop UI and lifecycle

- Show Bahi business, Tally company identity, operating mode, connection health,
  paused/offline state, last successful transfer and operation counts separately.
  Reachability is not proof of posting readiness or completed synchronization.
- Provide Sync Now, Pause/Resume, Settings, mappings, operation details,
  Reconcile Unknown and eligible Retry actions. Require saved configuration and
  confirmed write policy before mutation. Show exact blocking issues.
- Use QTableView with a model and bounded/paged history rather than an unbounded
  QTableWidget/per-row action-widget collection. Refresh asynchronously.
- Health checks may target ten-second intervals, but must coalesce, use the same
  Tally request path and avoid stale callbacks overwriting a new binding/status.
- Settings include configured deployment URL/key entry, Tally endpoint/company,
  history period, validated intervals, direction/mode and opt-in Windows startup.
  Never redisplay a stored token in logs or ordinary settings fields.
- Emit queued QObject signals for worker events. GUI slots update widgets on the
  main thread. Treat every stale binding/generation callback as discardable.
- Retain the QLockFile for process lifetime. Do not blindly remove a live owner's
  lock; show that the connector may already be running in the tray.
- Set appropriate Qt quit-on-last-window behavior. Tray includes Open Dashboard,
  Sync Now, Pause/Resume and Quit Connector; show close-to-tray notice sparingly.
- Quit stops new scheduling, prevents new writes, waits within bounded network/
  lifecycle limits, preserves unresolved attempts and closes resources. Killing a
  daemon thread is not the recovery strategy. Login startup runs as the user,
  not as a Windows service.

## 10. Packaging and support

Provide `scripts/build_exe.py`, `packaging/pyinstaller/connector.spec` and
`packaging/inno_setup/installer.iss`.
Package with no console and application name `InnoforaiTallySync`; bundle
templates/icon explicitly and resolve assets correctly from source and frozen
execution through the resource-access helpers in `config/paths.py`. Correctly
bundled package-relative resources may use `__file__` or `importlib.resources`;
a `_MEIPASS`-first branch is not mandatory. Include Tally templates and resource
data at their expected package locations. Explicitly imported Python migration
modules are code; SQL or other migration assets must be included as data. Test
these paths from source and frozen builds without depending on the current
working directory. Include the required Qt plugins. Verify the build on a clean
supported Windows machine without an external Python installation.

Installer/startup actions must respect standard-user permissions and explicit
startup preference. Include versioned migrations, a consistent pre-migration
backup and tested recovery instructions. Do not erase runtime data on upgrade
or ordinary uninstall. Record the code-signing/distribution approach for release.

Rotate/redact logs. Store only necessary operation snapshots with restricted
local access and agreed retention; log summaries/hashes by default. Diagnostic
payload capture and support export are explicit actions with secrets and
unnecessary customer details removed. Raw log payload is not executable retry input.

## 11. Acceptance tests and release gates

Use isolated temporary SQLite databases, mocked HTTP contracts, sanitized XML/
JSON fixtures, offscreen Qt checks and opt-in disposable Tally/Bahi test companies.
Do not use production books or keys in automated tests.

Required checks:

1. Business identity/scope isolation, missing permissions, empty versus failed
   list responses, direct PHP/post-path routing and explicit invoice statuses.
2. Complete pagination, shifting pages, old edits, unsupported records and safe
   checkpoints. Never claim snapshot guarantees that the backend lacks.
3. Metadata-only item updates, existing UOM/group dependencies, no implicit
   stock balance writes and no ambiguous automatic master links.
4. Purchase and later Sales/note round trips: dates/references, exact prices,
   discounts, GST rounding, inventory direction, ledger signs and balances.
5. Repeat event/Sync Now, duplicate queue dispatch, failed ack, lost create result,
   repeated known-ID posting, conflicting edits and server recovery failure.
6. Terminate at each write boundary: before send, after target commit/before local
   commit, after identity persistence and during reconciliation. Recover without
   lost durable work or duplicate business effects in the tested cases.
7. Tally offline/busy, network timeout, non-JSON/redirect responses, malformed XML,
   LINEERROR, exception-only counters, SQLite contention and disk-full behavior.
8. Binding switch/rename, restore/cursor regression, app restart, sleep/resume,
   tray absence, second instance and bounded shutdown without GUI freezes.
9. Clean install, frozen assets, optional login startup, upgrade with pending work,
   backup recovery and retained data on uninstall.

Accounting review must approve each supported voucher type. Benchmark actual
throughput and UI responsiveness; do not promise the proposal's timings without
measurement. Automatic mode remains disabled until its backend/recovery gates
pass. A runnable UI/mock demo is not a completed live synchronization product.

## 12. Instructions for implementation work

This revision replaces the earlier request to generate every module at once.
Implement complete, tested milestones with explicit capability boundaries:

1. **Phase 0:** Agree scope/contracts; validate Tally identity/read-back/AlterID
   queries; prove Qt/Huey startup, scheduling, stop and a minimal Windows build.
   Produce sanitized evidence and unresolved dependency decisions.
2. **Foundation:** Paths, secure credentials, migrations/operations/outbox,
   connection/read adapters, single-instance lifecycle and usable basic UI.
3. **Purchase slice:** Existing confirmed party/item/UOM mappings; one ordinary
   untracked purchase each way; DRAFT/post separation; duplicate/unknown-result
   handling and verified read-back. Backend-dependent behavior stays gated.
4. **Expansion:** Master creation with required data and confirmed policy, Sales,
   supported notes, mappings/conflicts, diagnostics and packaging.
5. **Production:** Backend synchronization guarantees, fault/recovery gates and
   reconciled pilot approval. Receipt/Payment waits for its own API contract.

Each implemented milestone must run without TODO-only behavior or simulated
success in production paths. Include run/test/build commands, validation results
and remaining capability limits. Do not generate guessed endpoints or silently
weaken accounting/recovery rules to satisfy an all-files-complete requirement.

## 13. References and authority

See the [documentation index](README.md) for reading order and document ownership.

- [Business setup handbook](api/bahi/handbooks/API-BIZ-SETUP-CHECK-HANDBOOK.md)
- [Party handbook](api/bahi/handbooks/API-PARTY-DEVELOPER-HANDBOOK.md)
- [Item-group handbook](api/bahi/handbooks/API-ITEM-GROUP-DEVELOPER-HANDBOOK.md)
- [Item handbook](api/bahi/handbooks/API-ITEM-DEVELOPER-HANDBOOK.md)
- [Invoice handbook v2](api/bahi/handbooks/API-INVOICE-DEVELOPER-HANDBOOK_v2.md)
- [Huey API reference](https://huey.readthedocs.io/en/stable/api.html)
- [Huey consumer reference](https://huey.readthedocs.io/en/stable/consumer.html)
- [Tally import/XML reference](https://help.tallysolutions.com/sample-xml/)

This revision governs the updated implementation requirements; handbooks govern
the documented wire contracts. Reference examples are not instructions to run
migrations, write to live businesses or expose credentials. Resolve deployment
differences explicitly and record them before enabling affected actions.
