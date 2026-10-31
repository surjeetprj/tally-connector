# Master matching rules

Status: planned behavior for the supervised milestone. See
[the field matrix](MASTER_FIELD_MAPPING.md) for supported identity and content fields.

## Meaning of the choices

| Choice | Effect |
| --- | --- |
| **LINK EXISTING** | Confirm that one Bahi record and one Tally record represent the same business entity; no remote write |
| **CREATE NEW** | Plan a destination create after checking prerequisites and existing candidates; requires a write preview |
| **SKIP** | Exclude this record from the current run; retain the reason; do not mark it synchronized |
| **UPDATE LINKED** | Plan only allowed changes to a verified existing link; separate from link confirmation |

## Identity and candidate rules

Use the business/company binding plus master type and stable IDs. A confirmed
mapping must be unique on both sides within its binding/type; duplicate mapping
attempts fail transactionally. Keep company generation/restore context so stale
identities do not silently attach to restored data.

1. Look up the saved mapping first. Verify both target identity and classification
   before reuse. Renames retain identity; they do not trigger another create.
2. For unmapped records, suggest candidates using the evidence below. Suggestions
   never establish identity without user confirmation.
3. Show all plausible candidates and relevant differences. Do not choose the first
   result merely because its name or GSTIN matches.
4. Recheck candidate identity and mapping availability before confirmation and
   again before applying dependent writes.

| Type | Candidate evidence | Why it is not proof |
| --- | --- | --- |
| Party | Compatible classification, name, GSTIN, address/state | Branches may share GSTIN; names can repeat; tax IDs can be absent or incorrect |
| Group | Name plus mapped parent hierarchy | Bahi group names are not unique; identical names under different parents differ |
| Item | Name, confirmed group/unit, supported identifiers | Names/barcodes may repeat; incompatible units/types make a match unsafe |
| Unit | Explicit code/name, quantity meaning and precision | `Nos.`, `pcs` and similar names need a business-confirmed equivalence |

Case/spacing normalization is for search suggestions only. Do not strip punctuation,
rewrite tax identifiers or truncate names in write payloads to force a match.

## Initial baseline

Initial scans describe records observed now. They do not prove creation dates or
that concurrent paginated reads form a complete snapshot. Display partial reads
and failed pages, and prevent a bulk all-clear claim when coverage is unknown.

For a confirmed link, save the source and destination observations separately.
If fields differ, show them and require a later explicit update decision or mark
them as intentionally different according to the field policy. Do not record an
acknowledged equal-content baseline for unequal records.

## Conflict and lifecycle cases

| Situation | Required behavior |
| --- | --- |
| Multiple candidate matches | Require explicit selection or skip; no automatic link/create |
| Destination name collision during create | Stop and inspect existing record; no silent rename, merge or fallback |
| Existing mapping points to missing identity | Investigate deletion/restore/access scope; no replacement create |
| Source renamed, same identity | Show allowed name update with collision check |
| Both sides edited a supported field | Show baseline/source/destination differences and require resolution |
| Source changed after preview | Invalidate the preview and reload the affected record |
| Destination changed after preview | Conflict/repreview; do not silently overwrite |
| Inactive/system party | Block update under the documented resource restrictions |
| Parent group unresolved | Block dependent group/item only |
| Existing item's unit/group changed | Block in this slice; require a separate reviewed migration policy |
| Company/business selection changed | Discard stale callbacks; preserve original operation binding |
| Unknown create outcome | Investigate saved intent and authoritative identity evidence; never POST again from name-search absence alone |

Before confirming a conflict resolution, re-read the destination and apply the
same expected-version/content guards. Choosing a winner in the UI does not make
an unprotected remote update atomic. Do not offer an automatic overwrite option
while the destination lacks the required protection.

## Audit and correction

Record who confirmed a link, when, binding, entity identities, chosen direction,
field policy and the observations used. Store only necessary business snapshots
under the runtime data policy; redact diagnostics and support exports.

An incorrect link is not fixed by deleting history. Block affected pending work,
review dependent item/voucher references, then record an explicit audited mapping
correction. Applied operations retain the identities used at execution time.
No bulk unlink/relink or destructive merge belongs in the first release.
