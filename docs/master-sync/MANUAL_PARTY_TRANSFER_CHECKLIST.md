# Owner manual verification: automated party workspace

Use Bahi business 52 and SIS Dummy. Automated checks use fake remotes; these
checks establish behavior in your installation. The mailing repair used export-only
diagnostics, with no assistant creates, updates or computer-use verification.

## Setup once

1. Quit the old connector, including its tray instance. Launch the same runtime:

   ```powershell
   .\.venv\Scripts\python.exe -m innoforia_tally_connector
   ```

   Keep Local AppData/InnoforaiTallySync and its journals. Migration 5 takes a
   consistent backup before upgrading. Do not replace/delete the database.
2. Existing confirmed identities/groups should reopen automatically after checks.
   For first setup only, use Settings to verify and explicitly confirm the observed
   roots. Save operator `surjeet` and review/save the contact-field policy once.
   Tax fields are currently excluded; optional omissions receive audited reasons.
   If transfers are not set up, Parties shows Finish transfer setup; its buttons
   open Settings at Your name. Enter your name and click Save operator and transfer
   policy. A blank name must show a visible message and start no transfer.
3. Confirm Parties loads automatically. Quit/reopen and check that no Verify,
   group confirmation, operator entry or Load click is required. Saved links must
   retain your earlier real link. Activity > Advanced retains legacy history.

## Transfer and inspect

Use distinct, unlinked test parties. Do not reuse invoice 69 or recreate prior
experiment records. Verify these four cases across your selections:

| Source | Type | Expected destination classification |
| --- | --- | --- |
| Bahi | Customer | Confirmed Sundry Debtors root in Tally |
| Bahi | Supplier | Confirmed Sundry Creditors root in Tally |
| Tally | Customer | Bahi server-configured CUSTOMER group |
| Tally | Supplier | Bahi server-configured SUPPLIER group |

1. Check/select parties on one side, then Transfer; also test dragging a selection
   to the opposite NEW-party area. Try one party and multiple parties. A batch
   cannot mix directions or exceed 100 unique sources.
2. Inspect the summary: Ready, Already linked and Needs review. Select a Ready row
   to inspect exact included values, destination/group and policy omissions. Close
   once without confirming; no create should occur.
3. Include a selection containing an already-linked party and a destination-name
   candidate. Only Ready parties can be approved. Candidate matches require an
   explicit existing-link review; they cannot be dismissed to allow creation.
4. Reopen/prepare a summary. Confirm the batch-level normal/non-system statement
   only if true for every applicable Ready source. It starts unchecked. Confirm
   transfer once; no per-party operator entry or field-reason editing is needed.
5. Inspect each result and target ID. Verify the actual destination name/type and
   every included contact/mailing value, including string leading zeroes. Omitted
   tax fields are not verified tax round trips. Successful and failed rows remain
   distinct. No record should be created twice.
6. Check Activity and Saved identity links: source/destination IDs, operator,
   included fields, omission reasons and eligibility confirmation. Quit/reopen;
   completed results and mappings must remain. Selecting a linked source again
   should report Already linked, with no additional destination record.
7. For a multi-party batch, try Stop unsent transfers: the current operation may
   finish, later unsent rows stop, and completed targets remain. Do not inject live
   crashes/timeouts; uncertain cases already have offline coverage.

## Expected exceptions

- Airtel India / Bahi 281: retain the existing Tally ledger (GUID ending 0000016b).
  The owner has corrected its mailing values. Its remaining address mismatch came
  from the legacy export replacing an en dash with a question mark. The fixed
  UTF-16 production reader now matches all approved values on the same GUID.
  No further ledger edits are needed: restart the connector and Check unresolved
  results (reads only). Verify Airtel becomes SUCCEEDED, its link appears and both
  survive restart. Do not create a replacement or change punctuation to hide the
  mismatch. The new dated builder still needs a distinct-record live trial.
- The earlier MST004-SUP-20261102-7a5d3198 country trial already completed after
  owner correction and read-only checks. Do not recreate it. Test the dated fix on
  a distinct unlinked party only after resolving the current mismatch. Inspect
  address, state, country and PIN directly in Tally, then restart/check persistence.
  New summaries show the company-derived mailing date in destination/group details.
  Live acceptance of this new create shape remains pending.

- Changed identity/classification: transfers stop and Settings explains the issue.
- Read failure: restore connection access and Refresh; do not cancel unrelated work.
- Expired summary: Refresh summary for review prepares new values; confirm again.
- Paused batch: use Activity > Check unresolved results (reads only), then Review
  remaining parties for a new summary. This never recreates an attempted source.
- Missing target identity or unresolved mismatch: retain the operation and send
  its details. Do not delete journals or create a replacement manually.
- Old unattempted drafts are superseded automatically. Attempted/uncertain legacy
  records retain history and can block new writes until reconciled.

## Screenshots to provide

Send Settings/policy and Parties after automatic startup; one mixed batch summary;
a completed batch with target IDs/field comparisons; the corresponding destination
records and saved links; and Activity/links after restart. For a blocked record,
include its expanded details and exact message. Never include credentials.

Earlier owner screenshot: actual-party Tally-to-Bahi record
9b70c10d-0ade-45c5-8da2-99027a69dec9 reported SUCCEEDED. Its destination detail and
restart evidence remain pending. The earlier agent account-275 experiment used
`--runtime-dir build/live-party-ui`; that isolated history is not merged here.
