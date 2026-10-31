# Current state and progress

Last updated: 31 October 2026.

## Active milestone

**Phase 0 — local packaging and controlled Bahi posting issues resolved.**
CON-001 has live read/write evidence and a proposed backend contract handoff.
CON-002 has baseline/populated Tally reads; Tally imports remain untested.
CON-003 source and fresh frozen lifecycle/resource experiments now pass locally.
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
- Bahi is company-owned; the user can arrange new endpoints but currently has no
  authoritative backend source. Do not inspect the excluded local `bahi` testing
  directory as a substitute. Use handbooks and live responses; server changes
  need authoritative source or the backend developer.

## Latest repository update

Fixed Mermaid syntax errors reported in the preview: renamed the sequence
participant `LINKS` to `ADAPTERS`, removed message semicolons interpreted as
statement separators, and replaced the unsupported default state class with an
explicit named class applied to all states. All seven diagrams across the
architecture, master UI flow, sequence and state documents parsed and rendered
to SVG in headless Chrome using the Mermaid bundle from installed Markdown
Preview Enhanced 0.8.40. Validation HTML/SVG output is ignored under
`build/mermaid-validation/`. This validates rendering with that bundle, not every
Markdown preview extension/version. No business requests or runtime tests ran.

Added [master sequence diagrams](master-sync/MASTER_SYNC_SEQUENCES.md) for local
linking, verified transfer and uncertain-write reconciliation, plus the
[shared operation state diagram](master-sync/MASTER_SYNC_STATES.md). Bold uppercase
labels and plain-language tables explain the normal and recovery paths. These
are planned behavior, not a new state enum or proof of implemented recovery.
The subsequent headless check above supersedes the earlier syntax-only checks.
Checks passed for the five diagram-related Markdown files: four Mermaid blocks,
balanced fences, 42 local links/anchors, no trailing whitespace and
`git diff --check`. No runtime tests, network requests or business writes ran.

Prepared the [master-sync documentation](master-sync/README.md): design and open
policy decisions, semantic field mapping, matching rules, beginner-friendly UI
flow and validation/recovery cases. Added MST-001 through MST-008 work packages
under existing CON tasks in the implementation plan. All packages are pending.
The selected delivery order is foundation, supervised masters, purchase slice,
then remaining automatic/expansion gates. The specification and index reflect it.

No master adapter, production sync engine, database schema or UI was implemented.
Tally mappings are semantic targets, not verified XML contracts. Backend changes
remain proposals. Master writes, service/charge representation, automatic mode
and policy decisions are not marked verified. Existing invoice 69 and runtime
journals are untouched; no network calls or business writes ran for this task.
Documentation checks passed for 11 affected Markdown files: balanced code fences,
95 local links/anchors and `git diff --check`. No runtime tests were run because
this task changes documentation only.

The architecture guide retains two simplified Mermaid diagrams with bold uppercase
labels. Its SVG rendering passed the headless check above. The existing .venv
references an unavailable Python312 interpreter; repair/recreate it before Python
experiments. Git tracks this project with origin pointing to
`https://github.com/surjeetprj/tally-connector.git`. The user requested a commit
of these master-sync documents and Mermaid fixes; no push was requested.

## Implemented scope

Source package structure and build metadata now exist; runtime application
services/entry point do not. Git now tracks the project. Phase 0 remains isolated
scripts/tests, an ignored project .venv, build outputs and sanitized evidence.
The specification's named service files remain planned, not implemented APIs.

- Bahi GET probe verified business, supplier, group, item and purchase contracts.
- Tally baseline and populated AlterID probes verify the observed query behavior.
- Credential entry uses a masked local window and Windows Credential Manager.
- Controlled Bahi draft/PATCH/post/repeat-post and known-ID client-crash recovery
  scripts retain durable local write intent and refuse uncertain create replay.
- Qt/Huey spike verifies local persisted tasks, retry, serialization, queued signals,
  heartbeat, idle stop and assets. A reproducible isolated-PATH build fixes the
  foreign ICU DLL that caused the earlier QtCore import failure.

## Verification and material external effects

- Fifteen offline tests pass. Source and fresh frozen Qt/Huey runs each pass all
  eleven runtime assertions. Python 3.12.8, PySide6 6.11.1, Huey 3.5.3,
  PyInstaller 6.21.0 and hooks 2026.6 form the current experiment baseline.
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
- Final checks passed: 18 Markdown files, 99 local links/anchors, eleven Python
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

Start [MST-001](IMPLEMENTATION_PLAN.md#master-first-work-packages): review the
master decision register and prepare controlled master identity/read-back
experiments for CON-002. Resolve policies only for the fields/types being enabled.
Restore the project interpreter before executing Python checks. Complete pending
Phase 0/foundation prerequisites, then deliver read-only discovery and confirmed
links before master writes. Do not begin purchase transfer ahead of this milestone.

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
