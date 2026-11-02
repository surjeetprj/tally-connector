# Read-only party discovery and local linking

Implemented 2 November 2026 for Bahi business 52 and the verified SIS Dummy GUID.
This source application reads existing parties, compares observations and stores
explicit local identity links. It has no remote create/update/delete/post actions.
The earlier [foundation slice](READ_LINK_FOUNDATION.md) remains historical evidence.

## Run and use

Use the existing project environment:

```powershell
.\.venv\Scripts\python.exe -m innoforia_tally_connector
```

Runtime files use `%LOCALAPPDATA%\InnoforaiTallySync\`. An explicitly isolated
directory can be selected for verification with `--runtime-dir`; the live UI
walkthrough used ignored `build/live-party-ui/`. Neither location imports or
replaces the Phase 0 journals. Existing credentials are read from their established
Windows Credential Manager reference; there is no new credential entry flow.

1. Choose **Verify connections**. The business name/ID and company name/GUID must
   match the expected pair before proceeding.
2. Select the observed customer and supplier group roots, then confirm the pair
   and groups. On 2 November the user confirmed **Sundry Debtors** for customers
   and **Sundry Creditors** for suppliers, including descendants, for read-only
   classification. This is not a party mapping or permission for future writes.
3. Choose **Load / Refresh parties**. Review each source's observation time,
   successful/failed page coverage and classification exclusions. Complete page
   coverage does not establish a stable snapshot.
4. Review all matching suggestions or select one observed record on each side,
   including pairs with different names. Review field differences, enter the
   confirming reviewer and explicitly confirm the local identity link. Inactive
   Bahi parties remain visible but cannot be linked in this slice.
5. Inspect **Saved local links** after reopening and re-confirming the pair.
   History is paged in batches of 200; previous/next controls never remove history.
   Close hides to the tray when available. **Quit connector** stops scheduling and
   closes background resources; when no tray is available, the window stays usable.

No first candidate is selected automatically. Link confirmation re-reads both
identities and rejects changed classifications, versions, content or stale details.
Differences stay separate; no equal-content acknowledgment or overwrite permission
is created. Binding/group policy changes require a separately reviewed migration.

## Architecture and storage

The [bootstrap](../../src/innoforia_tally_connector/bootstrap/dependencies.py)
constructs separate persistent HTTPX clients and one shared serialized Tally
gateway. Bahi enables only business-check and party GET routes. Tally constructs
export-only XML and validates it before sending. Both use bounded timeouts,
disabled redirects and an 8 MiB response cap; Bahi scans stop at 100 pages of 200
records with an explicit incomplete result. Credentials are frozen per logical
read so replacing the stored key cannot silently change a scan's business scope.

Company discovery, identity checks, group reads and ledger reads use the same
gateway and background execution. A bounded gateway lock reports busy rather than
starting another request. The UI only dispatches commands and consumes queued
events; binding generation and request identity reject stale results.

The shared execution path uses one SqliteHuey thread worker. A local command and
outbox entry commit together; queued arguments contain operation IDs only. Startup
repairs dispatch gaps and safely redispatches reads before starting the consumer.
Binding-sensitive recovered work remains blocked until the pair is explicitly
re-confirmed; use a new Load/Refresh after reopening rather than displaying an old
session's result as current.
Interrupted local confirmations require renewed review unless the mapping audit
establishes their commit. Duplicate delivery cannot claim a finished operation.

Metadata v2 adds confirmed setup evidence, command records and an outbox. Upgrades
take a SQLite-consistent backup, including committed WAL data, under the process
instance lock. Schema changes and `PRAGMA user_version` commit together. Existing
links/audits and earlier JSON observations remain readable; defaults do not turn
absent fields into explicit nulls. Metadata and Huey's queue are separate databases.
No remote write-attempt or acknowledgment capability is enabled by these tables.

Startup/migrations, request capture, network work and SQLite waits run outside the
GUI thread. HTTP clients and queue resources close after bounded worker shutdown.
Logs rotate and record counts, safe errors and operation IDs rather than payloads.

## Executed evidence

| Check | Result | Limit |
| --- | --- | --- |
| Company/group/ledger exports | Known company GUID; 28 groups, 60 ledgers; every group parent resolved | Single loaded company/release 6.2 only |
| GUID detail lookup | All 60 ledgers matched collection observations; missing GUID returned no records | No name fallback; live rename was not performed |
| Invalid company export | Returned no records | Not certification of multiple loaded companies or restore behavior |
| Live Bahi party reader | One party, one page; detail matched observation | Larger/concurrently edited pages tested offline only |
| Live Tally party reader | 48 parties, 12 other ledgers excluded; all 48 details matched | Standard roots initially experimental, subsequently user-confirmed for classification only |
| Native Windows screen | Verified pair, user-approved roots, one Bahi party/48 Tally parties/one suggestion loaded; clean Quit | One local setup saved; zero real party identity links seeded |
| Synthetic native walkthrough | Selected the second ambiguous candidate, confirmed locally, restarted and recovered the saved link | Synthetic records and temporary metadata; no remote effects |
| Offline regression | 90 passed; one opt-in live check skipped by default | No installer/frozen certification |
| Opt-in integration | One live GET/export test passed | Reads only; sanitized evidence in a temporary directory |

Sanitized [Tally query evidence](../api/tally/evidence/party-read-probes.json) and
[adapter read evidence](evidence/live-discovery-reads.json) contain counts, field
names, coverage and comparison outcomes, not customer payloads or keys. Native
test screenshots remain ignored under `build/`; they are not customer-data assets.

The offline suite covers paging failures/duplicates/limits, malformed responses,
redirects, wrong identities, classification descendants/overlap/cycles, exact GUID
lookup, rename fixtures, inactive detail rejection, missing/null preservation,
concurrent gateway serialization, GUI heartbeat during network/SQLite waits,
single-instance protection, outbox recovery, duplicate claims, local commit before
completion, migration backup/rollback, saved-link paging and architecture boundaries.
Existing matching query bounds remain 2/200/2,000 for 1/100/1,000 records per side.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
# Explicit opt-in: actual Bahi GET and Tally export requests, no mutations.
$env:CONNECTOR_LIVE_READS = '1'
.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_live_party_discovery.py
Remove-Item Env:CONNECTOR_LIVE_READS
```

The source environment and dependency versions were reused unchanged. `pip check`
passed. No lint/format command is configured. No installer or frozen build ran.
Invoice 69 and all earlier posting/recovery journals remain untouched.

## Observed protocol details and remaining gates

Tally ledger GUIDs in this release have a company UUID plus an eight-hex suffix;
query literals are validated against that observed shape. Company names are
resolved from the expected GUID before scoped reads; a changed context rejects the
result. GUID/AlterID and available MasterID are retained as observation metadata.

Root-group parents contain the invalid XML sentinel `&#4; Primary`. Only that
exact Primary-parent sentinel is normalized, with a safe count log. Other invalid
controls, DTDs/entities and malformed XML are rejected. Optional email, ledger
phone, GSTIN, PIN and state fields use their observed tags without rewriting their
values. Address remains explicitly unavailable on the Tally side; no flattening
or inferred substitute is enabled. Field presence/read-back is not tax validation.

MD-02 has a confirmed read/link classification for this pair; mutation policies
and unsupported field/type decisions remain open. This is the party subset of
MST-002/MST-003, not completion of group/item/unit discovery or master transfers.
Actual production identity links still require owner review. Restore/deletion
detection, lossless snapshots/change feeds, backend idempotency/versions/origin/
ownership, broader foundation fault tests, clean-machine packaging and frozen
Python 3.13 checks remain pending. A pre/post company check is not a remote atomic
snapshot or a cross-PC ownership guarantee.

Next: review actual candidate identities with the owner using this screen, retain
explicit local links only where confirmed, and prepare the separately authorized
party create/update/read-back experiments before enabling any master write.

Implementation references: [SQLAlchemy SQLite transactions](https://docs.sqlalchemy.org/en/21/dialects/sqlite.html),
[HTTPX streaming](https://www.python-httpx.org/quickstart/#streaming-responses) and
[Huey API](https://huey.readthedocs.io/en/stable/api.html). The installed Huey 3.5.3
source and existing spike were checked because current stable docs describe 3.5.4.
