# Read/link foundation slice

Implemented 31 October 2026; matching performance updated 2 November 2026.
This records the initial offline-tested party discovery/linking core. The
subsequent [read-only desktop milestone](READ_ONLY_DISCOVERY.md) now supplies
guarded readers, bootstrap, background execution and a native review screen.
Sections below describe the initial slice's evidence and then-pending gates;
use the current report/state for implemented capabilities. No remote master
mutation capability is enabled.

## MST-001 review

Read scope is CUSTOMER/SUPPLIER identity, classification evidence, name and
optional contact/GSTIN/address/state/PIN observations. Missing values differ from
explicit nulls; phone and PIN remain strings. Balance and stock fields cannot be
included in the canonical party content. These are observation fields, not a
write allowlist. Group/item/unit discovery and transfers remain pending.

MD-01 through MD-07 in the [decision register](MASTER_SYNC_DESIGN.md#decision-register)
remain open. The current request authorizes building confirmed-link functionality;
it does not confirm a particular business mapping, Tally party group, field owner
or mutation policy. No production mapping is seeded. Confirmation records a named
reviewer and review reference, two identities and separate observations. It grants
no direction or overwrite authority and creates no acknowledged equal-content
baseline. A later write preview must obtain its own reviewed policies.

| Prerequisite | Evidence / status | Consequence |
| --- | --- | --- |
| CON-001 / BAH-001 | Supplied contracts and sampled Bahi reads; required master field matrix documented; no signed ownership/classification policy | Party read/link core only; all remote writes unavailable |
| CON-002 | Company GUID, collections and selected AlterID filters observed; per-record canonical/classification reads, imports and restore behavior still pending | No production Tally party reader claimed |
| CON-003 | Historical 3.12 source/frozen checks; fresh 3.13 source lifecycle passes eleven assertions | Frozen 3.13 and clean-machine gates still pending |
| CON-010 | Editable package installed; pytest configured and running | No application entry point, CI or production installer yet |
| CON-011 | Dedicated metadata v1 initialization, binding generations, unique local party links and atomic confirmation audit | Operation/attempt/outbox/recovery engine and schema upgrades/backups still pending |
| CON-012 / BAH-002/003 | Existing experiment credential/read scripts; application read-only ports now defined | Production credentials/clients and guarded readers still pending |
| CON-013 | No production UI/controller/bridge | Full read-only and supervised-link release gates remain open |

The application [ports](../../src/innoforia_tally_connector/application/ports.py)
require readers to verify the authenticated business and company identity and
provide classification evidence. Implementations must use documented Bahi GET
contracts and the shared background Tally gateway. Requested context alone is not
verification. Fixture readers in tests are synthetic and do not verify live APIs.

## Local behavior and verification

[Discovery](../../src/innoforia_tally_connector/application/masters/parties.py)
rejects wrong-context scans, retains incomplete coverage and observation times,
and returns every same-classification name/GSTIN candidate. Case/spacing changes
are search-only. Already linked identities are excluded from new suggestions;
saved links can be retrieved by either identity. Duplicate identities across
pages invalidate the scan. Even complete page coverage is not a stable baseline
unless the reader has evidence of stable snapshot semantics. Bahi currently lacks
that guarantee. Safe read failures must propagate or be represented as failed
pages; they must never become an empty successful baseline.

The 2 November review fix checks mapping eligibility once per observed identity,
only within the current discovery call. Eligible Tally records are indexed by
classification plus normalized name and by classification plus exact nonempty
GSTIN. Ordered index lists are merged with duplicate positions removed, preserving
Bahi order, Tally order, ambiguity and `name` then `gstin` reason order. A pair
matching both criteria appears once with both reasons. GSTIN is not normalized.
Mapping lookup failures propagate. A later discovery call checks eligibility
again; cached suggestions never replace confirmation's detail/uniqueness guards.

Real SQLite query instrumentation reproduced 10,100 mapping SELECTs for 100
unlinked records per side before the fix. The final regressions measure:

| Records per side | Mapping SELECTs | Candidates in disjoint-name/GSTIN fixture |
| --- | ---: | ---: |
| 1 | 2 | 0 |
| 100 | 200 | 0 |
| 1,000 | 2,000 | 0 |

The regression also rejects any SQL other than mapping SELECTs during discovery.
These counts cover discovery after temporary schema/binding setup, not runtime
initialization. Large genuine match sets still require emitting every candidate;
this change does not impose a limit or choose one ambiguous match automatically.
Public interfaces, storage schema and confirmation behavior are unchanged.

[Confirmation](../../src/innoforia_tally_connector/application/masters/mappings.py)
re-reads both selected identities before opening the local transaction. Changed
content, versions, classifications or context require another review. Stale/future
detail timestamps fail. This narrows stale-link risk but does not make two remote
reads atomic. Only identity is linked; remote fields remain untouched.

[Storage](../../src/innoforia_tally_connector/persistence/repositories/party_links.py)
requires an explicitly registered binding. Both identities are unique within a
binding generation across customer/supplier classifications. Another confirmation
cannot silently replace history. Evidence and audit commit together. Each side's
snapshot remains separate, including unequal initial content and missing/null
distinctions. Repeated confirmation reports a conflict; it creates no second link.

The dedicated metadata engine uses WAL, FULL durability, foreign keys and a
five-second busy timeout. The migration runner uses an explicit numbered registry,
transactional DDL and `PRAGMA user_version`, and rejects newer/unrecognized
databases. Run initialization under exclusive startup ownership before workers.
Only empty-database initialization and same-version reopening are delivered;
upgrades need SQLite-consistent backups before they can be enabled. This does not
migrate Phase 0 journals or Huey's queue database. The eventual runtime location
remains `%LOCALAPPDATA%\InnoforaiTallySync\`.

SQLite transaction configuration follows the official
[SQLAlchemy SQLite documentation](https://docs.sqlalchemy.org/en/21/dialects/sqlite.html#enabling-non-legacy-sqlite-transactional-modes-with-the-sqlite3-or-aiosqlite-driver),
with real rollback/process-exit tests rather than relying on DDL examples alone.

Run all configured offline tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

On 2 November, 35 focused matching/persistence tests and all 51 configured offline
tests passed, including the 15 Phase 0 tests. The initial slice had 41 tests.
Cases cover ambiguous matches,
duplicate GSTIN candidates, wrong binding/generation, changed/stale observations,
incompatible classifications, leading zeroes, missing/null, forbidden balances,
partial paging, concurrent unique-link confirmation, restart retrieval, atomic
audit rollback, migration exception and abrupt process exit, foreign/newer schema
rejection and package import boundaries. The matching fix adds measured query
bounds, exact candidate/reason ordering, linked-record exclusion, dual-match
deduplication, exact GSTIN handling, invalid context before lookups, propagated
lookup failures, per-call eligibility refresh and preservation of partial scan
metadata. All master observations are synthetic
test fixtures; no customer snapshots or secrets were committed.

## Environment repair

The former `.venv` pointed at unavailable Python 3.12.8. It is preserved as ignored
`.venv-python312-unavailable/`. The new `.venv` uses installed Python 3.13.15.
Sandbox launches cannot access that base interpreter, so verification ran through
approved execution outside the sandbox. `pip check` passed. Qt/Huey source seed
and run used a fresh ignored `build/master-read-link-python313-spike/` directory;
all eleven assertions passed. Its expected retry exception is intentional.
See [sanitized source evidence](../phase0/evidence/qt-huey-source-313.json).
Earlier journals and frozen artifacts were not replaced.
The matching-only fix reused this environment and installed no dependencies;
Qt/Huey lifecycle and frozen checks were not repeated for that fix.

[requirements-dev-lock.txt](../../requirements-dev-lock.txt) records this Windows
Python 3.13 source/test environment, including packaging dependencies. It excludes
the editable project itself. Reproduce with the selected interpreter:

```powershell
python -m pip install -r requirements-dev-lock.txt
python -m pip install --no-deps --no-build-isolation -e .
```

This is not a certified production/frozen lock. The historical Phase 0 lock and
3.12 frozen evidence remain unchanged. No installer build or live Bahi/Tally call
ran in this milestone. Runtime journals and retained Bahi invoice 69 were untouched.

## Next controlled read-back experiments

Before implementing the Tally reader, recheck SIS Dummy's known GUID and keep all
requests export-only. Establish company-scoped single-ledger lookup by GUID,
GUID/MasterID/AlterID/name read-back, parent-group ancestry, dual-role/unsupported
classification handling, optional fields and missing-identity behavior. Preserve
sanitized XML fixtures after observing exact tags; current collection evidence
does not prove these additional queries. Company mismatch must stop the scan.

Implement Bahi business-check and party list/detail readers against supplied
contracts, with explicit page coverage and concurrent-edit limitations. Do not
claim a lossless snapshot from total_pages or timestamps. Connect both readers via
background execution and a native review screen before claiming MST-002 complete.
Then verify confirmed-link restart behavior through that screen for MST-003.

Create/read-back experiments remain prepared, not authorized or executed: obtain
reviewed disposable test identities and exact customer/supplier groups and fields,
record intent before each import, then verify stable identity/classification and
every enabled field. Unknown outcomes must block another create. Do not invent
XML import tags or reuse posting invoice 69. Group/item experiments additionally
need confirmed parent/unit/manufacturer/price/tax inputs under MD-04/05/06.
