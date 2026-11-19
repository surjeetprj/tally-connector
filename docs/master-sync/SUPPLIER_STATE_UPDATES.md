# Supplier State updates: Bahi to Tally

This original State workflow is now a subset of
[linked-party field updates](LINKED_PARTY_UPDATES.md). Current controls use field
checkboxes, **Review selected changes** and **Confirm selected updates**. Existing
State approvals/results retain their semantics and hashes; the sections below
record the State-specific contract and owner evidence.

The owner verified the [controlled trial](CONTROLLED_STATE_UPDATE.md) directly in
Tally and after restarting the connector. The regular feature supports successive
approved State changes on a confirmed supplier link. It retains the verified
single mailing-record structure and the shared execution/recovery engine. Both
dated and undated entries are supported, preserving date presence/value exactly.

## Use

1. Select one linked Bahi supplier in Parties and choose **Review linked changes →
   Tally…**. The connector loads current values and the latest update result for
   that supplier automatically.
2. For a first entry in an empty native mailing aggregate, enter its effective
   date as YYYY-MM-DD. The field starts blank; no business date is inferred.
   Leave it blank for ordinary changes to populated mailing entries.
   For an eligible **Bahi changed** State, choose **Review State update…**. Inspect
   the exact old/new State, date when creating the first entry, destination and existing GUID. The saved operator is
   reused; confirm normal parties/no competing editor and **Confirm State update**.
3. Read-back verifies State and preservation before completion. The differences
   refresh automatically. **Refresh changes** checks later edits without writing.
   **Load latest State update** restores the selected supplier's durable result.

Each update requires a fresh five-minute exact preview and approval. Updates are
never sent on refresh, opening a review, or startup. Attempted/uncertain updates
use **Verify saved update (reads only)**; never approve another attempt of them.
Cancel affects only an unsent preview. Activity retains all historical operations.

## State baselines and conflict handling

The first update compares each side with its own original link observation.
After verified completion, a separate acknowledgement holds the approved source
and verified target State. Only State uses that newer baseline. Original identity
links and their confirmation evidence remain unchanged, and other fields retain
their original observations. A pre-existing difference is not creation/update
permission. Only an eligible nonempty Bahi-only change can be approved.

A Tally edit is **Tally changed**; divergent edits on both sides are **Conflict**.
Neither can be overwritten through this feature. Null/empty/absent State values
remain clearing requests requiring separate support. Policy exclusions, inactive
or system parties, renamed identities and changed classification block writes.
Failed, blocked, cancelled or uncertain work does not advance the baseline.

The approval includes its predecessor acknowledgement ID along with existing
source/target/native/context evidence. Transactional checks reject a stale baseline
at reservation, attempt and completion. One unresolved write still reserves the
binding. Duplicate delivery cannot repeat an attempted update; each genuinely new
change receives a new durable intent and fresh approval.

## Persistence and supported contract

Migration 7 takes the existing consistent backup, rebuilds the State audit table
to permit multiple operations per link, and preserves evidence byte-for-byte.
Operation identity remains unique. The old successful controlled trial immediately
serves as the State baseline; its approval hash and original observations are
unchanged. Audit insertion, baseline advancement and local success are one commit.
Known-ID read-only recovery retains these guarantees after interruption/restart.

No new XML contract is introduced: the current name is resolved/rechecked from the
saved GUID, the one existing mailing entry/date is retained, and only State is
changed. Native preservation and the narrow observed metadata rules still apply.
An existing entry without APPLICABLEFROM remains undated. Empty date nodes also
retain their representation; populated dates must still be valid and not future.
The observation reader supports the same single undated entry. New creations still
require their approved creation date in verification. An unexpected server-added
date fails preservation; it is never silently accepted or followed by a retry.
The connector never fills in today's date or another default.
An empty native aggregate is not a populated undated entry. It requires a
user-chosen valid, nonfuture effective date. The immutable preview, typed payload
and native read-back bind that exact date and State; another date or extra field
fails validation. Dates of populated entries cannot be changed here. The field is
cleared after completion so it is not silently reused for a later State change.
The owner-approved Apollo record
`a2ba296a-c9f2-411d-b53b-2ede7aa39c79` showed Tally ignoring a State-only write into
such an aggregate: retained read-back had no State, while version/import metadata
changed. The earlier offline fake's acceptance assumption was incorrect for this
case. The old attempt is never resent or turned into success.

### Closing the known unchanged failure

For a BLOCKED empty-mailing attempt whose State comparison is false, the named
operator can confirm normal parties/no competing editor and **Close unchanged
failed update (reads only)**. This acknowledges a local closure, not an idempotency
or remote-version guarantee. Two fresh native reads must agree and match the
original contents, permitting only the already verified import/version metadata
representations. A changed ledger, applied State, populated original entry or
unknown outcome blocks closure. The journal becomes FAILED with its original
attempt/approval retained; reviewer and read evidence are appended atomically.
Closure never advances the State baseline and is not automatically dispatched on
restart. A new dated preview is a separate operation requiring fresh approval.
No successful live undated or first-entry alteration is claimed from offline tests.

The owner subsequently approved dated first entry
`9effcb23-5bd9-4bb2-9e84-67e99782872e` for Apollo: date 20261101, State Kerala.
Retained live exports verify the exact date/State and unchanged other business
values. Tally additionally emitted empty PINCODE, MAILINGNAME and COUNTRY nodes;
the original strict shape check blocked local completion. The repaired verifier
permits only these three absent-to-empty additions for an approved minimal
date+State first entry. Populated/whitespace values, attributes, children, duplicate
nodes, changed dates and other native fields still fail. Ordinary updates retain
exact preservation. The original snapshot/hash remains unchanged and the retained
evidence passes; use read-only reconciliation, never another import. Runtime
completion has not been changed by the assistant.
The subsequent owner screenshots show this same record SUCCEEDED, all comparisons
true, and Kerala directly in Tally. This confirms first-entry reconciliation for
the approved date/State subset. Blank address and Country Not Applicable are not
missing approved fields: address/country were outside this State-only operation.
No broader linked-field update or new restart acceptance is inferred.
The repair passes 124 focused checks and the full offline suite (494 passed,
one opt-in live skipped), including reconciliation of a saved failure without a
second import or approval rewrite. Retained owner evidence passes in a read-only
local check; no assistant-driven write or runtime status edit ran.

The first-entry extension passes 110 focused XML/application/native UI checks,
including old approval-hash compatibility and repeated changes after creating
the first entry. A shared completion race exposed by the full suite was repaired:
the writer reservation precedes reading attempt evidence so SQLite can wait before
establishing a WAL read snapshot. 101 batch/journal/State regressions pass with
six competing-approval cases. Final full suite: **480 passed, one opt-in live
skipped**. Documentation and whitespace checks pass. No live import or runtime
closure was performed; Apollo's native shape and dated payload were checked with
exports and local validation only.
This does not establish remote conditional writes or exclude races with another
editor. Customers, other fields, tax, clears, multiple mailing-history records,
reverse updates, batches of updates and unattended synchronization remain outside
this feature. No Bahi write adapter or BahiAI dependency is added.

## Owner acceptance

19 November undated extension: 107 focused offline checks and the full offline
suite (458 passed, one opt-in live skipped) pass, including the
actual typed gateway with fake HTTPX, temporary SQLite and offscreen Qt. A fresh
company/GUID-scoped export for Apollo source 277's target ending 0000013e built
and validated an undated State payload locally; no import was sent. This confirms
the native shape and request construction, not live alteration behavior. Per the
owner's updated instructions, no additional manual trial is required; test-system
live regressions are authorized if needed. Existing application approval remains
required for ordinary feature use.

Verification in the existing .venv: **87 focused checks passed; full offline suite
425 passed, one opt-in live test skipped**. Tests use temporary SQLite, fake HTTPX
responses through the typed gateway and offscreen Qt; no live write was performed.

The controlled source-282 State trial and restart are owner-verified. On 19 November
the owner supplied screenshots for the second live update, **Delhi to Haryana**,
record `ec02114b-7aa7-46a5-bf70-b2fe4901ef81`. The normal feature shows SUCCEEDED
with all seven comparisons true, State baseline saved and original link/audit
preserved. Tally directly shows Haryana with unchanged visible address/country/PIN.
Restart persistence of this second result and the independent-edit conflict check
remain pending. The checklist below describes the feature acceptance cases; steps
1 and 2 have this live evidence.

1. Change State on the same test supplier in Bahi. Refresh changes; expect **Bahi
   changed**, with Delhi as the previous verified State. Opening review sends nothing.
2. Approve that exact update once. Check SUCCEEDED, State in Tally, unchanged
   address/country/PIN and accounting values. Refresh should show Already matches.
3. Restart. Load latest State update and confirm its result remains; Activity must
   retain both operations and the original saved link.
4. On a test record, edit Tally State independently. Review must show Tally changed
   (or Conflict if Bahi also changed) and offer no State write for that conflict.

No assistant-driven live write or computer-use automation is part of implementation.
