# Current state and progress

Last updated: 19 November 2026.

## Current milestone: repeatable supplier State updates

The owner verified controlled record `bcc0b354-14ab-4f7b-a1c1-cfc5d277d778`
(Bahi source 282, Tally GUID ending 0000016c) directly in Tally: Delhi and
unselected details are correct. The saved SUCCEEDED result also survives restart.
All seven read-back/preservation comparisons pass. This owner evidence completes
the [controlled trial](master-sync/CONTROLLED_STATE_UPDATE.md).

The normal [State update feature](master-sync/SUPPLIER_STATE_UPDATES.md) now supports
successive Bahi-to-Tally supplier State changes: **Review linked changes → Review
State update → Confirm State update**. Saved operator, automatic party-scoped latest
result and post-success refresh replace test-labelled controls. Each new change
requires fresh exact approval; startup and refresh never write.

Successful audit evidence is the separate State-only acknowledgement. Future State
reviews use it, while original identity links/other-field observations stay intact.
Approval binds the predecessor acknowledgement; transactional reservation/attempt/
completion checks reject stale baselines. Uncertain/blocked outcomes do not advance
it or permit another write. Migration 7 backs up and preserves v6 trial evidence,
removing only the one-audit-per-link restriction; operation uniqueness remains.
The typed mailing contract, preservation rules, shared journal and gateway remain.
No GUID-only/remote conditional-write guarantee is claimed.

**87 focused checks passed** for State XML, actual gateway/HTTPX with fake remotes,
repeat updates, State-only baselines, conflicts/clears, uncertainty/no resend,
old approval hashes, migration backup/rollback and offscreen UI/restart. Complete
offline suite: **425 passed, one opt-in live test skipped**. Documentation checks
pass for 9 Markdown files and 129 local links/anchors; git diff --check passes.
No dependencies/environment changes, computer use,
BahiAI reuse, assistant live writes or runtime journal changes ran for this work.

Owner screenshots on 19 November confirm the repeat update **Delhi to Haryana**,
record `ec02114b-7aa7-46a5-bf70-b2fe4901ef81`, source 282 and the same GUID.
The normal feature shows SUCCEEDED, all seven comparisons true, original link/audit
preserved and State baseline saved. Tally directly shows Haryana with the same
visible address, country India and PIN 110019. This verifies a second live update;
restart persistence of this new record and independent-edit conflict handling
remain pending owner checks.

Next: restart and load this latest result; confirm both update histories/original
link remain. Then check an independent Tally edit blocks propagation using the
short feature checklist. No additional write is needed for the restart check.
Customers, other fields, clears, multi-entry mailing history, reverse/batch updates
and unattended sync remain separate gates. Preserve journals, records and invoice 69.

## Current repair: TallyPrime 7.0 mailing and Unicode

Fresh owner-run supplier trial: Reliance Jio Infocomm Limited, Bahi source 282,
batch 3dc1c9d0-a034-41e9-b018-ce0cb7339562, now shows SUCCEEDED and a saved link.
Tally screenshot shows populated address, country India and PIN. Read-only local
journal inspection confirms GUID ending 0000016c and all approved comparisons
true: name, address, country, PIN, identity and supplier/group context. State was
null and explicitly omitted by saved policy, as were null email/phone; tax fields
were disabled. Tally's Not Applicable state therefore does not contradict the
approved manifest. This establishes fresh dated/Unicode creation for this subset;
populated state/contact fields, customers and multi-party cases remain pending.
Restart persistence for this new Reliance link is not yet owner-confirmed.

The owner corrected Airtel's mailing fields in its existing Tally ledger. The
remaining saved failure was address only: approved U+2013 en dash, read-back U+003F
question mark. Export-only comparison proved the value is correct in Tally:
legacy and explicit UTF-8 HTTP exports substitute the character, while UTF-16
returns the exact approved address. No further owner correction is needed.

The private transport now sends Unicode XML with Content-Type UTF-16 for guarded
exports/typed imports. Strict parsing accepts observed UTF-16LE no-BOM replies
and BOM-marked UTF-16, without replacement decoding. XML declaration, DTD/entity,
invalid-control and typed-create guards remain enforced. Production-reader live
exports now match Airtel's existing identity, group/type and **every approved
field**. The owner now confirms Airtel shows **SUCCEEDED** after the prescribed
restart/read-only reconciliation. The owner also confirms its saved link is
visible and remains after restart. No assistant
journal writes, remote imports or remote corrections ran. See
[Unicode evidence](api/tally/README.md#unicode-http-repair--18-november-2026).

Owner's fresh Bahi-to-Tally supplier Airtel India (source 281) was created as GUID
0b212ad8-3be5-45fe-8719-e1a70e240d4c-0000016b, but mailing address/state/PIN were
not saved. Saved comparisons blocked completion. A root country field returned
India despite the owner's mailing Country showing Not Applicable. The previous
root COUNTRYOFRESIDENCE-only fix was insufficient; it is not a verified import.

The builder now uses the observed dated LEDMAILINGDETAILS.LIST for address,
state, country and PIN. Its applicable date comes from the destination company's
BooksFrom, is bound to approval context, and is checked again before import.
Missing/invalid/future/changed dates block creation. Export-only checks on SIS
Dummy returned BooksFrom 20260401; known-GUID exports confirmed an empty mailing
aggregate for Airtel and a dated aggregate for the earlier owner-corrected ledger.
Before owner correction, the export-only scan completed with 54 eligible parties
and 12 classification exclusions; Airtel's mailing fields then read as absent.
See [actual evidence and limits](api/tally/README.md#dated-mailing-repair--18-november-2026).

Reads prefer dated mailing values, including their absence, over root echoes.
Multiple/unsupported/not-yet-effective mailing records remain unavailable; no
history row is chosen by guesswork. New creates require the approved dated
aggregate on read-back. Blocked results now name failed comparisons. Name/email/
phone-only creation, legacy journals and one-attempt recovery remain unchanged.
No schema/dependency/environment changes, live imports, remote corrections,
computer-use testing or owner-runtime edits ran. Existing Airtel must not be
recreated. Its corrected fields match and owner-run reconciliation now succeeds.

Verification: existing Python **3.13.15**; **153 focused checks passed**;
complete offline suite **338 passed, one opt-in live check skipped**. Tests include
real gateway/HTTPX XML adapters and temporary SQLite, both party types, independent
native export fixtures, ignored-field failures, date guards, persisted results,
atomic mapping/audit, exact Unicode values through transport/SQLite and known-GUID
reconciliation without a second create. Unicode transport's create path is tested
offline only; this turn's live checks were exports only.
Documentation links/fences and git diff --check passed. Fresh live import acceptance
now has the owner-run Reliance evidence above for its exact included fields.

## Owner-verified behavior and next action

- Apollo Hospital Jayanagar transferred to Bahi 52 account 280, Active, Vendors
  (A/P) / VENDOR. Owner verified destination details and batch/link persistence
  after restart; reviewer surjeet. Displayed optional fields were blank.
- Earlier supplier source 276 / batch 2da2cf3d-5040-4145-bce8-5680bb4a6262 completed
  after the owner corrected Country in its existing Tally ledger and ran read-only
  reconciliation. The saved comparisons/link pass; this does not certify creates.
- Transfer setup now explains the required saved operator/policy; recovery refreshes
  links/status and completion messages. Scrollable pages fit scaled Windows screens.
  The owner reports no geometry warning after restart.
- X uses graceful Quit; minimize keeps the app running. Owner confirmed terminal
  exit works. Shared worker/resource shutdown and startup-failure paths have tests.

Other pending create acceptance: confirm the new Reliance result/link survive restart, then verify a fresh
party with populated state/contact fields and customer/multi-party cases.
Airtel's reconciliation and saved-link restart checks are already owner-confirmed.
No repeat create is needed for either source. Customer/multi-party live cases, tax
support, broader MST-004 and Phase 0/foundation/frozen certification remain pending.
Ledger/UOM work stays deferred while party transfers are verified.

Owner-selected development order: official Tally documentation first, then
read-only investigation/tests; BahiAI implementation is a fallback only when the
issue remains unresolved. Independently verify adapted code rather than inheriting
its assumptions. See the plan's reuse assessment.

Read-only BahiAI source comparison: its add_vendor_mailing_details uses the same
dated aggregate concept already implemented here. Useful behavior can be ported
as connector-owned code/fixtures, per the plan's reuse assessment; no runtime
dependency is needed. Its fallback to today's date, PIN extraction from address,
extra alias tags and counter-only create result are not adopted as verified
connector policies. Its application/xml HTTP path has no explicit UTF-16 handling;
source inspection does not establish equivalent live Unicode behavior. No BahiAI
files, connector runtime code or live records changed during this comparison.

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
