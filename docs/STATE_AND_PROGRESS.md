# Current state and progress

Last updated: 18 November 2026.

## Current repair: transfer setup guidance

Latest layout repair (18 November): owner Windows scaling exposed a minimum
window height larger than available desktop space, clipping Activity controls.
Primary pages now scroll overflow instead of forcing that minimum on the window;
initial sizing uses available logical screen geometry. Focused checks: 18 passed,
including larger-font/smaller-window reachability and normal transfer flows.
Full offline suite: **276 passed, one live check skipped**. Changed documentation
links/fences and git diff --check passed. The owner restarted and reports no
terminal geometry warning; this confirms warning removal on their installation.
No computer-use automation, live calls or runtime edits ran. Scroll reachability
has offline coverage; broader native layout inspection remains owner-run.

Latest recovery verification (18 November): owner clicked read-only result checks
and the Bahi-to-Tally batch 2da2cf3d-5040-4145-bce8-5680bb4a6262 now shows
SUCCEEDED. Read-only local journal inspection confirms all stored comparisons,
including country, pass and the identity link exists. Its target was corrected
by the owner; this does not verify the new create XML on a fresh ledger.
Activity was showing stale saved links and Working in background after completion.
The recovery result now refreshes links automatically, updates party link status
and displays explicit completion; errors remain visible. Focused checks: 14 passed.
Full offline regression: **272 passed, one live check skipped**. Documentation
link/fence checks and git diff --check passed.
No live calls or runtime edits were performed during this repair.

Latest country fix (18 November): the owner reports TallyPrime 7.0 and supplied
an all-ledger XML export. It uses COUNTRYOFRESIDENCE (16 occurrences), not
COUNTRYNAME (zero); the blocked ledger has no country. The builder/query now use
the observed native country field, with strict read-back comparisons retained.
No date is invented for dated mailing records. Synthetic country-shape fixtures
and known-GUID read-only reconciliation tests were added; reconciled child success
now updates a fully completed parent batch. Focused mapping/batch checks: 44 passed;
complete offline suite after recovery test: **270 passed, one live check skipped**.
See [export evidence and limitations](api/tally/README.md#supplied-tallyprime-70-export).
No live API requests, remote corrections, runtime edits or duplicate creates ran.
Corrected create XML is offline-tested, not live-import-certified.

Owner screenshots show loaded parties and preserved identity links, but no saved
operator/field policy; transfer buttons were silently disabled. Parties now shows
Finish transfer setup and its buttons open Settings at the required name field.
Blank-name validation is visible in Settings; failed saves retain the setup gate.
Successful save enables preparation without starting a transfer. The LOAD status
no longer tells the user to transfer when setup is incomplete. Existing verified
binding, approval, execution and recovery guards are unchanged.

Focused offline UI/integration checks: 12 passed. The tests reproduce Refresh
before saving settings, both transfer directions/types and saved-policy restart.
Complete offline regression: **265 passed, one opt-in live check skipped**.
Changed documentation links/fences and git diff whitespace checks passed.
No live calls, computer-use automation or owner-runtime edits were performed.
Owner verification on 18 November: Apollo Hospital Jayanagar transferred from
Tally to Bahi business 52 as account 280, Active, Vendors (A/P) / VENDOR. Batch
5a37f710-4ae7-4cdc-a67f-8266ea906d34 and its saved identity link survived restart,
confirmed by the owner and screenshots; reviewer surjeet. Displayed contact/tax
fields are blank, so populated-field round trips are not established by this case.
The reverse trial on 18 November created a Tally supplier but is BLOCKED:
batch 2da2cf3d-5040-4145-bce8-5680bb4a6262, source
MST004-SUP-20261102-7a5d3198, destination GUID
0b212ad8-3be5-45fe-8719-e1a70e240d4c-0000016a. Read-only inspection of the saved
runtime comparison evidence shows name, email, identity, supplier type and group
matching; only country fails (approved India, country absent from read-back).
No live requests, runtime edits, reconciliation or repeat creation were performed
while diagnosing this case. Do not recreate or weaken its approved comparisons.
The subsequent Tally screenshot confirms Country is Not Applicable rather than
India, so this is a saved-value mismatch, not merely an absent read field. The
current root COUNTRYNAME payload did not establish the approved country on this
deployment. Official generic samples show that tag, while the release-3 schema
documents dated LedMailingDetails/Country; neither alone verifies the required
7.0 create shape/date. The supplied export establishes the native country field;
the owner's correction and read-only reconciliation have now completed this
existing transfer as recorded above. Do not transfer the source again. The new
create mapping still needs live verification. Customer and multi-party live
cases remain pending.
Ledger/UOM work remains deferred while party transfers are being verified.

## Latest contract refresh

Imported all seven supplied Bahi handbooks, preserving their bytes and existing
project link paths. Ledger and UOM contracts are newly supplied; party routing
and obsolete item-field guidance changed. Invoice, group and setup content is
unchanged. Updated the assessment, specification, plan and master/Phase 0 notes
to distinguish documented APIs from pending adapters and deployment verification.
See [comparison and follow-up gates](api/bahi/HANDBOOK_REFRESH_2026_11_16.md).

No runtime code change was needed for the unchanged party wire contract. SHA-256
copy checks, Markdown local links/anchors, fences and diff whitespace checks passed.
Runtime tests/builds and live API calls were not run for this documentation task;
the project Python launcher failed because sandbox access to its base interpreter
was denied. PowerShell/Git supplied the document checks. Ledger/UOM reader work
remains a separate bounded implementation task; owner workspace verification below
remains pending. Historical verification below describes the 4 November implementation.

## Active milestone

The default native app now provides **Parties, Activity and Settings**, saved
operator/field policies, automatic verified connection restoration/loading and
selected party batches with one approval. Offline implementation is complete;
one Tally-to-Bahi supplier and restart are owner-verified; other live cases remain pending. Full MST-004,
Phase 0/foundation and frozen Python 3.13/clean-machine certification remain open.

See [workspace behavior](master-sync/AUTOMATED_PARTY_WORKSPACE.md),
[owner checklist](master-sync/MANUAL_PARTY_TRANSFER_CHECKLIST.md) and
[foundation report](master-sync/READ_LINK_FOUNDATION.md).

## Current behavior

- Reuse the existing confirmed Bahi business 52 / SIS Dummy binding after fresh
  identity and classification-ancestry checks. First setup confirms observed roots;
  Settings saves the named operator and versioned destination field selections.
  Subsequent launches load parties automatically. Changed contexts stop transfers.
- Select/check 1–100 customers/suppliers on one source side; use Transfer or drag
  to the opposite NEW-party area. Review Ready, Already linked and Needs review.
  Existing-row drops open explicit identity-link review, never remote creation.
- Saved policy includes supported contact/mailing fields and records automatic
  omission reasons for unavailable/invalid optional values. Tax fields remain
  disabled. No truncation, inferred defaults, balances or tax translation.
- One confirmation approves the exact Ready subset, operator, policy version,
  source evidence, destination/group context and payload hashes. The unavailable
  system-flag confirmation starts unchecked and applies to all applicable children.
  It is reviewer evidence, not API-verified is_system=False. Inactive/system parties
  remain blocked. Expired/changed summaries refresh and require renewed review.
- Migration 5 extends the existing journal with policy versions, batches and child
  membership. Existing upgrade handling takes a SQLite-consistent backup. Only
  temporary test databases were migrated during implementation, not owner runtime DBs.
- Approval durably reserves the binding and sources before dispatch. One shared
  Huey thread and one injected Tally gateway execute children sequentially.
  Each attempt is recorded before IO; returned identity precedes verification;
  mapping/audit/completion remain atomic. No transaction spans network IO.
- Authoritative per-record rejection permits later children; uncertainty, mismatch,
  changed context/source, expiry or local completion failure pauses remaining work.
  Stop unsent transfers finishes the current bounded operation and cancels unsent
  children without deleting targets. Duplicate clicks/delivery never recreate.
- Unapproved obsolete drafts, including legacy unattempted PENDING previews, are
  superseded automatically with history retained. Attempted/uncertain records
  retain their reservations. Startup restores unsent work for review and never
  creates. Known-ID recovery performs bounded reads/local completion only.
- Activity pages batches and saved links; advanced details preserve legacy and
  per-party history. No unlink/relink, updates, automatic links or unattended writes.

## Verification and owner evidence

- Existing .venv / Python 3.13.15 reused; dependency versions unchanged.
- Complete offline regression: **264 passed, one opt-in live test skipped**.
  Coverage includes policies/omissions, both directions/types, mixed eligibility,
  exact approval, duplicate dispatch/competing approvals, mapping/audit rollback,
  cancellation during IO, expiry between children, lost acknowledgement after
  target commit, dispatch-gap recovery, migrations/backups and restart.
- Production Workspace tests exercise Qt/controller/Huey/bootstrap/adapters/SQLite
  with fake remotes, GUI heartbeat and automatic reconnect/loading after restart.
  Existing matching SELECT bounds (2/200/2,000), gateway serialization and layer
  boundary checks remain covered. No computer-use automation was run.
- An intermediate focused run exposed a startup scheduling timeout. Setup now
  waits for a saved policy before loading and starts recovery after loading;
  subsequent complete offline regression passed.
- Owner previously confirmed drag initiation and preservation of their real link
  after restart. Their later screenshot reports Tally-to-Bahi SUCCEEDED for
  record 9b70c10d-0ade-45c5-8da2-99027a69dec9. Destination identity/fields and restart
  evidence for that actual-party transfer are still pending; batch live gates
  cannot be inferred from that screenshot.
- No live Bahi/Tally GET/export/POST/import, posting experiment, runtime journal
  edit, installer or frozen build ran for this implementation. No configured lint
  or formatting command exists.
- Documentation checks passed for 13 Markdown files and 151 local links/anchors.
  Whitespace checks passed for 78 changed/new files excluding the unrelated
  pre-existing database.py finding; 65 Python files parsed successfully. Supplied
  handbooks are unchanged. Scoped git diff --check passed.
- Whole-tree diff whitespace checking reports an unrelated pre-existing blank
  first line with a space in persistence/database.py; it is preserved.

## Field and automation limits

Bahi wire payloads follow the supplied handbook. Tally contact/mailing XML has
verified-source documentation and offline coverage. Tally PAN/registration reads
and tax writes remain gated pending exact release-6.2 evidence. Missing, null,
empty and unavailable values remain distinct, including legacy observations.

Backend idempotency/outcome lookup, conditional versions, change capture,
origin/ownership and cross-PC writer leases remain unverified. Local reservations
and preflight scans do not supply remote atomicity or an exactly-once guarantee.
Items/groups, transactions, party updates and unattended sync remain separate gates.

## Preserved runtime and authorization

- The user authorized implementation of supervised batches and saved omission
  policies. Each exact Ready subset still needs explicit in-app approval. No
  assistant-driven live creation, cleanup, deletion or unattended sync is authorized.
- Known pair: Bahi 52, SISOFT Technologies Private Limited, and owner-reported
  TallyPrime 7.0 (original probes used 6.2),
  SIS Dummy GUID 0b212ad8-3be5-45fe-8719-e1a70e240d4c. Sundry Debtors/customers and
  Sundry Creditors/suppliers with descendants were owner-confirmed on 2 November.
- Bahi base: https://innoforia.com/201/h-bahi/bahi/web-api/. Existing Credential
  Manager reference: InnoforiaTallyConnector/Phase0/Bahi/innoforia.com/201/h-bahi.
  No credentials enter SQLite, queue arguments or logs.
- Preserve Local AppData/InnoforaiTallySync, all links/audits, Phase 0 journals,
  existing test parties and invoice 69. The isolated build/live-party-ui runtime
  is separate and is not merged with the owner's default runtime.
- Earlier agent-approved synthetic supplier trial e69dc947-97fb-4d22-bee5-7696f229baa7
  created Bahi ID 275 once, with read-back/restart/GET-only reconciliation in the
  isolated runtime. See [retained experiment evidence](master-sync/CONTROLLED_SUPPLIER_EXPERIMENT.md).
  Earlier posting evidence remains in [controlled posting](api/bahi/CONTROLLED_POSTING.md);
  do not repeat it.

## Next concrete action

The existing country mismatch is resolved and its mapping persisted. Restart to
load the Activity refresh fix; inspect the completed batch and saved link.
Then follow the short manual checklist for remaining customer/supplier and batch
cases. The corrected create path needs a separately reviewed live case. Record
owner evidence honestly; do not run live transfers automatically.

## References

[Agent instructions](../AGENTS.md), [documentation index](README.md),
[specification](PROJECT_SPECIFICATION.md), [implementation plan](IMPLEMENTATION_PLAN.md),
[Bahi contracts](api/bahi/README.md), [Tally evidence](api/tally/README.md),
[backend handoff](api/bahi/SYNC_EXTENSION_CONTRACT.md),
[Qt/Huey compatibility](phase0/QT_HUEY_COMPATIBILITY.md).
