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

Opening Activity from the transfer summary now starts at the top, with Advanced
collapsed and a compact result showing party names, status, destination identities
and omitted fields (up to five parties, with full batch inspection available).
Legacy per-party evidence and recovery remain available under Advanced; normal
navigation no longer expands or focuses the older transfer form. Changing the
binding clears the compact result. This display change sends no remote writes.
Double-clicking a saved transfer link opens its original field table in Advanced
> Operation details. Saved updates also open there with before/approved/read-back
columns. Link JSON is labelled as the original historical observation; later
updates do not rewrite it. Field tables remain read-only and scrollable.

The initial window fits the available logical desktop area. Tab contents scroll
when large fonts, display scaling or advanced panels exceed the viewport, keeping
lower controls reachable instead of forcing the window beyond the screen.

Closing the main window with X now runs the same graceful shutdown as Quit
connector, including while startup is pending or has failed. The process exits
after bounded work/resources finish. Use the standard minimize button to keep
the connector running; closing no longer hides it in the tray.

When party lists are loaded before a policy is saved, Parties displays a persistent
Finish transfer setup action. The transfer buttons then open Settings at the name
field rather than remaining silently disabled. A visible validation message explains
a missing name. Saving settings enables preparation but never starts a transfer;
the exact batch still needs approval. Setup guidance disappears once the saved
policy has been returned successfully, including after restart.

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
The current transfer workflow includes all supported applicable source fields in
both directions: contact/mailing values, PAN and valid GSTIN/registration type.
Name/classification remain required. Opening Settings or preparing a new batch
versions old contact-only policies automatically; unapproved drafts require a new
summary. Approved/executing/historical work retains its original field decisions.
Fields are not silently dropped merely because older policies predated support.
Invalid/unavailable/destination-incompatible optional values still have reasons.

Tally GST creation requires the complete supported Regular/Composition pair and
populated source State/country India. Its initial master applicability date is the
verified destination Books From date, shown before approval with exact payload
values. This is not a fabricated source registration date or history. Known-GUID
read-back verifies the approved date and fields. Bahi stores current tax scalars.
No tax rates, accounting balances, bank settings or unsupported aliases are added.

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

When read-only checks finish, Activity refreshes saved links automatically and
shows a completion message. Newly linked parties receive Linked status. A link
refresh failure remains visible rather than reporting success or leaving a stale
Working in background message.

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

On 18 November the owner verified a new workspace supplier transfer, Apollo
Hospital Jayanagar, to Bahi business 52 account 280. The destination screenshot
shows Active, Vendors (A/P) / VENDOR; the owner confirmed the successful batch
5a37f710-4ae7-4cdc-a67f-8266ea906d34 and mapping survive restart, with reviewer
surjeet. Contact/tax fields shown are blank; this case does not verify populated
optional fields, reverse-direction transfers, customers or multiple-party batches.

Follow the [owner checklist](MANUAL_PARTY_TRANSFER_CHECKLIST.md). Full MST-004,
Tally tax support, groups/items, transactions and unattended sync remain separate
gates. Backend idempotency/outcome lookup, conditional versions, change capture and
cross-PC writer ownership are not established by a local reservation/preflight scan.

TallyPrime 7.0 mailing repair (18 November): root mailing writes were ignored on
the owner's Airtel trial. New creates now use one dated mailing aggregate with
the verified destination Company.BooksFrom bound to approval. Read-back verifies
that dated representation; empty/root-only echoes cannot pass. Ambiguous history
and unavailable/changed dates block. See [evidence and remaining live gate](../api/tally/README.md#dated-mailing-repair--18-november-2026).
125 focused checks and the full offline suite (310 passed, one live skipped) pass.
Export-only diagnostics ran; no assistant remote writes or runtime edits occurred.

The subsequent owner-corrected Airtel address exposed lossy legacy HTTP exports:
an en dash became a question mark. The private transport now uses UTF-16 XML,
with strict native reply decoding and exact field comparison retained. All
approved Airtel fields match via live exports; owner-run reconciliation is next.
153 focused checks and the full offline suite (338 passed, one live skipped) pass.
See [Unicode evidence and create limitation](../api/tally/README.md#unicode-http-repair--18-november-2026).

## Owner acceptance: all applicable fields

On 19 November 2026 the owner reported that SKE CLOUD PRIVATE LIMITED transferred
successfully from Tally to Bahi with no omissions. This is owner-reported live
acceptance for that record, following the policy upgrade. Independent destination
field inspection, record IDs, party type and restart evidence were not supplied.
The separate SK TRADING PAN investigation confirmed the source PAN was empty;
that omission is source availability, not a disabled tax policy.

On 20 November the owner supplied Bahi source account 285, the SUCCEEDED
Bahi-to-Tally policy-v4 result, and a Tally destination screenshot for customer
TCS(Tata Consultancy Services Limited). Destination Sundry Debtors, name/address,
Maharashtra, India, PIN 400021, PAN AAACR4849R, GSTIN 27AAACR4849R1ZL and Regular
registration are visible and match the supplied source. This establishes the new
customer/Regular tax-creation subset. Phone/email are included in the approved
payload but not visible in the Tally screenshot; applicability date 20260401 is
shown in the approved context. Restart persistence, independent native-date
inspection, supplier/Composition creation and mixed batches remain unverified by
these screenshots. No new assistant transfer was performed.

Further owner evidence on 20 November (policy v4): a three-customer Tally-to-Bahi
batch for M/s Sanjay Sales, SHAKUMBRI METALS and Surjeet Pvt shows three SUCCEEDED
results, transferred and linked. The owner confirms all three exist in Bahi.
A Bahi-to-Tally mixed batch shows Reliance Industries Limited (CUSTOMER) and
Infosys Limited (SUPPLIER) moving from Ready to SUCCEEDED, while TCS remains
Already linked before and after execution. Its existing link is retained rather
than submitting another create. This is live batch/linked-skip evidence for these
cases; independent new-destination field/native-date inspection and restart
persistence remain separate. No assistant transfer was run to collect evidence.

The owner subsequently confirmed on 20 November that the new transfer results
and saved links remain after restarting the connector. This supplies the pending
owner restart-persistence evidence for the reported transfers, without repeating
creation. Other capability-specific evidence limits above remain explicit.

## Next workflow: scheduled synchronization

The owner clarified that scheduling is the planned routine workflow. A manual
Review and sync changes action is for on-demand runs and exceptions. Reuse the
existing worker, durable intents/attempts and reconciliation engine; do not add
another queue. Begin with configurable scheduled read-only discovery of linked
party changes and a clear last-run/next-run/error view. Define direction and field
ownership, preserve verified baselines, suppress echoes and block conflicting
edits. Extend to policy-authorized unattended writes only when the required
change/version, writer ownership and uncertain-result contracts are verified.
A timer does not make an unverified write capability safe or establish idempotency.
Creation, clears, renames and unresolved outcomes retain their separate gates.
This records the next delivery direction; scheduling is not implemented or enabled
by this documentation-only change.
