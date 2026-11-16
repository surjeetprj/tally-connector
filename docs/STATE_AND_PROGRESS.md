# Current state and progress

Last updated: 4 November 2026.

## Active milestone

The default native app now provides **Parties, Activity and Settings**, saved
operator/field policies, automatic verified connection restoration/loading and
selected party batches with one approval. Offline implementation is complete;
owner manual verification of the new workspace remains pending. Full MST-004,
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
- Known pair: Bahi 52, SISOFT Technologies Private Limited, and Tally release 6.2,
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

The owner should quit the old connector and launch the same runtime. Save the
operator/default field policy once, verify automatic reopening on a second launch,
then follow the short manual checklist for single/multiple customer/supplier
transfers in both directions. Include a mixed Ready/Linked/Needs-review selection,
destination field inspection, saved links and restart screenshots. Record actual
outcomes as owner-reported evidence. Do not run live transfers automatically.

## References

[Agent instructions](../AGENTS.md), [documentation index](README.md),
[specification](PROJECT_SPECIFICATION.md), [implementation plan](IMPLEMENTATION_PLAN.md),
[Bahi contracts](api/bahi/README.md), [Tally evidence](api/tally/README.md),
[backend handoff](api/bahi/SYNC_EXTENSION_CONTRACT.md),
[Qt/Huey compatibility](phase0/QT_HUEY_COMPATIBILITY.md).
