# Linked-party field updates: Bahi to Tally

The linked review supports exact selected updates of email, phone, address, State,
country, PIN and PAN for customers and suppliers under the confirmed direct Sundry
Debtors/Creditors roots. Paired GSTIN/registration-type updates are covered by the
[dated GST extension](GST_PARTY_UPDATES.md). The [allowlist](../../src/innoforia_tally_connector/domain/party_changes.py)
and [typed XML adapter](../../src/innoforia_tally_connector/integrations/tally/party_update.py)
own the implemented fields and wire rules. The original
[State/first-mailing workflow](SUPPLIER_STATE_UPDATES.md) remains a compatible subset.

## Normal workflow

The default desktop workflow now automatically includes all supported eligible
Bahi changes, including PAN, blank fills and eligible paired GST fields. The
table has no selection checkboxes. **Review all eligible changes** prepares the
complete set and **Confirm update** approves its exact values, dates and displayed
blank fills once. Conflicting/unsupported changes remain visible and excluded;
effective dates are still required where history needs an explicit date. The
field-selection controls described below document the earlier workflow, retained
for compatibility tests; they are not required in normal use. This change does
not enable unattended writes. [Reverse linked review](TALLY_TO_BAHI_UPDATES.md) is now available as a separate destination adapter through the same lifecycle.

Select a linked Bahi party and **Review linked changes**. Eligible contact/mailing
changes are checked initially. PAN always requires explicit selection. Use the
field checkboxes, **Review selected changes**, then inspect exact old/new values
and confirm once with the saved operator and normal-party/no-competing-editor
acknowledgement. Field/date changes disable the prior approval. No write occurs
on selection, preparation, refresh or startup.

An unchanged source value with a known blank destination can appear as **Fill
missing destination**. It starts unchecked. Select it and explicitly approve
filling blank fields before preparing. This also covers unavailable historical
observations only when the current destination is known to be blank. Original
link evidence is not rewritten. A known blank destination that changes between
absent, null and empty also requires explicit filling approval, even when Bahi's
value changed. These representations remain distinct in the evidence; the change
alone does not establish an entered Tally value. A formerly populated destination
that was cleared remains protected. A nonempty pre-existing difference, destination
edit, divergent conflict, currently unavailable representation, invalid value,
rename/classification change or clearing request cannot be dismissed to write.

Mailing edits copy the one existing supported record, preserving its effective
date and unselected content. A first entry in an empty aggregate requires the
user-entered date, as described in the State workflow. Contact-only/PAN updates
do not rewrite mailing data. Address line breaks, whitespace, Unicode and leading
zeroes are retained exactly; values are not truncated or translated.

TallyPrime 7.0 exports selected mailing address/PIN values again at the ledger
root, with `TYPE="String"` on address lines. Verification checks their exact
values and permits only that known type annotation. Mailing Country is stored
in the documented mailing aggregate; `CountryOfResidence` need not mirror it.
Its root value may remain exactly as observed before the update or match the
approved country. Other values, duplicate nodes, unknown attributes, changed
mailing dates and unselected content still fail preservation checks. Retained
pre-repair approvals use their original before evidence for this comparison;
their stored expected snapshot and approval hash are not rewritten.

## Baselines, execution and recovery

Each completed operation acknowledges only its selected fields. The separate
per-field history uses each field's last verified source/destination observation;
it never blesses incidental changes to unselected fields. Fields without an
acknowledgement retain original linking observations. The latest audit ID guards
competing previews transactionally across all fields. Legacy State audit entries
are interpreted as acknowledging State only.

The existing UPDATE commands, shared attempt/outbox engine, binding reservation
and serialized gateway are reused. The legacy State module/method names remain
internal compatibility details, not another queue. Five-minute approval binds
selected values, initial-fill choices, policy version, source/target/native
snapshots and binding/generation. Fresh reads precede the one recorded attempt.
Known-ID read-back verifies every selected field and unselected native content.
Ignored/uncertain results do not advance baselines or issue a second import.
Original links/audits remain immutable; field acknowledgements and local success
commit atomically. Restart performs no automatic write. The narrow unchanged
empty-mailing closure action remains limited to the old State-only rejection.

No database migration is required for this extension: additional intent metadata
is stored in existing JSON evidence. Default legacy fields are excluded from old
approval hashes. Migration, restart and old-record regressions remain required.

## Contract evidence and limits

[Official ledger examples](https://help.tallysolutions.com/sample-xml/) document
name/group, contact fields and name-targeted Alter. Current name is resolved and
rechecked from the saved GUID; no GUID-only or remote compare-and-swap claim is
made. [Official dated schema](https://help.tallysolutions.com/developer-reference/release-3-tdl-enhancements-tally-prime/what-are-the-changes-in-xml-tags/)
documents mailing aggregates. The existing date/preservation controls remain.
[Official ledger methods](https://help.tallysolutions.com/article/Tally.ERP9/Data_Management/list_of_odbc_fields_of_a_ledger.htm)
identify IncomeTaxNumber as PAN; read-only inspection confirmed the scalar in the
current test ledger export. PAN is read only when the requested scalar is present;
unknown representation never becomes a guessed blank value.

GSTIN and registration type use the separate dated extension after verified
import/read-back/history behavior; no root-tax write fallback is enabled. PAN and
GST updates require explicit field selection and do not enable tax fields in
creation policies.
Batches of updates, clears, multiple mailing histories, bank/bill
settings, balances, customer/supplier reclassification and unattended writes remain
outside this increment. The later reverse increment adds the bounded Bahi PATCH adapter; no BahiAI dependency was introduced.

## Verification

Automated checks use temporary SQLite, fake HTTPX through the production typed
gateway, and offscreen Qt. They cover individual and combined fields, both party
types, exact values, per-field baselines, explicit fills, conflict blocking, stale
approval, ignored replies, timeout/read-only recovery, no repeated import, old
hashes, migrations and restart. No additional owner manual-test gate is required.
The PIN regression covers blank export padding after a State update, explicit
fill selection/acceptance in Qt, exact read-back and no repeated import; edited or
cleared nonempty target values remain blocked.
Owner operation `479f956b-af96-4609-b4af-1f3519eb6c25` filled Apollo's mailing
address, PIN and Country, but was blocked by those export differences. Its saved
post-write evidence and a fresh serialized, company/GUID-scoped live export both
pass the repaired native verifier. The diagnostic made no imports or runtime
database writes. The owner subsequently supplied SUCCEEDED/all-true application
evidence and inspected the address, State, Country and PIN in Tally. Contact,
PAN and other live cases are not established by this mailing result.
