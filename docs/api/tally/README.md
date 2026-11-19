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

The first repair used COUNTRYOFRESIDENCE and fetched CountryofResidence. The
fresh Airtel trial below establishes that this root-only write was insufficient.
Root-only legacy reads preserve missing/empty values and flag native/legacy
conflicts; dated mailing reads now take precedence. The
[synthetic fixture](../../../tests/fixtures/tally/party_country_7.xml) retains
observed tag shapes with synthetic ledger values; the owner export is not copied
into the repository. Offline checks do not certify live import acceptance.

The already-created ledger is not altered or recreated. If the owner corrects
its Country to the previously approved India in Tally, known-GUID read-only
reconciliation can verify all original fields and complete the local mapping.
A fully reconciled batch now reflects its child success; unsent cancelled rows
still require renewed review. No remote update method has been added.

### Dated mailing repair — 18 November 2026

Fresh source 281 / Airtel India created GUID
0b212ad8-3be5-45fe-8719-e1a70e240d4c-0000016b. The saved comparison evidence shows
address/state/PIN false and root country true. The owner's Tally screenshot shows
empty mailing address and Not Applicable State/Country. Therefore root country
alone cannot certify the saved mailing values. No repeat create or update ran.

Serialized export-only investigation used the existing gateway/private bounded
transport, adding Company FETCH BooksFrom/StartingFrom and Ledger FETCH
LedMailingDetails.*. The GUID-selected SIS Dummy company returned both dates as
20260401. Airtel returned an empty LEDMAILINGDETAILS.LIST despite root country
India. The earlier owner-corrected GUID ending 0000016a returned a mailing
aggregate with APPLICABLEFROM 20260401, PINCODE, MAILINGNAME, STATE and COUNTRY.
Only tag/date findings are retained; raw customer responses are not committed.
Before owner correction, an export-only scan using the updated query/reader
completed with 54 eligible parties and 12 classification exclusions. Airtel's
mailing fields then reported absent; one ambiguous mailing history was unavailable.
The supplied all-ledger export has 48 empty aggregates and one ledger with two
populated mailing records, so history must not be selected arbitrarily.

The [official aggregate schema](https://help.tallysolutions.com/developer-reference/release-3-tdl-enhancements-tally-prime/what-are-the-changes-in-xml-tags/)
defines Ledger/LedMailingDetails/ApplicableFrom, Address, State, Country and PINCode.
The [official Company method example](https://help.tallysolutions.com/user-defined-fields-validations-and-controls-in-tdl/)
uses BooksFrom. Production [queries](../../../src/innoforia_tally_connector/integrations/tally/queries.py)
now fetch BooksFrom and LedMailingDetails.*. The
[builder](../../../src/innoforia_tally_connector/integrations/tally/builders/parties.py)
places mailing fields inside one LEDMAILINGDETAILS.LIST, with ADDRESS.LIST and
APPLICABLEFROM/PINCODE/STATE/COUNTRY. Email/phone remain ledger scalars.

For **new ledgers only**, the chosen initial mailing effective date is the verified
destination Company.BooksFrom. This is not a historical mailing update policy.
No date is inferred from another party, the computer's date, or a fixture. The
gateway binds the date/source to the approved group context and rechecks it before
import; unavailable, invalid, future or changed dates block. Strict typed XML
validation rejects old root mailing payloads, multiple aggregates and other imports.
The effective date is visible in the exact preview's destination/group evidence.

Read-back prefers the dated mailing aggregate, even when empty, and new dated
creates require the same applicable date. Multiple populated aggregates,
unsupported structures, invalid dates and future records mark mailing fields
unavailable. A missing aggregate cannot pass a new create using root echoes.
Legacy saved previews remain readable/reconcilable against their original fields;
no approved payload or comparison is rewritten. Mismatches now name failed fields.

Offline: 125 focused tests and the complete suite (310 passed, one live skipped).
Tests use independent sanitized native export shapes, real HTTPX/gateway adapters,
temporary SQLite, both classifications, date invalidation and known-ID recovery.
No live import or remote alteration was performed. Dated create acceptance still
requires the owner's distinct-record test after resolving the existing mismatch;
the code change cannot repair the already-created Airtel ledger.

### Unicode HTTP repair — 18 November 2026

After the owner's manual correction, the saved journal reported only address
false; state, country, PIN and other approved comparisons were true. Both root
and dated address in the raw legacy HTTP export substituted U+003F question mark
for the approved U+2013 en dash. Explicit Content-Type UTF-8 also substituted it.
The same GUID exported with a UTF-16-encoded request and Content-Type UTF-16
returned an exact match. Therefore this remaining failure was a lossy export,
not evidence that the owner needed to edit the ledger again. No characters are
normalized or accepted as equivalent in the comparison.

[Tally's HTTP prerequisites](https://help.tallysolutions.com/pre-requisites-for-integrations/)
document UTF-16 content for special characters. The observed reply is UTF-16LE
without BOM or an XML declaration; generic byte parsing alone failed on it.
The [private transport](../../../src/innoforia_tally_connector/integrations/tally/_transport.py)
now sends guarded exports and already-validated typed imports as UTF-16 XML.
The [strict decoder](../../../src/innoforia_tally_connector/integrations/tally/xml_codec.py)
recognizes observed XML UTF-16 byte signatures/BOMs, decodes without replacement,
validates declarations and applies the same DTD/entity/control checks. Only the
previously verified Primary parent sentinel is normalized. No broad XML recovery,
business-value substitution, new import method or retry path was added.

An export-only check using the updated production gateway/reader/destination
adapter confirmed the existing Airtel GUID, classification/group and every
approved field. No local journal/link was committed by the diagnostic. The owner
subsequently confirms Airtel shows SUCCEEDED after the prescribed restart/read-only
reconciliation. The owner also confirms its saved link is visible and persists
after restart. Retain the existing ledger. Added GST values
visible in the owner's screenshot do not verify
or enable connector tax writes, which remain excluded.

Offline: **153 focused passed; 338 passed, one live skipped** in the full suite.
Coverage includes dash/accent/Indian-script/currency/non-BMP values, UTF-16 with
and without BOM, malformed encodings/declarations, XML attacks and controls,
typed create wire payloads/receipts, independent native read-back and SQLite
reconciliation/restart without duplicate creates. No assistant live import ran.

### Fresh supplier acceptance — Reliance Jio

The owner supplied a new successful Bahi-to-Tally trial for source 282, Reliance
Jio Infocomm Limited, batch 3dc1c9d0-a034-41e9-b018-ce0cb7339562. Screenshots show
SUCCEEDED, a saved identity link and populated address/country/PIN in SIS Dummy.
Read-only journal inspection confirms target GUID ending 0000016c and every
approved comparison true. Included fields were name, address, PIN, country and
supplier type; state/email/phone were null and omitted by saved policy, and tax
fields were disabled. The displayed Not Applicable state is consistent with that
manifest; this trial does not verify populated state or tax transfer. This is
fresh owner-run create/read-back evidence for the included mailing fields, beyond
the earlier manually corrected Airtel recovery. New-link restart persistence,
populated state/contact fields, customers and multi-party live cases remain pending.
No remote calls, runtime changes or repeated creations ran during this inspection.

### Controlled supplier State update implementation

Following the owner-verified difference screen, a
[separate controlled State experiment](../../master-sync/CONTROLLED_STATE_UPDATE.md)
now provides exact preview/approval and one shared-journal attempt. The official
sample's NAME selector is resolved/rechecked from saved GUID, not advertised as a
verified GUID-only Alter. Native snapshots guard version/context and compare all
unselected fields after transmission. Missing/ambiguous GUID/name or unsupported
mailing history prevents a write. No race-free/conditional-write claim is made.

Export-only preparation evidence on GUID ending 0000016c: full snapshot 15,393
UTF-8 evidence bytes; one dated mailing record at 20260401; typed payload 867 bytes,
containing GUID and the existing mailing entry with only State proposed as Delhi.
It was **not sent**. Full native exports put NAME in an attribute and use U+0004
references in nine tax/default scalar tags. The dedicated snapshot reader retains
these as opaque evidence tokens, never imports them or weakens the general parser.
Snapshot handling rejects unknown controls and unsupported mailing structures.

45 focused checks and full offline suite (404 passed, one skipped) pass, including
strict XML, actual typed transport/gateway with fake remotes, preserved failure
snapshots, one-attempt recovery, atomic audit and native UI/restart. Migration 6
adds appended verification/audit evidence, preserving original links. No live
update, runtime upgrade or journal edit ran by the assistant during implementation.

The owner subsequently approved and ran State trial
`bcc0b354-14ab-4f7b-a1c1-cfc5d277d778` on source 282. State read-back was Delhi;
the original preservation check blocked on added LEDSTATENAME (TYPE String) and
empty REMOTEALTGUID becoming the same ledger GUID. Retained before/after evidence
contains no other changes beyond ALTERID and the approved State. The repaired
comparison permits only those exact representations and retains the old approved
snapshot/hash. Wrong State, foreign import identity and all other native changes
still fail. The [official import-definition reference](https://help.tallysolutions.com/import-file-definition-attributes/)
uses RemoteAltGUID as import identity metadata; this trial's empty-to-self
transition remains an observation, not a general guarantee. The owner now supplied
a screenshot of this same record SUCCEEDED, with all seven comparisons true and
original link/audit preserved. Direct destination and post-success restart
acceptance were subsequently owner-confirmed with screenshots: Tally State Delhi,
unselected details preserved and SUCCEEDED after restart. The repaired slice passes 51 focused checks and the complete offline
suite (413 passed, one live skipped). No second import or runtime journal edit
ran during this repair.

The approved [repeatable supplier State feature](../../master-sync/SUPPLIER_STATE_UPDATES.md)
reuses this contract with fresh approval per change and a separate verified State
baseline. It adds no broader XML mutation support. On 19 November the owner supplied
the normal feature's second successful live result, record
`ec02114b-7aa7-46a5-bf70-b2fe4901ef81`: Delhi to Haryana on source 282 and the same
saved GUID, all seven comparisons true. The Tally screenshot shows Haryana and
unchanged visible address/country/PIN. Post-second-update restart persistence and
independent-edit conflict acceptance remain pending.

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
