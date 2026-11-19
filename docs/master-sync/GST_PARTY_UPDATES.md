# Linked-party GST updates: Bahi to Tally

GSTIN and registration-type updates use the existing selected-field update
workflow, journal, approval, serialized gateway and per-field acknowledgements.
They are enabled for confirmed customer/supplier links in the currently supported
business-52/SIS-Dummy test binding. This does not enable tax fields on party
creation, reverse updates, GST rates, transactions or unattended writes by itself.
The later [all-applicable-fields creation increment](AUTOMATED_PARTY_WORKSPACE.md#saved-field-policy)
now supports the exact first-entry schema on new ledgers, with an approved initial
applicability date and exact read-back; new-tax-ledger live acceptance remains
separate from the update evidence below.

## User workflow and limits

The normal desktop now includes an eligible GST pair automatically along with
other eligible Bahi changes. Field selection and separate blank-fill acceptance
are folded into the one exact update confirmation. The earlier explicit-selection
description below records the prior interface; date, source-value and history
requirements remain current. Owner screenshots verify Apollo's actual GST update
`bf38c56c-7392-44b6-ad1d-f5f801ccf4b1` succeeded, with Regular and
32AAFCA7004C2ZF visible in Tally, effective 20261101.

In **Review linked changes**, explicitly select GSTIN or registration type. The
connector selects both together; neither is selected automatically. Both Bahi
values must be populated. The first supported registration types are the exact
strings **Regular** and **Composition**. GSTIN must be a supported uppercase
15-character value; the connector does not translate or invent source values.
There is no GST portal validation or claim that format checks prove registration.

Enter the **GST registration effective date**, independently of any mailing date.
The date must be valid, nonfuture and later than every existing tax entry. Review
the exact pair, date and GST State, then confirm once with the operator and normal
party/no-competing-editor acknowledgement. Blank target differences still require
explicit filling acceptance. A currently matching GST companion may be included
without inventing a historical baseline; a divergent unavailable/conflicting
target cannot be dismissed.

This increment requires populated, matching Indian mailing State/Country on
source and destination. An existing nonempty tax State must also match the
approved State. Tax-State changes need separate review. Existing tax settings
(such as transporter and place-of-supply values) are copied into the new entry;
earlier entries are unchanged. A first entry supplies only the approved date,
GSTIN, registration type and State. Native empty optional slots and empty/No
logical padding are verified; no client business defaults are fabricated.

Historical replacement, same-date corrections, clears, Unregistered/UIN and other
registration types, future-dated history and unknown tax structures remain
blocked. A date change invalidates approval. As with other updates, approval is
valid for five minutes, no automatic resend occurs, and startup performs no write.

## Wire contract and preservation

The [official schema](https://help.tallysolutions.com/developer-reference/release-3-tdl-enhancements-tally-prime/what-are-the-changes-in-xml-tags/)
places registration date, type, State and GSTIN in Ledger/LedGSTRegDetails.
The [official API Explorer Alter guide](https://tallysolutions.com/tallyprime-api-explorer/pages/alter-ledger.html)
documents selecting an existing ledger and changing the supplied storages.
Neither page alone proves collection merge semantics on this installation.

Live 7.0 verification established that supplying only the new GST entry replaces
the old list. The connector therefore reconstructs the **complete approved tax
history plus the new dated entry** through the adapter's scalar allowlist. This
is a typed request; arbitrary native XML, balances, vouchers and unrelated fields
cannot be submitted. Every prior date/value/setting must survive exact read-back.
History order is compared by unique effective dates, never by guessing a row.

The [tax adapter](../../src/innoforia_tally_connector/integrations/tally/gst_updates.py)
owns supported storage shapes, dates and padding. The
[typed writer](../../src/innoforia_tally_connector/integrations/tally/party_update.py)
owns the import allowlist. Normal reads fetch the complete tax aggregate in the
existing bounded ledger query and expose the latest nonfuture entry. Missing,
duplicate, undated, future or unknown structures stay unavailable or blocked.
Root tax echoes alone do not establish success.

Approval binds the pair, GST date/State, all source/target/native snapshots,
policy and binding generation. Fresh checks run before the one durable attempt.
Exact field and full native-history verification precede atomic audit/baseline
completion. Only selected field acknowledgements advance. Original links and
legacy approval hashes remain unchanged; optional JSON metadata uses the existing
tables, with no new migration or queue.

## Executed evidence: 19 November 2026

The owner confirmed Apollo source 277's mailing operation
`479f956b-af96-4609-b4af-1f3519eb6c25` SUCCEEDED, with all comparisons true and
address, Kerala, India and PIN 683576 visible in Tally. This is mailing evidence,
not a live GST update of Apollo.

Authorized live GST contract checks used two retained synthetic ledgers, existing
GUIDs ending **0000016a** and **0000015f**, through one serialized background
gateway. Each transmission had a recorded intent, payload hash and native backup.

- On 0000016a, the first new-entry-only hypothesis replaced the original blank
  Regular row dated 20260401. Verification caught the loss and stopped further
  transmission. A distinct recorded repair restored that original row and retained
  the new Regular entry dated 20260402. The corrected full-history request then
  added Composition dated 20260501. Fresh reads verify all three dates and every
  original setting; the initial failed attempt remains retained.
- On 0000015f, the empty first-mailing test set Kerala/India dated 20260401. A
  separate first GST entry dated 20260402 saved Regular and the synthetic test
  GSTIN. Tally added empty optional tax slots; the narrowly corrected verifier
  passed by reads only, without resending that operation.

The synthetic GSTIN is 32AAACA1234A1ZT. Test values remain in the two test ledgers;
no cleanup deletion is included. No Bahi records, application mappings/journals or
invoice 69 were written by these contract probes. Raw local journals/native
backups stay outside Git; sanitized tests cover observed replacement, ordering,
padding and identity-token shapes. Offline workflow/Qt coverage exercises both
party types, paired selection/date approval, conflicts, expiry, cancellation,
repeated changes, timeouts, preservation failures and read-only restart recovery.
The complete offline suite passed **620 tests**, with one opt-in live test skipped.
Final journals and two fresh native checks are archived under the runtime
diagnostics directory `gst-contract-20261119-a531945d`; the initial single-entry
request was reconstructed and matched its recorded SHA-256. No probe is a
background retry task, and none runs automatically with the connector.
