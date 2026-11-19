# Linked-party updates: Tally to Bahi

Select one linked customer or supplier on the Tally side of **Parties**, then
**Review linked changes → Bahi**. Supported eligible changes are included
automatically. Review the exact old/new values, use **Review all eligible changes**,
and **Confirm update** with the saved operator and normal-party/no-competing-editor
confirmation. Existing party 283 uses its saved account ID; it is never recreated.

The reverse review supports nonempty email, phone, address, State, country, PIN,
PAN, GSTIN and registration type, subject to the supplied Bahi field limits.
GSTIN requires the observed registration type. Bahi receives current scalar tax
values, not Tally's dated history; no mailing/GST effective date is requested for
this direction. Rename, classification, clears, balances, bank/bill settings,
contact-person/notes and unattended writes are outside this feature.

Current blank destination fields may be filled after exact approval, including
fields omitted during the original creation. Populated pre-existing differences,
destination edits, conflicts, inactive/system parties, unknown current values and
invalid source values remain protected. Values are never split, truncated or
translated. For example, a combined phone/email string over Bahi's 16-character
phone limit stays excluded; it is not converted into guessed contact fields.

GSTIN/PAN on SSS BUILDING PVT LTD were omitted by the earlier creation policy.
The owner's destination screenshot confirms address/State/PIN reached Bahi 283,
with GSTIN/PAN blank. The owner subsequently reports the linked reverse update
succeeded; Bahi's account-283 screenshot shows GSTIN 09CNXPP6229G1Z7 and PAN
CNXPP6229G on the same active supplier. This is owner-run destination acceptance
for that supplier/field subset, not all Bahi PATCH fields or customers. Restart
persistence and the update operation ID were not supplied.
No assistant repair write or new party creation was performed for this feature.

New transfers now include all supported applicable fields in either direction.
Older policies are versioned automatically on reopening/preparation; historical
exclusions are retained. See [current creation policy](AUTOMATED_PARTY_WORKSPACE.md#saved-field-policy).

## Execution and recovery

The [shared linked-update workflow](LINKED_PARTY_UPDATES.md) owns both directions.
Five-minute approval binds direction, source/target identities and observations,
payload, policy version and binding generation. Fresh reads check source, mapping,
business and destination values before recording the single attempt. The typed
adapter permits only `PATCH api-party.php?id=<saved account ID>` with approved
nonempty fields; it cannot create, delete, rename or modify invoices.

Read-back uses the known account ID, checks every included field and compares all
other returned values except the documented server-managed `updated_dtm` timestamp.
Only exact success advances per-field baselines and appends audit evidence in one
local transaction. Original link observations remain immutable. Both directions
share acknowledged field baselines, preventing an echo after a verified update.

Timeouts, malformed replies, preservation mismatches and failed local completion
retain their attempt and permit reads only. Startup never resends an update.
History and **Verify saved update (reads only)** restore durable results.
Inspecting an UPDATE in Advanced opens its before/approved/saved-read-back field
table in Operation details; verification refreshes that table through reads.
Double-clicking a saved transfer link loads its original field decisions. The
link JSON remains the original historical snapshot even after later updates. A
documented rejection remains visible, including missing `party:update` permission.
The Bahi API has no verified remote compare-and-swap or idempotency contract;
fresh reads do not eliminate the race with another editor after the check.

## Verification

Temporary SQLite, fake HTTPX and offscreen Qt cover customers and suppliers,
missing tax fills, repeated later edits, unchanged links, directional baselines,
invalid contacts, stale/cancelled approvals, permission refusal, lost responses,
ignored fields, unrelated mutations, restart and no resend. UI checks cover the
Tally-side review action, automatic inclusion, correct reverse commands, absent
Tally date controls and scrollable read-only operation evidence. No computer-use
automation or live remote write is part of this verification.
