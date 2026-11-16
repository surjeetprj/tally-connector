# Supervised party transfer

The default launch now uses the [automated batch workspace](AUTOMATED_PARTY_WORKSPACE.md).
The single-party controls below describe the original implementation and advanced
inspection/recovery path. Normal users now save a field policy once and approve
selected batches instead of entering exclusion reasons for each party.

Implemented 3 November 2026. Automated evidence is offline only; the four live
customer/supplier direction combinations await owner testing. Follow the
[manual checklist](MANUAL_PARTY_TRANSFER_CHECKLIST.md). No computer-use automation,
live calls, runtime-database upgrades or installer builds were performed for this change.

## Use and behavior

Use the existing Python environment and the same runtime directory that contains
your links and experiment history. Quit the previous connector before launching:

```powershell
.\.venv\Scripts\python.exe -m innoforia_tally_connector
# Only to reopen the earlier isolated experiment runtime instead:
.\.venv\Scripts\python.exe -m innoforia_tally_connector --runtime-dir build/live-party-ui
```

Verify the business/company and explicitly reopen the confirmed customer/supplier
roots. Load parties. Select one actual customer or supplier and use Transfer to
Tally / Transfer to Bahi, or drag it to the opposite panel's labelled NEW-party
drop area. Direction follows the chosen source/destination; no synthetic name or
source identity is generated. Dropping on an existing row opens local identity-link
review, never creation. External, stale, same-side, multi-row and incompatible drops
are rejected. The buttons provide the keyboard-accessible equivalent.

The 4 November owner test exposed missing Qt model drag flags: the initial offline
drop-handler tests did not exercise drag initiation. Party models now explicitly
enable copy drags, with mouse-gesture regression tests in both directions. Other
tables remain non-draggable. Native owner retesting is still required.

Preparation re-reads source details, verifies identities and classification,
checks saved mappings/reservations and scans the destination without UI filters.
Name suggestions use existing case/spacing normalization; GSTIN comparisons stay
exact. All plausible matches block creation, including inactive or already-linked
targets. Exact/normalized-name collisions also block across classifications and
non-party Tally ledgers. There is no candidate-dismissal override: review a
compatible existing link or cancel. Selecting a candidate shows field differences.
Already-linked sources open saved-link details. Reported system parties and
inactive Bahi parties, or Bahi records with unavailable active eligibility, cannot transfer.

The supplied Bahi API explicitly does not expose system flags; the Tally reader
also does not establish one. On 3 November the owner chose a required named-reviewer
confirmation for unavailable flags: the reviewer must separately confirm that the
source is a normal, non-system business party. Its checkbox starts unchecked.
The limitation and confirmation are retained in the operation and mapping audit;
this is owner evidence, not a claim that the API verified is_system=False. A
reported system party cannot bypass the block by checking that box.

Transfer review displays source identity/time, classification, destination/root,
actual values, availability, validity and exclusions. Uncheck an optional field,
give its exclusion reason, then Apply exclusions / renew preview. This records a
new preview and cancels the prior unattempted preview atomically. A nonrepresentable
required name blocks transfer; it cannot be excluded or truncated. Aliases,
contact person and notes are visibly outside this release.

A named reviewer approves the exact included values, exclusions and destination.
When source system status is unavailable, the separate non-system confirmation
must also be checked; cancellation or renewal resets it. It is never sent as a
Bahi/Tally business payload field.
Approval is tied to the source observation, binding/session generation, direction,
group context and digest; it expires after five minutes. Changed fields/context,
expiry or restart require renewal. Cancellation sends no create. Group selection
does not grant overwrite or automatic-sync permission.

Tally creates only under the confirmed Sundry Debtors/customer or Sundry
Creditors/supplier root; source subgroups are not recreated. Bahi chooses its
server-configured CUSTOMER/SUPPLIER group; its code/ID is not exposed or selectable.

## Field capabilities and evidence limits

Wire contracts remain in adapters and the
[supplied handbook](../api/bahi/handbooks/API-PARTY-DEVELOPER-HANDBOOK.md).
The canonical model now includes country, PAN and GST registration type alongside
the prior contact/mailing/GSTIN fields. Older observations remain readable; newly
introduced fields are unavailable until fresh reads establish their presence.
Null, missing, empty and unavailable are distinct. Original names, case, leading
zeroes and line boundaries are retained. No automatic tax or country translation,
default registration label or opening/accounting balance is introduced.

| Capability | Implementation / remaining evidence |
| --- | --- |
| Bahi name/contact/mailing/PAN/GST fields | Documented payload validation and mocked POST/detail coverage; new actual-source round trips await owner evidence |
| Tally name/email/phone/country/state/PIN | Documented single-ledger XML and mocked transport/read-back; new live round trips pending |
| Tally multiline address | Ordered ADDRESS.LIST children retained as newline-separated canonical content; ambiguous structures become unavailable, never flattened silently |
| Tally PAN and registration-type reads | Unavailable pending release-specific evidence; require explicit exclusions |
| Tally GST/PAN/registration writes | Disabled pending exact 6.2 representation/read-back evidence; require explicit exclusions |
| Bahi GSTIN without an observed registration type | Blocked as an unresolved tax profile; exclude GSTIN too rather than invent a registration type |

Tally's [official sample XML](https://help.tallysolutions.com/sample-xml/) documents
mailing/contact tags. Its [release-3 schema changes](https://help.tallysolutions.com/developer-reference/release-3-tdl-enhancements-tally-prime/what-are-the-changes-in-xml-tags/)
describe dated mailing and GST registration aggregates. These do not establish an
exact create mapping, applicable date or PAN tag for this 6.2 deployment. Existing
observed root GSTIN can remain candidate evidence, but is not proof of complete
tax-registration semantics. No end-to-end tax transfer is certified by fixtures.
Null values without a destination representation and invalid values likewise need
explicit exclusions; invalid required fields block approval. The UI does not edit
or invent source business values.

Owner-invoked field evidence commands (not run against live services in this task):

```powershell
# Offline: inspect an owner-exported XML file. Keeps tag paths/counts, not values.
.\.venv\Scripts\python.exe scripts/master_sync/party_field_evidence.py --xml-file build/owner-ledger.xml
# Explicit opt-in GET/export detail reads. Replace IDs with owner-selected records.
.\.venv\Scripts\python.exe scripts/master_sync/party_field_evidence.py --live-read --bahi-id 275
.\.venv\Scripts\python.exe scripts/master_sync/party_field_evidence.py --live-read --tally-guid '<ledger-GUID>'
```

The default output is ignored build/party-field-evidence.json. These commands
never create, update, delete or post. Field availability is not write evidence.
Do not commit raw customer exports, credentials or runtime databases.

## Execution, mapping and recovery

The feature reuses the shared operation/outbox journal, one Huey thread worker,
one injected serialized Tally gateway and bounded HTTPX clients. Queue arguments
remain operation IDs. No database transaction spans network IO. Typed Tally
imports allow one customer/supplier Create only, never arbitrary XML or balances;
the existing export path remains export-only. Bahi adds no PATCH/DELETE/invoice routes.

Metadata migration 4 extends the existing journal with source reservations and
queryable history, preserving experiment rows. The migration runner first backs
up committed SQLite/WAL state. The schema version remains PRAGMA user_version.
Existing bindings, credentials references, links/audits and old observation JSON
are preserved. Credentials remain in Windows Credential Manager.

Preparation reserves the source and binding in a bounded transaction. Both local
link confirmation and competing previews respect that reservation. Immediately
before transmission, the feature rechecks source content/classification, context,
mapping availability, complete destination coverage and candidates, then atomically
records the approved attempt. Duplicate clicks/delivery cannot create again.

The returned destination ID/receipt is saved before further reads. Bahi reads the
returned account ID. Tally uses returned MasterID/GUID or a positive create receipt
plus a fresh, uniquely resolved new GUID. Matching names alone never resolve an
uncertain outcome. Counters without actual detail verification never mean success.

Identity/context, party type, group semantics and every transmitted field must
match. The source is re-read again before atomic mapping/audit/success completion.
The mapping audit contains included fields and explicit exclusions; each side's
observation remains separate, without a whole-record equal-content claim.

Timeout, malformed response or interruption after an attempt preserves uncertainty.
Known IDs permit read-only reconciliation. Missing IDs, changed source, mismatches
or mapping conflicts retain the target evidence and block recreation. Local audit
failure rolls back mapping and completion together; reconciliation can complete
the local commit only if the original approved conditions still hold. Startup
never creates: unsent work requires review, started work is recovered through reads.

Reservations protect this metadata database, not other connector installations or
external editors. Preflight is not an atomic remote snapshot or cross-PC lease.
No backend idempotency or universal exactly-once claim is made.

## Activity history and checks

Activity history lists real transfers and legacy synthetic experiments with paging,
status/type filters and stable selected IDs. Refresh history, select a row and
inspect it to restore its details. A newer pending preview does not hide completed
rows. Unattempted previews may be cancelled; attempted operations cannot be cancelled
into a retry. Legacy synthetic creation is retired; known-ID legacy reconciliation
remains read-only and never creates a real mapping.

An active/unresolved-operation message is a reservation safeguard. Transfer review
provides an **Open Activity history** action that resets status/type filters and
loads history through the background controller. Inspect the earlier row; only an
unattempted PENDING preview can be cancelled to free its reservation. No blocking
record is automatically cancelled, retried or overwritten.

On 4 November the owner confirmed dragging a Tally row now works, but preparation
reported a Bahi read failure. The old message combined connection, timeout and JSON
failures; the screenshot cannot establish which occurred. GET failures now identify
the endpoint and safe failure category without response bodies, credentials or party
IDs. Preview-read advice requests connection verification/reload rather than unrelated
activity cancellation. No automatic retries or live diagnostic requests were added;
the owner must retest and provide the new precise message if the failure persists.

History belongs to the selected runtime and binding generation. The agent's earlier
account-275 experiment lives in build/live-party-ui; the owner's separate default
runtime contains their own links/history. This feature does not merge databases.

Automated tests cover field decisions, payload/XML contracts, all four direction/type
combinations with fake remotes, Qt/button/drop review, exclusions, mapping audits,
local reservation races, backup/rollback, interrupted attempts, dispatch suppression,
atomic completion, history and restart. Existing query bounds, heartbeat and
architecture checks remain in the full suite. Actual totals and outstanding manual
gates are in [current state](../STATE_AND_PROGRESS.md).
