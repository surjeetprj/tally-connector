# Controlled supplier State update

Historical trial: the owner has now verified Delhi/unselected details directly in
Tally and SUCCEEDED after restart. The normal UI is superseded by
[repeatable supplier State updates](SUPPLIER_STATE_UPDATES.md); the original record
and evidence remain retained. Labels/checklist below describe the original trial.

Implemented 18 November 2026. This is one controlled update experiment following
[linked-party review](LINKED_PARTY_CHANGES.md), not general party update support.
No assistant-driven live alteration ran. The owner subsequently ran the approved
source-282 trial; see the recovery evidence below before sending any new work.

## Owner checklist

For the already attempted record `bcc0b354-14ab-4f7b-a1c1-cfc5d277d778`, restart
the repaired connector, open the linked Reliance review, **Load latest State
test → Verify saved update (reads only)**. Do not prepare or send it again.
Confirm SUCCEEDED, inspect State and other fields in Tally, then check persistence
after restart. The following preparation steps describe the original trial flow.

1. Quit/restart the updated connector with the existing .venv. Startup migration
   6 takes a consistent backup of a recognized older metadata DB. Keep the backup,
   journals and the same InnoforaiTallySync runtime directory.
2. Select linked Reliance source 282 in Bahi and open **Review linked changes →
   Tally…**. Click **Prepare State-only update test…**. This performs reads and
   saves an immutable preview; it sends no import.
3. Inspect destination/company/GUID, source ID, old/new State and expiry. The
   observed proposal is empty to **Delhi**, existing GUID ending 0000016c, retaining
   mailing date 20260401. Test Close/Cancel without approving: no remote change.
   Preparing again supersedes only an unattempted State preview, retaining history.
4. Only when approving that exact test, enter the named reviewer, confirm normal
   business parties/no competing editor, and click **Approve this one State
   update**. The final dialog asks to send once. If the assistant conducts a live
   trial, it must first show the completed preview in chat and await approval.
5. Inspect result/comparisons and Tally directly. State should be Delhi; all other
   native data must remain unchanged. A preservation mismatch is BLOCKED even
   when counters look successful. Never resend an attempted update. Use **Verify
   saved update (reads only)** for uncertainty or unfinished local completion.
6. Restart and use **Load latest State test**, or Activity > Advanced > Controlled
   state updates. Check durable outcome/evidence and no second import. Original
   link/confirmation observations remain intact; new evidence is appended separately.

Implementation and export-only checks consumed no live approval. Earlier supplier
creation permission does not approve this alteration.

## Scope and targeting

Only the confirmed Bahi-52/SIS-Dummy test pair, supplier root Sundry Creditors,
one nonempty exact Bahi State, one existing mailing entry, and one successful
controlled trial per link are supported. Rename, customer/reverse updates, tax,
other contact fields, clears, multi-record mailing history and unattended updates
remain disabled. No Bahi PATCH or generic XML import route was added.

The [official Alter example](https://help.tallysolutions.com/sample-xml/) selects
a ledger by NAME with Action Alter. This implementation resolves the current name
from the confirmed GUID, then checks company, native identity/version/content and
case-insensitive name uniqueness under the one serialized gateway lock. GUID is
also supplied in the typed request. A missing GUID never falls back to a name.
This does not establish GUID-only selection, remote compare-and-swap or a lease;
external-editor races remain possible. The explicit single-editor acknowledgement
is part of this controlled trial, not proof of backend writer ownership.

The [official dated aggregate schema](https://help.tallysolutions.com/developer-reference/release-3-tdl-enhancements-tally-prime/what-are-the-changes-in-xml-tags/)
documents mailing fields. The payload resends the one existing mailing entry with
only State replaced and its original date retained. Unknown structures, multiple
entries, missing/future dates and invalid strings block preparation. The ledger
payload contains only GUID and the mailing entry under explicit company context.
Strict validation rejects Create/Delete, extra ledgers, accounting fields, changed
identities or other XML. UTF-16 remains the wire encoding. No BahiAI code was used.

## Preservation evidence

Full company/GUID-scoped native snapshots are bounded at 1 MiB per ledger and
stored only in local runtime evidence. FETCH * exposes NAME as an attribute;
the matching scalar projection is retained for comparison. Nine observed native
tax/default scalar tags contain forbidden U+0004 references. The snapshot reader
preserves these as reserved opaque evidence tokens; it never removes them,
imports them or treats them as business values. The general parser remains
strict. Other controls, declarations/entities and token collisions fail closed.
Mailing entries with such tokens cannot enter a payload.

Before/expected/actual comparisons retain ordered children, scalar whitespace and
attributes; only formatting whitespace between elements is ignored. Root
AlterID is omitted from after comparison. Expected differences are the one dated
State and its scalar LEDSTATENAME projection. After the owner-run trial, two
narrow representation rules also apply: a previously absent LEDSTATENAME may
appear with the exact approved State and optional TYPE String; an existing empty
scalar REMOTEALTGUID may become this same ledger's GUID with identical attributes.
An existing projection must remain present; unsupported attributes, foreign GUIDs,
changed nonempty import identity and duplicate nodes fail. These rules compare
temporary trees without rewriting the approved snapshot or payload hash.
Every other exported native field/aggregate must match. Failure snapshots are durable, including unexpected
unselected-field changes and verification preceding a failed local audit commit.
Accounting values may appear in read-only preservation evidence; they are never
copied into the write payload or customer fixtures committed to the repository.

## Shared journal and recovery

The existing operation/outbox/attempt engine handles UPDATE previews and one
attempt. Approval binds exact State, source/target/link/native snapshots, policy
version, reviewer, normal-party confirmation, binding/generation and five-minute
expiry. Changed content/context/policy, cancellation or missing approval causes
zero imports. The known target GUID is durable before transmission. No SQLite
transaction spans HTTP, and duplicate delivery/clicks never send another attempt.

Malformed/error/counter-only responses or disconnects retain uncertain outcome
and known identity; read-back is authoritative. State, GUID/context, classification,
eligibility and native preservation must pass. Migration 6 adds verification and
unique per-link trial-audit tables. Audit and local success commit atomically;
original links/audits are unchanged. Audit failure permits reads, not another write.
Competing batch/single-record writes share the binding guard. Restart never applies
unsent updates: renew the preview/approval; attempted work recovers through reads.

## Actual checks and remaining gate

Existing .venv Python 3.13.15. **51 focused checks passed; full offline suite
413 passed, one opt-in live test skipped** after the preservation repair.
An existing UI test now waits for the asynchronous saved-link refresh instead of
assuming the batch-state event means it has already completed.
Coverage includes actual typed gateway/
HTTPX XML with fake remotes, native preservation, Unicode, gateway concurrency,
approval invalidation/expiry, lost acknowledgement, no second attempt, local audit
failure, migration backup/rollback and preserved original links. Offscreen Qt
tests cover preview, explicit approval, execution, result and restart retrieval.

Export-only inspection on existing GUID ending 0000016c captured 15,393 UTF-8
snapshot bytes and built/validated an 867-byte State payload, retaining date
20260401. The payload was not sent. No live import, runtime migration/journal edit,
computer-use automation or installer build ran during implementation.

The owner-approved trial changed State to Delhi but originally remained BLOCKED:
only ALTERID, the newly projected State and empty-to-self REMOTEALTGUID differed
in the retained native snapshots. The repaired verifier passes those retained
snapshots in a read-only local check. The [official import-definition documentation](https://help.tallysolutions.com/import-file-definition-attributes/)
identifies RemoteAltGUID as import identity metadata; the particular empty-to-self
transition is observed trial evidence, not a universal Tally guarantee. A regression
reconciles the old approved record without changing approval evidence or sending
a second import. No runtime journal was modified during this investigation.

The latest owner screenshot confirms this same record is **SUCCEEDED**, all seven
comparisons true, with original link/audit preserved and new evidence appended.
The owner subsequently confirmed both direct Tally inspection of Delhi/unselected
fields and persistence after restart, with screenshots. This completes acceptance
of this single State experiment.

The repeatable State workflow is tracked separately. Historical mailing changes,
other fields/directions and automatic sync remain separate gates.
