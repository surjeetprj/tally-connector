# Tally Phase 0 evidence

## Country write mismatch — 18 November 2026

Owner screenshot of SIS Dummy ledger MST004-SUP-20261102-7a5d3198 shows Country
Not Applicable after an approved country India create. Saved GUID read-back also
omits country; other approved comparisons matched. The existing root COUNTRYNAME
mapping follows the [generic sample](https://help.tallysolutions.com/sample-xml/),
but does not establish working country transfer on this release. The
[release-3 schema](https://help.tallysolutions.com/developer-reference/release-3-tdl-enhancements-tally-prime/what-are-the-changes-in-xml-tags/)
documents Ledger/LedMailingDetails with ApplicableFrom and Country, requiring
deployment-specific XML evidence before selecting its shape/date. Preserve the blocked
record and all comparisons; no repeat creation, country inference or remote
alteration is authorized by the screenshot. No live API calls were performed
during this investigation; official documentation was read on the web.

### Supplied TallyPrime 7.0 export

The owner reports the current installation is 7.0; prior 6.2 probes are historical.
The supplied UTF-16 Ledgers.xml contains 65 ledgers, 16 COUNTRYOFRESIDENCE elements
and zero COUNTRYNAME elements. India ledgers also show dated
LEDMAILINGDETAILS.LIST/COUNTRY with APPLICABLEFROM. The blocked test ledger has
neither country representation. Source SHA-256:
`881a653688ee189d6871962fd6991d422143d060a1438e3cc3b6fe57ddf67abd`.

The create builder now uses COUNTRYOFRESIDENCE, and the company-scoped collection
query fetches CountryofResidence. Reads preserve missing/empty values and mark
conflicting native/legacy country fields unavailable. No applicable date is
invented and no dated mailing aggregate is sent by this change. The
[synthetic fixture](../../../tests/fixtures/tally/party_country_7.xml) retains
observed tag shapes with synthetic ledger values; the owner export is not copied
into the repository. Offline checks do not certify live import acceptance:
the corrected create mapping still needs an owner-approved future live trial.

The already-created ledger is not altered or recreated. If the owner corrects
its Country to the previously approved India in Tally, known-GUID read-only
reconciliation can verify all original fields and complete the local mapping.
A fully reconciled batch now reflects its child success; unsent cancelled rows
still require renewed review. No remote update method has been added.

Observed 29 October 2026, approximately 19:47 IST. CON-002 is partially validated;
the observations below do not establish import, idempotency or crash recovery.

## Party read-back update — 2 November 2026

Subsequent update (3 November): [actual-party transfers](../../master-sync/PARTY_TRANSFER.md)
add documented structured mailing XML and typed customer/supplier creates with
mocked transport and read-back tests. No live export/import ran for that update.
The [official mailing example](https://help.tallysolutions.com/sample-xml/) and
[dated GST schema changes](https://help.tallysolutions.com/developer-reference/release-3-tdl-enhancements-tally-prime/what-are-the-changes-in-xml-tags/)
do not establish exact PAN/GST create or applicable-date behavior on this 6.2
deployment. Tally tax writes and PAN/registration reads remain unavailable;
explicit exclusions are required. Owner screenshots/read-back and exported XML
can supply the next evidence without guessing tags or defaults. The command
scripts/master_sync/party_field_evidence.py supports owner-invoked read-only field
availability and offline XML-shape inspection; it was not run against live systems.

The export-only [party experiment](../../../scripts/phase0/probe_party_reads.py)
verified all 60 ledger GUID lookups against their collection observations,
including GUID/MasterID/AlterID/name/parent and observed optional scalar fields.
All 28 group parents resolved. A missing GUID returned no records; a nonexistent
company name returned no records. See [sanitized evidence](evidence/party-read-probes.json).

Ledger GUIDs use a UUID plus an eight-hex suffix in this release. Root-group
PARENT values use `&#4; Primary`; the runtime normalizes only this verified root
sentinel and rejects other invalid controls or XML declarations. The application
resolves company names from the verified GUID and serializes every request through
its injected gateway. This does not establish an atomic snapshot or cross-PC lease.

The user subsequently confirmed Sundry Debtors/Customer and Sundry
Creditors/Supplier roots, including descendants, for read/link classification.
The runtime reader observed 48 parties, excluded 12 other ledgers and matched all
48 selected details. Actual native-screen loading passed. No Tally imports or
live rename tests were performed. Address flattening, changes/deletions/restores
and automatic mutation guarantees remain unverified. See
[the desktop milestone](../../master-sync/READ_ONLY_DISCOVERY.md).

The remaining sections retain the original 29 October baseline and its then-open
read-back questions; this update supersedes those questions only for the executed
party read scope.

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

The MST-004 supplier experiment now includes a strict single-ledger create adapter
with offline XML/receipt tests, based on the official master example. It has not
sent a live Tally import. The selected live trial created only in Bahi; Tally
email acceptance, import receipt shapes and identity resolution remain live gates.
See [controlled supplier experiment](../../master-sync/CONTROLLED_SUPPLIER_EXPERIMENT.md).

See the [purchase capability checklist](../../phase0/CONTRACT_VALIDATION.md)
and [current state](../../STATE_AND_PROGRESS.md).
