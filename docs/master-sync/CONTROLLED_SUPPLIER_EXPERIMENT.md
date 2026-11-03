# Controlled supplier experiment (MST-004)

## Scope and authorization

The native Controlled party experiment tab prepares one generated synthetic
SUPPLIER in the explicitly selected destination. Direction has no default.
The owner selected **Tally → Bahi, business 52** for the first live trial.
The input has no source identity; it creates no cross-system mapping.
Existing discovery stays read-only. The owner reported that the real party link
shown in the earlier screenshot survived restart; preserve that link and invoice 69.

Both systems are owner-designated test environments. This permission does not
replace approval of the exact generated record. If an assistant conducts the
trial, show the actual preview in chat and wait for approval before Create.
Retain the test record; no deletion, patch, invoice posting or cleanup is enabled.

## Native workflow

Launch with the existing environment:

```powershell
.\.venv\Scripts\python.exe -m innoforia_tally_connector --runtime-dir build/live-party-ui
```

Verify connections and reopen the owner-confirmed Sundry Debtors/customer and
Sundry Creditors/supplier roots. Open Controlled party experiment, select a
direction, and Prepare preview. Preparation uses only business/company checks,
group exports and party-list reads. Name collisions or incomplete coverage block it.

The preview shows the generated India-date name and matching example.invalid
email, destination, group semantics, omissions and five-minute expiry. Enter a
named reviewer, then approve the exact record in the confirmation dialog. Changed
direction, payload, binding/session generation, destination/group context or an
expired preview requires renewed review. Unsent work is never created on startup.

Bahi accepts only party_type, account_name and email in POST api-party.php. The
server selects the SUPPLIER group; its code/ID is not exposed and cannot be
client-selected. Read-back verifies the observable SUPPLIER semantics, not an
invented group identifier. party:create permission remains a live gate until tested.

Tally accepts a typed single-ledger Create request under the verified Sundry
Creditors root in SIS Dummy. The existing export transport remains export-only.
The strict builder rejects Alter/Delete, multiple masters, balances and arbitrary
import XML. The template follows the official
[master XML example](https://help.tallysolutions.com/sample-xml/); actual create,
email acceptance and receipt behavior remain live-unverified for Tally.

## Durable execution and recovery

Metadata migration 3 adds experiment previews/approvals, unique external attempts,
target receipts and comparison evidence. The existing migration runner takes a
SQLite-consistent backup before upgrade; links and audits remain in place.
The shared operation journal records APPLYING and the approved payload digest
atomically before network transmission. Queue arguments remain operation IDs.
Transactions never span HTTP. There is at most one attempt per experiment in
this journal; no backend idempotency or universal exactly-once guarantee is implied.

Returned identifiers are saved before detail verification. Bahi reads the returned
account ID. Tally uses returned MasterID when available, then resolves/reads GUID;
only a positive create receipt permits resolving a single new GUID against the
pre-import baseline. A matching name after an uncertain response is not identity
evidence and never authorizes recreation. Counter receipts alone are not success.

Exact name, SUPPLIER classification, email and observable group semantics must
match. Mismatches stay BLOCKED. Timeout/disconnect/malformed receipt or interruption
after an attempt is OUTCOME_UNKNOWN. Known identity permits read-only reconciliation;
unknown identity requires investigation. An unresolved experiment blocks another
preview for the binding. Generic completion and outer error handling cannot replace
an external outcome with a retryable read result. Startup performs no create.

Use Inspect last experiment after restart to retrieve durable results. Read-only
reconciliation never sends a create. No unlink/relink or remote correction exists.

## Verification and remaining gate

Offline contracts cover exact Bahi payloads, denial, redirect, timeout, malformed
and identifier-bearing error receipts; Tally single-ledger XML guards and receipt
failures; serialized typed imports versus competing exports and changed group
context rejection; SQLite duplicate delivery, changed/expired approval, no-direction,
superseded previews, mismatch, known-ID reconciliation, interrupted boundaries,
startup suppression and preservation against generic error handling. Native tests
cover cancel, explicit approval digest and Qt's string conversion of direction
through validated commands. Existing migration, matching query bounds, discovery,
GUI heartbeat and architecture tests remain required.

The owner approved the exact generated preview in chat; the native confirmation
then submitted one Bahi create. HTTP 201 returned account ID **275** for
MST004-SUP-20261102-d5a58e36, email mst004-d5a58e36@example.invalid.
Actual detail GET matched all enabled fields and observable supplier semantics;
the party was active. The native screen restored SUCCEEDED, target ID, reviewer
surjeet and all comparisons after clean Quit/restart. Create remained disabled.
ID-based read-only reconciliation after restart also matched the same fields.
The isolated build/live-party-ui journal contains one attempt and zero mappings;
the owner's real link in the separate user runtime was not modified. The retained
record has not been deleted. See [sanitized evidence](evidence/supplier-create-bahi.json).

Full offline suite: **134 passed, 1 opt-in live test skipped**. Focused persistence
and UI checks: **23 passed**, including two abrupt subprocess exits. Documentation
link/fence and whitespace checks are recorded in [current state](../STATE_AND_PROGRESS.md).
This passes only the first bounded supplier experiment. Tally's destination path, customer
creation, updates, live crash injection, full MST-004 and frozen Python 3.13
certification remain separate gates.

See the [party handbook](../api/bahi/handbooks/API-PARTY-DEVELOPER-HANDBOOK.md),
[read/link foundation](READ_LINK_FOUNDATION.md) and
[read-only discovery evidence](READ_ONLY_DISCOVERY.md).
