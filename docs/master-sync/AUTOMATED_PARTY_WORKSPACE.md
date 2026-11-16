# Automated preparation and approved party batches

Implemented 4 November 2026. This is the default native application workflow.
It automates preparation and execution after explicit batch approval; it does
not enable unattended creation or synchronization. The previous
[single-party implementation](PARTY_TRANSFER.md) remains the execution foundation
and an advanced inspection path.

## Everyday workflow

Launch with the existing `.venv` and the same runtime directory as before:

```powershell
.\.venv\Scripts\python.exe -m innoforia_tally_connector
```

The primary areas are Parties, Activity and Settings. An existing confirmed
binding reopens only after fresh business/company identity and classification
ancestry checks. First setup requires explicit observed-root confirmation. Save
the operator and field policy once in Settings; subsequent launches verify,
load parties and check known unresolved targets automatically. No periodic polling
is enabled. Failed verification leaves transfers disabled with an actionable message.

Check/select 1–100 customers/suppliers on one side and use Transfer or copy-drag
to the opposite NEW-party area. One batch has one direction and may contain both
party types. Preparation reads fresh source details, mappings and complete
destination observations. Destination observations are reused within preparation;
Tally also checks non-party ledger names. Final write checks remain fresh.

The resizable summary separates Ready, Already linked and Needs review. Select
a row for exact fields, destination/group semantics, omissions and candidates.
Empty candidate views are hidden. Duplicate names/GSTINs within the selected
sources also need review. Candidates cannot be dismissed to authorize creation.
Existing-row drops and candidate actions require explicit local identity-link
confirmation, without remote field changes.

One Confirm transfer action approves the exact Ready subset. Where system flags
are unavailable, a separate unchecked batch checkbox requires the named operator
to confirm all applicable Ready sources are normal non-system business parties.
The confirmation is recorded against each applicable child, not claimed as API
verification. Known system parties and inactive/unavailable-active Bahi parties
remain ineligible. Closing the summary without confirmation sends no create.

## Saved field policy

Policies are versioned and binding-scoped, with separate destination selections.
Initial contact/mailing choices are email, phone, address, country, state and
pincode. Name/classification are required. Tax writes remain disabled while the
Tally representation gates are open.

Saving the policy explicitly permits automatic omission of unavailable or invalid
optional fields, with generated reasons retained in every child preview and link
audit. Disabled fields have policy/version reasons. Missing, null, empty and
unavailable remain distinct; valid values are copied exactly. No truncation,
tax translation, balances or invented defaults are enabled. GSTIN cannot be
included without required observed registration information.

Policy edits invalidate unapproved summaries. Approved/executing/historical work
retains its original policy, payloads and operator. Expired or previous-session
summaries refresh through reads and require another review. Each child must still
pass the five-minute freshness gate immediately before execution.

## Execution and recovery

Migration 5 adds policy versions, batches and membership on the existing operation,
outbox, attempt and mapping journal. The migration runner takes a SQLite-consistent
backup before upgrading an existing database. Credentials stay in Windows Credential
Manager; only references are local.

Approval atomically reserves the binding/sources, stores exact child intents and
approval evidence, and places the first child operation ID in the shared outbox.
One Huey thread executes children sequentially through the existing one-attempt
workflow and injected serialized Tally gateway. Each completed child schedules the
next through a transactional outbox record. Network IO never runs inside a transaction.

Each child rechecks source/context/collisions, records its attempt before sending,
persists target identity before read-back, then atomically commits mapping/audit/
completion. Authoritative rejections permit later children to proceed; errors and
successes remain separate. Uncertain writes, read-back differences, changed sources,
expired approvals and local completion failures pause remaining work. Outer errors
also preserve write evidence and pause the batch when storage remains available.

Stop unsent transfers persists cancellation from the dispatch thread; the current
bounded operation finishes and unsent children are cancelled. No created records
are deleted. Obsolete unapproved drafts are superseded automatically, including
legacy unattempted PENDING previews; attempted history is never superseded.

Restart never creates. Started work becomes uncertain; unsent children require
a new reviewed summary. Known target identities permit bounded read-only
reconciliation (up to 20 candidates per check), automatically after loading a saved
connection and after paused execution. Missing-ID outcomes cannot be resolved by
names or absence. Unresolved reservations remain until authoritative evidence
establishes the outcome. Review remaining parties prepares a new summary without
recreating attempted records.

Activity pages batches in groups of 50 and saved links in groups of 200. Advanced
details retain per-party/legacy history. History belongs to its original runtime
and binding generation; build/live-party-ui is not merged with the default
Local AppData/InnoforaiTallySync runtime.

## Evidence and remaining gates

Tests use synthetic remotes, offscreen Qt, real worker/adapters, temporary SQLite
and restart. No assistant live requests, computer-use verification, runtime upgrade
or installer/frozen build ran. Totals are in [current state](../STATE_AND_PROGRESS.md).

The owner supplied an actual-party Tally-to-Bahi screen showing SUCCEEDED for
record 9b70c10d-0ade-45c5-8da2-99027a69dec9 before this batch change. This is
owner-reported application success; the cropped screenshot does not establish
destination identity/fields or restart persistence for that transfer.

Follow the [owner checklist](MANUAL_PARTY_TRANSFER_CHECKLIST.md). Full MST-004,
Tally tax support, groups/items, transactions and unattended sync remain separate
gates. Backend idempotency/outcome lookup, conditional versions, change capture and
cross-PC writer ownership are not established by a local reservation/preflight scan.
