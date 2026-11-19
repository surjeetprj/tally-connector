# Supplier State updates: Bahi to Tally

The owner verified the [controlled trial](CONTROLLED_STATE_UPDATE.md) directly in
Tally and after restarting the connector. The regular feature supports successive
approved State changes on a confirmed supplier link. It retains the verified
single dated mailing-record contract and the shared execution/recovery engine.

## Use

1. Select one linked Bahi supplier in Parties and choose **Review linked changes →
   Tally…**. The connector loads current values and the latest update result for
   that supplier automatically.
2. For an eligible **Bahi changed** State, choose **Review State update…**. Inspect
   the exact old/new State, destination and existing GUID. The saved operator is
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
This does not establish remote conditional writes or exclude races with another
editor. Customers, other fields, tax, clears, multiple mailing-history records,
reverse updates, batches of updates and unattended synchronization remain outside
this feature. No Bahi write adapter or BahiAI dependency is added.

## Owner acceptance

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
