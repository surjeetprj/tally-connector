# Master field mapping

Status: semantic implementation matrix. Bahi names below come from supplied
handbooks; **Tally columns describe meaning, not verified XML tags**. Each enabled
field needs adapter fixtures and live read-back evidence. Handbooks remain the
wire-schema authority; this table is not a complete payload schema.

## Customers and suppliers

Reference: [party handbook](../api/bahi/handbooks/API-PARTY-DEVELOPER-HANDBOOK.md).

| Bahi field | Tally meaning | Direction and rule |
| --- | --- | --- |
| `account_id` | Ledger GUID; MasterID when available | Identity mapping only; never send Bahi ID as Tally identity |
| `party_type` | Customer/supplier ledger classification | Confirm CUSTOMER/SUPPLIER mapping both ways; immutable through Bahi PATCH |
| `account_name` | Ledger name | Both ways after confirmed identity and collision checks; preserve original content |
| `display_name` | Display/alias concept | Optional; defer unless an exact supported representation is verified |
| `phone`, `email` | Contact fields | Both ways if representable; keep phone as string |
| `address` | Mailing address | Verify multiline flattening/length; block lossy writes rather than truncate |
| `state`, `country`, `pincode` | Mailing state/country/postal code | Confirm code/name translation; preserve PIN as string |
| `gstin`, `gst_reg_type` | GST registration details | Explicit validated representation; never infer registration from ledger name |
| Other optional fields | Field-specific counterpart | Deferred until individually allowlisted and verified |

Bahi create requires `party_type` and `account_name`; both configured party groups
must be valid even for reads. Omitted PATCH fields remain unchanged; null clears
only permitted nullable fields. Do not send activation flags, server audit fields
or group codes as party payload fields. Classification changes, inactive parties
and system parties must show precise blocking messages.

One ledger cannot silently become both CUSTOMER and SUPPLIER mappings. Dual-role
parties require an explicit business decision. Opening balances, running balances,
credit balances and general accounting groups are not party metadata to copy.

## Item groups

Reference: [group handbook](../api/bahi/handbooks/API-ITEM-GROUP-DEVELOPER-HANDBOOK.md).

| Bahi field | Tally meaning | Direction and rule |
| --- | --- | --- |
| `grp_id` | Stock-group GUID/verified identity | Persist scoped link; names are not unique in Bahi |
| `grp_name` | Stock-group name | Both ways with explicit collision handling |
| `parent_grp_id` | Parent stock group | Resolve mapped parent first; zero means Bahi root; map to verified Tally root semantics |
| `grp_desc` | Group description | Required on Bahi create; collect a deliberate value if unavailable, including an explicitly chosen permitted empty value |
| `hsn_code`, `gst` | Group tax source metadata | Required on Bahi create; no assumed Tally stock-group equivalent; user input or verified tax representation required |
| `taxability_type`, cess fields | Taxability/cess concepts | Defer until exact semantics and XML round-trip pass; never approximate |
| `disp_seq` | Display ordering | Bahi-local; exclude from cross-system business comparison |

Required Bahi create fields are `grp_name`, `grp_desc`, `hsn_code`, `gst`.
Preserve documented strings, permitted empties and decimal precision. Do not
create a Tally group named Primary. Reject hierarchy cycles and unmapped parents.
Do not propagate group tax changes as implicit item/tax rewrites without preview.

## Items and units

Reference: [item handbook](../api/bahi/handbooks/API-ITEM-DEVELOPER-HANDBOOK.md).

| Bahi field | Tally meaning | Direction and rule |
| --- | --- | --- |
| `item_id` | Stock-item GUID/verified identity | Scoped stable link |
| `item_name` | Stock-item name | Both ways for supported types; validate name collisions |
| `item_disp_name` | Alias/display name | Deferred until exact representation is verified |
| `item_desc` | Item description | Required on Bahi create; verify representation and length |
| `item_grp_id` | Parent stock group | Require confirmed group mapping; no implicit change on existing items |
| `item_uom` | Base unit | Existing confirmed Bahi code and Tally unit; no guessed aliases or unit creation |
| `manu_code` | Manufacturer identifier | Required on Bahi create; no assumed Tally equivalent; collect confirmed business value |
| `item_type` | Inventory/service classification | Initial creation slice: supported untracked GOODS; SERVICE/CHARGE blocked pending design/evidence |
| `item_sale_price` | Supported standard sale-price concept | Required on Bahi create; explicit Decimal business value, never infer from a purchase rate or last voucher |
| `tax_source` | Item-level versus group-derived tax policy | Resolve effective source explicitly; no blind copying of group defaults |
| `hsn_sac_code`, `gst_rate` | Item tax classification/rate | Enable only with validated tax representation and read-back |
| `avail_qty` | Stock balance | Never transfer through master sync |
| Tracking, image and other fields | Feature-specific data | Exclude unless separately approved and tested; unsupported tracking blocks creation |

The seven required Bahi item fields are the create prerequisites described in
the handbook; linking existing items does not require inventing new values.
Bahi units must already exist, with confirmed code spelling/case. Multiple or
compound units need a separate conversion contract. Sale-price schedules in
Tally may not equal a single Bahi price; block a nonrepresentable source.

## Comparison and update rules

- Compare only the confirmed supported field set. Exclude transport metadata,
  IDs, AlterID and audit timestamps from business-content hashes; keep them
  separately as observation/version data.
- Normalize decimals and equivalent typed representations deterministically.
  Preserve meaningful names, leading zeroes and missing/null distinctions.
  Candidate-search normalization must not rewrite persisted business content.
- Detect source edits and destination edits against the last acknowledged field
  baseline. Preview the exact PATCH/Alter fields; omission means preserve, not clear.
- A linked pair with initial differences needs an explicit accepted field
  baseline and owner policy. Linking does not claim that its contents match.
- Any changed destination field after preview invalidates dependent writes.
  Without atomic expected-version enforcement, disclose the concurrent-edit gap.
- Read-back verifies the destination's actual supported representation. Missing
  values, rounding or ignored fields are differences, not automatic success.

See [matching rules](MASTER_MATCHING_RULES.md) and
[validation cases](MASTER_SYNC_VALIDATION.md) for acceptance criteria.
