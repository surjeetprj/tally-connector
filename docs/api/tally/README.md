# Tally Phase 0 evidence

Observed 29 October 2026, approximately 19:47 IST. CON-002 is partially validated;
the observations below do not establish import, idempotency or crash recovery.

## Reproducible experiment

[Probe script](../../../scripts/phase0/probe_tally.py) uses Python standard-library
HTTP/XML support. All requests are sequential POSTs containing TALLYREQUEST=Export
to `http://localhost:9000`. No import/create/alter/delete requests are constructed.
This isolated Phase 0 experiment is not the future application transport/gateway.

```powershell
python scripts/phase0/probe_tally.py --company 'SIS Dummy'
python -m unittest discover -s tests/phase0 -v
```

The run used Python 3.12.8's local installation path specified in the progress
record, without installing project dependencies. Network sandbox execution could
not reach loopback; the approved run outside that sandbox succeeded. No firewall
or Tally configuration was changed. A future rerun may produce different counts.

## Observed results

- All ten final export requests returned HTTP 200 and strictly parsed XML with
  no nonempty detected Tally error tags.
- Company collection contained one loaded company, matching `SIS Dummy` exactly.
  It returned GUID `0b212ad8-3be5-45fe-8719-e1a70e240d4c` and company number
  `100006`. This proves these identity fields can be read in this instance;
  stability across restores/rewrites and active-selection enforcement are untested.
- Product AboutPage returned Release `6.2 (Upgrade Available)` and Edition
  `Gold (Multi User) Rental`. Educational mode is user-reported; these fields
  alone do not establish current license mode or permitted transaction dates.

| Company-scoped collection | Records | With GUID and numeric AlterID | Observed AlterID range | Records above observed maximum |
| --- | ---: | ---: | --- | ---: |
| Unit | 7 | 7 | 212–306 | 0 |
| Ledger | 60 | 60 | 31–423 | 0 |
| StockItem | 21 | 21 | 235–424 | 0 |
| Voucher | 58 | 58 | 178–697 | 0 |

Each request sets SVCURRENTCOMPANY to SIS Dummy. No company mutation was used to
test how Tally handles invalid or changing context. Counts describe returned
collections, not a proven all-period snapshot: voucher date-range defaults and
other export scope must be established before production cursor design.

Initial parsing counted similarly named CMPINFO header counters as records.
The parser was corrected to count direct records inside COLLECTION only; offline
regressions cover header counters, empty collections, selected-company projection,
export-only requests/company escaping, and AboutPage redaction. All five passed.
The final rerun and table use the corrected parser.

## Retained evidence and limits

A subsequent [selective-filter experiment](../../../scripts/phase0/probe_tally_selective.py)
ran on 29 October around 20:19 IST after rechecking the company GUID. Unit >305,
Ledger >422, StockItem >423 and Voucher >696 each returned exactly one record,
whose AlterID was respectively 306, 423, 424 and 697. All four predicates passed;
see [sanitized selective evidence](evidence/selective-probes.json). This checks
populated filters on existing data, not new/edit event capture or pagination.

- [Sanitized final observations](evidence/read-only-probes.json): timestamps,
  HTTP results, raw-response hashes/sizes and allowlisted projections/aggregates.
- Request XML files in `evidence/` reproduce company discovery, Product AboutPage,
  four scoped baseline collections and their corresponding AlterID filters.
  Each is referenced by filename in the JSON observations.
- Raw responses are not saved. Names/addresses, voucher references/amounts,
  individual record identities, other-company details, serial/license values and
  local paths are excluded from retained business-record evidence. The selected
  dummy-company identity and product edition/release are deliberately retained.
- Hashes establish which response was summarized; they do not permit replaying
  the original response or independently auditing omitted fields. Offline tests
  use synthetic XML and do not substitute for further live experiments.

Pending: source-identity/REMOTEID semantics; per-record lookup and canonical
read-back; date-range scope and pagination; edits,
deletions and restore behavior; company mismatch guard; educational-mode date
limits; controlled imports; timeout/crash recovery; cross-PC writer ownership.
No balance, stock or voucher was changed by these probes.

See the [purchase capability checklist](../../phase0/CONTRACT_VALIDATION.md)
and [current state](../../STATE_AND_PROGRESS.md).
