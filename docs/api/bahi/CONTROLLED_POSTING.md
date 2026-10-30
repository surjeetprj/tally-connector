# Authorized purchase posting and recovery test

29 October 2026. The user explicitly authorized posting in business 52 and asked
to fix the remaining Phase 0 issues. One controlled purchase was created; it is
retained ACTIVE for audit. No original business invoice or master was edited.

## Test record and observed effect

| Field | Value |
| --- | --- |
| Business | 52 |
| Invoice ID / internal number | 69 / P0CT-261029-01 |
| Supplier reference / date | P0CT-261029-01 / 2026-10-29 |
| Existing supplier / item | 274 / 84 |
| Actual item type / unit | SERVICE / pcs |
| Quantity / test price | 1.000 / 1.00 |
| Taxable / GST / net | INR 1.00 / 0.18 / 1.18 |
| Final status | ACTIVE |
| Item quantity before / after / repeat | 0 / 0 / 0 |

The initial preflight expected GOODS and stopped before any write. A read then
confirmed SERVICE, untracked, group-sourced GST. The test was adapted to preserve
that master and validate accounting-only behavior, not change its type or unit.
It therefore does not validate inventory-purchase stock increases.

## Executed workflow

1. Authenticated business identity was rechecked, along with existing supplier,
   item and tax-group data. A full current PURCHASE duplicate scan found no test
   reference. The request used only supported create fields and explicit test values.
2. Durable local TEST_PREPARED/WRITE_INTENT records were flushed/fsynced before
   creation. POST returned invoice 69; the ID was persisted before continuing.
3. Detail read-back confirmed DRAFT, identities, references, quantity, price, GST
   and totals. A note-only PATCH was accepted; another detail read confirmed unchanged
   canonical invoice values.
4. Separate bodyless POST to `api-invoice.php/69/post` succeeded. Its response body
   was not used as completion authority; GET confirmed the matching ACTIVE invoice.
5. Repeating the known-ID post returned the same ACTIVE invoice; stock stayed zero.
   Final detail values still matched. No cancellation, reversal or deletion ran.

See [posting evidence](evidence/controlled-post.json) and the
[test implementation](../../../scripts/phase0/test_bahi_posting.py). The durable
local journal remains under ignored `.phase0-runtime/bahi-write/attempts.jsonl`.
It records test payload/identity and response hashes, never authentication headers.
The script refuses an uncertain prior create without a known ID and rejects
conflicting journal identities. Do not delete that journal to force another create.

## Separate-process known-ID recovery

[test_bahi_recovery.py](../../../scripts/phase0/test_bahi_recovery.py) persisted an
APPLYING intent for an idempotent repeat post on the existing test invoice. After
receiving the server response, the process deliberately called os._exit(23)
before recording local completion. That exit code was observed.

A new process found the unresolved intent, verified business/record identity and
read ACTIVE status using GET only. Recovery performed **zero creates and zero
posts**; stock remained zero. See [recovery evidence](evidence/controlled-recovery.json).

This demonstrates one client acknowledgment-loss window on an already posted,
known-ID action. It does not simulate server/database crashes, unknown-ID create
recovery, a genuinely dropped network response or prove journal crash atomicity.
ACTIVE is the API's confirmation; an independent ledger-journal audit is not
available through the supplied contracts.

## Further work

Preserve invoice 69 as a clearly marked test entry unless cleanup is explicitly
requested. Do not automatically reverse it. Confirm real business mappings before
production transfers; this test used selected Bahi masters without asserting a
mapping to different Tally data. GOODS stock movement, Tally imports and broader
fault cases remain untested. See the
[sync-extension proposal](SYNC_EXTENSION_CONTRACT.md) for backend guarantees still
needed before automatic bidirectional mode.
