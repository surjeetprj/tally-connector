# Master sync validation

Status: acceptance plan. Every case below is **NOT RUN for the production master
workflow**. Existing Phase 0 read probes are limited evidence, not passing master
mutation or recovery tests. See [Tally evidence](../api/tally/README.md) and
[Bahi live reads](../api/bahi/LIVE_VALIDATION.md).

## Evidence levels and test environment

| Level | What it proves | What it does not prove |
| --- | --- | --- |
| Supplied handbook | Documented Bahi wire contract | Deployment compatibility or permission to write |
| Offline fixture/test | Parsing, validation and local workflow behavior for the fixture | Actual remote semantics |
| Controlled live experiment | Observed behavior for the selected type/version/company/business | All other types, releases or crash timings |
| Recovery experiment | Behavior at the explicitly injected failure boundary | Universal exactly-once execution |

Use a disposable Bahi business and disposable Tally company or explicit bounded
test records under separately established authorization. Business 52 posting
authorization and retained invoice 69 do not authorize arbitrary master changes.
Do not reuse or reverse that invoice as a master test. No live writes are made
by preparing this plan. Use the selected project interpreter after repairing the
currently unavailable base-interpreter reference in the existing .venv.

Before each live write, prepare the target identity, exact test fields, expected
canonical result and intent journal. Confirm permissions for only the intended
party/item actions; no invoice/post/delete scope is needed for this milestone.
Retain test records unless an explicit cleanup plan authorizes removal.

## Controlled experiments

| ID | Experiment | Acceptance evidence |
| --- | --- | --- |
| MV-01 | Read complete supported master lists/details from both sides | Binding guard, recorded scope/page coverage and identities; incomplete scans clearly marked |
| MV-02 | Create one CUSTOMER and one SUPPLIER in each direction | Correct classification, returned/located stable ID and matching allowlisted content read-back; no balances changed |
| MV-03 | Create root and child groups in each direction | Verified parent mapping, required values explicit, no Primary creation and no hierarchy cycle |
| MV-04 | Create one supported untracked GOODS item in each direction | Confirmed unit/group and required Bahi fields; tax/type/price representation checked; no stock balance write |
| MV-05 | Update a verified nonidentity field, then rename | Same mapped identity remains; exact field changes verified; name collision blocks safely |
| MV-06 | Observe Tally records before/after create and edit | GUID/AlterID behavior, deterministic interval coverage and relevant collection scopes; no assumed global cursor |
| MV-07 | Observe Bahi edit during and between paginated scans | Hash comparison detects observed edits; capture limits documented; no lossless-feed claim |
| MV-08 | Test optional/tax fields independently | Each enabled field round-trips with its meaning intact; unsupported fields stay disabled |

Run each type/direction independently, initially one record per request. If a
required Tally tax or service representation is unavailable, fail that capability
gate rather than insert a fallback ledger or silently drop data. SERVICE/CHARGE
creation remains excluded until separately designed and validated.

## Offline and integration acceptance cases

| Area | Required cases and expected behavior |
| --- | --- |
| Matching | Same name/different identity; duplicate GSTIN; duplicate group names; multiple candidates; explicit link required |
| Mapping persistence | Unique source/target constraints; concurrent confirmation; wrong binding rejected; original operation context retained |
| Field validation | Missing manufacturer/price; invalid unit; decimal precision; omitted versus null; phone/PIN leading zeroes; XML escaping and invalid controls |
| Dependencies | Parent-first order; blocked parent blocks children only; cycle rejected; Primary not created |
| Unsupported records | SERVICE/CHARGE without representation, tracking, compound units and nonrepresentable price schedules block with reasons |
| Existing items | Unit/group changes blocked; no implicit alter or quantity/balance fields in master writes |
| Lifecycle | Inactive/system party restrictions; no automatic delete/reactivate/deactivate; missing record triggers investigation |
| Baseline and conflicts | Initial differences not marked equal; source/destination changed after preview; both sides edited; reviewed resolution rechecks freshness |
| Echo prevention | Own write read-back produces no reverse write; later human edit to same ID remains detectable |
| Dispatch | Intent and outbox commit together; dispatch gap repaired; duplicate jobs and repeated clicks cause no duplicate effect |
| Architecture | Pure domain/application boundaries; no sibling feature imports; only gateway imports Tally transport; health/read/write calls serialized |
| UI/security | Background work keeps UI responsive; stale callbacks discarded; keys absent from queue/logs; no raw XML/stack traces in screens |

## Failure and recovery matrix

| Failure boundary | Required outcome |
| --- | --- |
| Crash before durable capture | Later safe read can rediscover work; no external write happened |
| Crash after intent/outbox commit, before queue dispatch | Redispatch the same durable operation ID |
| Failure before request transmission is proven | Retry only under a verified safe classification |
| Timeout or crash after write may have been sent | Retain uncertainty; reconcile before retrying |
| Target committed, local mapping/result not committed | Recover authoritative target identity/content; no second create |
| Response contains counters only or an ignored field | Follow-up lookup/read-back required; mismatch is not success |
| Backend outcome lookup absent and result ambiguous | Keep operation visibly unresolved; unattended recovery gate fails |
| 401/403, invalid references or invalid payload | Require action; do not repeatedly retry |
| Read-only 429/5xx or connection unavailable | Bounded safe backoff; no growing duplicate cycles |
| Disk full/SQLite busy after target write | Preserve attempt/recover from available durable intent; no blind recreation |
| Company restore, changed binding or cursor regression | Pause writes and require investigation/rebaseline |
| Concurrent editor or second connector | Expected-version/lease contract rejects stale/competing writes, or automated mode remains disabled |

## Evidence to retain

For each executed case, record case/type/direction, tool/runtime/Tally versions,
binding identity, intent/operation reference, request schema/template revision,
safe response summary, verified target identity, per-field comparison and observed
limitations. Keep necessary raw business snapshots in restricted ignored runtime
storage, not Git. Committed fixtures/evidence must be synthetic or sanitized;
never publish keys, addresses or customer payloads just to make a test reproducible.

No runnable master XML examples are provided yet: exact tags and source-identity
lookup remain unverified. Attach sanitized request templates and read-back
fixtures as the adapter experiments establish them, with evidence labels.

## Completion gates

**Read-only gate:** correct binding, honest coverage, clear matching suggestions
and no writes. **Supervised link gate:** confirmed identity mappings survive
restart without changing remote data. **Supervised write gate:** each enabled
type/direction passes create/update/read-back and applicable recovery cases;
unresolved cases remain visible and block replay. Any concurrency/recovery gap
must be stated as a limitation, not counted as verified safety.

**Automatic gate:** additionally prove backend snapshot/change-feed handoff,
idempotency/outcome lookup, conditional versions, origin/ack and writer ownership,
plus complete Tally change capture/restore handling. Mocks cannot pass this gate.

The [implementation plan](../IMPLEMENTATION_PLAN.md#master-first-work-packages)
owns task progression. Run focused checks while developing and the full configured
regression suite at milestone completion; do not run live scripts as offline tests.
