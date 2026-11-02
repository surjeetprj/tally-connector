# Current state and progress

Last updated: 2 November 2026.

## Active milestone

**Read-only party discovery and local-link desktop slice implemented.**
MST-002/MST-003 party capabilities have live reader and native-screen evidence;
broader master types, actual owner-reviewed party links and all writes remain gated.
CON-001 has live read/write evidence and a proposed backend contract handoff.
CON-002 has baseline/populated Tally reads; Tally imports remain untested.
CON-003 source/frozen checks passed on 3.12; source lifecycle was rechecked on 3.13.
The full product, clean-machine certification and automatic sync are not complete.

## Authorization and environment

- The user explicitly authorized controlled purchase posting in Bahi business 52
  and asked to fix packaging/recovery issues. Do not request that authorization
  again for the same test. It does not authorize deletion of unrelated history.
- Bahi base: `https://innoforia.com/201/h-bahi/bahi/web-api/`. Authentication verified
  biz_id 52, matching the SISOFT Technologies Private Limited dashboard. The key
  is in Windows Credential Manager under
  `InnoforiaTallyConnector/Phase0/Bahi/innoforia.com/201/h-bahi`; never log it.
- Tally: `http://localhost:9000`, release 6.2, SIS Dummy GUID
  `0b212ad8-3be5-45fe-8719-e1a70e240d4c`, company number 100006. Educational mode
  is user-reported; transaction-date restrictions have not been write-tested.
- Bahi and Tally data differ. No production cross-system master mappings were
  confirmed, and no bulk alignment or historical overwrite is authorized.
- On 2 November the user confirmed Sundry Debtors as customers and Sundry
  Creditors as suppliers, including descendants, for this pair's read-only
  classification. This does not confirm any individual party link or write policy.
- Bahi is company-owned; the user can arrange new endpoints but currently has no
  authoritative backend source. Do not inspect the excluded local `bahi` testing
  directory as a substitute. Use handbooks and live responses; server changes
  need authoritative source or the backend developer.

## Latest repository update

Implemented guarded Bahi party GETs, serialized Tally export readers, native
review/link UI, source entry point, Credential Manager retrieval, instance lock,
rotating redacted logs and background startup/shutdown. Metadata v2 adds confirmed
setup and durable operation-ID/outbox execution through one Huey thread worker.
Upgrades back up committed SQLite/WAL state and retain existing links/audits.
Restart safely rediscovers reads; interrupted confirmations require renewed review
unless their local mapping audit proves completion. Missing/null observations stay
distinct through journal serialization. Saved-link inspection is paged at 200 rows.

Live Tally queries verified 28 groups and GUID-based detail read-back for all 60
ledgers; missing GUID and invalid company reads returned no records. Ledger GUIDs
use a UUID plus eight-hex suffix. A narrowly verified Primary-parent XML sentinel
is normalized; other invalid XML/controls/entities are rejected. Address remains
unavailable on the Tally side. Live reader checks observed one Bahi party and 48
Tally parties, with 12 other ledgers excluded; all selected details matched.
See [implementation, usage and evidence](master-sync/READ_ONLY_DISCOVERY.md).

Offline regression: **90 passed, 1 opt-in live test skipped**, including Phase 0 and the indexed matching
query-count checks. Opt-in live GET/export integration: **1 passed**. Native Windows
walkthrough verified an explicit second ambiguous synthetic candidate, local
confirmation, restart and saved-link retrieval. Actual source-app startup and
connection verification passed through Windows UI automation; Quit closed cleanly.
After the user's root confirmation, the live screen loaded one Bahi party, 48
Tally parties and one suggestion. The live UI uses ignored `build/live-party-ui/`;
its database contains one confirmed setup and zero real party links.

Reused Python 3.13.15 and all installed dependency versions; `pip check` passed.
Python/network checks required approved execution outside the sandbox. No
lint/format command is configured. Frozen/installer checks were not run.
Final checks passed: 44 changed/new Python files parsed, two sanitized evidence
JSON files validated, 14 Markdown files/131 local links and anchors checked,
all task-file whitespace checked and `git diff --check` clean. Handbooks unchanged.
No remote mutation or invoice/posting experiment ran. Existing Phase 0 journals,
invoice 69 and supplied handbooks are intact. MD-02 is confirmed only for this
pair's read/link classification; write and unsupported-field/type policies remain
open. Broader Phase 0/foundation/automatic gates are incomplete.

## Implemented scope

Source application, party readers, background review and durable local linking
now exist. Source launch: `.\.venv\Scripts\python.exe -m innoforia_tally_connector`.
Inspect source for actual implemented APIs; the specification remains a target
for deferred master types, accounting transfers and broader operational features.

- Bahi GET probe verified business, supplier, group, item and purchase contracts.
- Tally baseline and populated AlterID probes verify the observed query behavior.
- Credential entry uses a masked local window and Windows Credential Manager.
- Controlled Bahi draft/PATCH/post/repeat-post and known-ID client-crash recovery
  scripts retain durable local write intent and refuse uncertain create replay.
- Qt/Huey spike verifies local persisted tasks, retry, serialization, queued signals,
  heartbeat, idle stop and assets. A reproducible isolated-PATH build fixes the
  foreign ICU DLL that caused the earlier QtCore import failure.
- Party read/link source workflow has live reader/native UI evidence. Full
  MST-002/MST-003 coverage for other masters, CI/frozen foundation checks and
  production mapping review remain pending. No external-write attempt engine exists.

## Verification and material external effects

- Historically fifteen Phase 0 offline tests passed. Source/frozen Qt/Huey runs passed
  eleven runtime assertions. Python 3.12.8, PySide6 6.11.1, Huey 3.5.3,
  PyInstaller 6.21.0 and hooks 2026.6 form the historical packaging baseline.
- Fixed executable: `build/phase0-fixed-dist/ConnectorPhase0/ConnectorPhase0.exe`.
  It passed seed/run from a different working directory without manual edits.
  Older failed build directories are historical outputs, not releases.
- Packaging cause: a Poppler ICU DLL was collected from the tooling PATH. The
  build wrapper isolates native search PATH; the spec rejects foreign ICU and
  relies on Windows system ICU. No system DLL was modified.
- Bahi invoice **69**, internal/reference **P0CT-261029-01**, dated 2026-10-29,
  is retained **ACTIVE**. Supplier 274, SERVICE item 84, quantity 1, test price INR
  1.00, GST 0.18, total 1.18. Item quantity remained zero across posting/repeat.
  No cancellation/reversal/deletion ran. Do not create a second copy of this test.
- A separate process intentionally exited with code 23 after a repeat post on 69,
  before recording local completion. A new process recovered by GET only, with
  zero creates/posts during recovery. Server crashes/unknown creates are not proved.
- `scripts/phase0/requirements-lock.txt` records the isolated environment; it is
  an experiment lock, not the production application's final dependency policy.
- Historical Phase 0 checks passed: 18 Markdown files, 99 local links/anchors, eleven Python
  files' syntax and consistent posting/recovery/frozen evidence. Fifteen offline
  tests pass; pip check reports no broken requirements. All five handbooks remain
  byte-identical to the supplied originals; saved JSON contains no API-key pattern.

## Remaining gates

- Tally controlled imports, per-record canonical read-back, date-range coverage,
  deletion/restore detection and uncertain Tally write recovery.
- GOODS stock movement: the available Bahi item is SERVICE, so the live test
  validates accounting-only posting. Production master mappings remain unconfirmed.
- Clean Windows packaging/installer checks, in-flight shutdown, full scheduler
  coalescing, application gateway architecture and broader fault tests.
- Backend change-feed/snapshot, idempotency/outcome lookup, conditional versions,
  origin/ack, ownership and UOM/configuration APIs. The proposed contract is written;
  review/implementation require the backend team/source. Do not enable automatic
  bidirectional mutation until guarantees are implemented and tested.

## Next concrete task

Use [the source review screen](master-sync/READ_ONLY_DISCOVERY.md#run-and-use) to
review actual candidate identities with the owner and save only explicitly
confirmed local links. Prepare bounded party create/update/read-back experiments
and required MD-01/03/05/06 decisions before enabling any master write. Groups,
items, UOM discovery/transfer and the purchase slice remain separate milestones.

Use [the backend handoff](api/bahi/SYNC_EXTENSION_CONTRACT.md) to resolve the sync
extension design with the backend developer. Continue CON-002 read-back/import
experiments in SIS Dummy with explicit test mappings; keep unknown outcomes visible.
Proceed toward the foundation with the tested embedding/build recipe, without
claiming that these experiments implement the production app or complete every
Phase 0 acceptance gate.

## Resume references

- [Agent rules](../AGENTS.md), [documentation index](README.md)
- [Specification](PROJECT_SPECIFICATION.md), [implementation plan](IMPLEMENTATION_PLAN.md)
- [Phase 0 checklist](phase0/CONTRACT_VALIDATION.md)
- [Bahi reads](api/bahi/LIVE_VALIDATION.md), [posting/recovery](api/bahi/CONTROLLED_POSTING.md)
- [Qt/Huey fix](phase0/QT_HUEY_COMPATIBILITY.md), [Tally evidence](api/tally/README.md)

Keep exact implemented signatures/enums in source/tests as the application grows.
