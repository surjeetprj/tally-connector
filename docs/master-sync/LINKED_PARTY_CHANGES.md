# Linked-party changes: first read-only milestone

The current screen also supports [selected field updates](LINKED_PARTY_UPDATES.md).
The original read-only comparison and State experiments below are historical
milestones; current verified baselines advance separately for selected fields.

Implemented 18 November 2026, as the first bounded step toward supervised updates
in MST-004. Original difference review is read-only. A subsequent
[controlled supplier State experiment](CONTROLLED_STATE_UPDATE.md) added a separate
exact preview/approval and is owner-verified. The current
[supplier State feature](SUPPLIER_STATE_UPDATES.md) supports repeatable approved
State changes using a separate verified State baseline. Other-field writes remain
disabled. Existing create and
reconciliation actions keep their current scope.

## Owner workflow

1. Restart the updated connector and let the saved connection/parties load.
2. In Parties, select/check exactly one already-linked **Bahi** party, such as
   Reliance source 282. Click **Review linked changes → Tally…**.
3. Inspect Bahi now, Tally now and each field's review status. Select a field to
   see each side's separately saved value at linking, current value and reason.
4. Source 282 now matches following the verified State update. Later Bahi-only
   State edits show **Bahi changed** relative to that verified State. Opening or
   closing review sends no write. Use **Review State update…** for an eligible
   change. Do not repeat creation for an existing linked party.

## Implemented behavior

The application resolves the persisted confirmed link by binding and Bahi ID,
verifies connection identities and reads details by the saved Bahi ID/Tally GUID.
It rejects stale observations and wrong returned identities; a missing GUID is
an error, never a name-match fallback. There is no remote write capability in the
review workflow, and saved links/observations/audits are not modified by review.

Each side is compared with **its own saved observation**, using the last verified
State acknowledgement for State when present and original linking observations
for all other fields. Identity confirmation
did not establish that both contents were equal or approve field ownership:

| Review status | Meaning |
| --- | --- |
| Bahi changed | Bahi value changed; Tally is unchanged relative to its saved observation. Candidate for future approval only. |
| Already matches | Current values match exactly; no update proposed. |
| Tally changed | Destination changed since linking; no overwrite proposed. |
| Conflict | Both sides changed differently; preserve destination edits and require resolution. |
| Pre-existing difference | Values already differed when linked; not a new Bahi edit. |
| Unavailable | A current or saved representation is unavailable; absence cannot be inferred. |
| Clearing needs review | Source became null/empty/absent; no permission to clear destination fields. |
| Excluded by policy / Invalid / Blocked | Saved field choice, value validation or eligibility/context prevents a candidate. |
| Out of scope | Rename/tax fields are displayed but are not update candidates. |

Contact/mailing candidate fields follow the saved to-Tally field selection, which
remains a creation policy and does **not** approve updates. Inactive/system records,
unavailable Bahi active eligibility, renamed records and classification changes
block candidate updates. Null, absent, empty and unavailable values remain distinct;
no whitespace, punctuation, Unicode or address values are rewritten. A missing
operator/policy is explained. Tally system-flag unavailability does not become a
verified normal-account claim; renewed eligibility confirmation will be necessary
in an eventual write approval.

PARTY_CHANGES uses the existing command/outbox/Huey worker. Durable arguments
contain the Bahi identity and binding, not a client-selected target or raw payload.
Repeated reads coalesce per source; different source requests keep separate IDs.
The controller rejects older requests/binding generations. Binding re-verification
hides old reviews; errors leave no stale successful review visible. Results are
transient read evidence and are recomputed on request, not durable approvals.
No schema migration, dependency/environment change or second queue was introduced.

## Documentation-first contract findings and next gate

The [official ledger alteration example](https://help.tallysolutions.com/sample-xml/)
uses a name-targeted Ledger element with Action Alter. That example does not
establish GUID-only targeting on this installed release. The
[official dated aggregate schema](https://help.tallysolutions.com/developer-reference/release-3-tdl-enhancements-tally-prime/what-are-the-changes-in-xml-tags/)
lists mailing ApplicableFrom/Address/State/Country/PINCode, but does not establish
whether a partial alteration merges or replaces existing mailing data/history.
No BahiAI code was consulted or copied for this milestone.

Before enabling Apply: verify exact company/GUID targeting and dated mailing
alteration semantics (preservation of unselected fields and history, effective
date policy, unavailable/clearing behavior) in a narrowly approved controlled
experiment. Then extend the **shared** durable operation lifecycle with immutable
before/after approval, fresh source/destination/version/context checks, a persisted
attempt, known-ID read-back, uncertainty/reconciliation and atomic local completion.
Do not infer conditional updates, writer ownership or race-free behavior from a
local AlterID comparison. No automatic/unattended or reverse updates are enabled.

## Verification

Existing .venv Python 3.13.15. **30 focused checks passed; full offline suite
363 passed, one opt-in live test skipped.** Unit tests cover separate baselines,
conflicts, exact Unicode/whitespace, null/absence/legacy availability, policy,
eligibility and wrong-context/stale/read failures. Offscreen Qt integration exercises
the native screen/controller/shared worker, actual readers with fake remotes and
temporary SQLite; it checks responsiveness, errors, binding invalidation, separate
request coalescing and unchanged links/audits. No computer-use automation ran.

A GET/export-only call through the new application workflow used the saved source
282 link and GUID ending 0000016c, with SQLite mode=ro. State was **Bahi changed**;
address/country/PIN matched; null phone/email remained pre-existing differences.
No credentials/raw customer values were retained in fixtures or output. No runtime
journal edits or remote writes ran. The owner subsequently supplied a native
review screenshot for source 282: State Delhi versus Tally empty is Bahi changed;
address/country/PIN match, null phone/email remain pre-existing differences and
rename/tax fields remain out of scope. This verifies screen-level review, not
approval, update execution or an altered destination record.
