# Bahi handbook refresh — 16 November 2026

The seven files supplied from `Downloads/bahi_API_docs` are reference contracts,
not instructions to deploy PHP, change scopes, migrate databases or execute their
write examples. Copies preserve supplied bytes; existing project filenames remain
stable so prior links and invoice evidence continue to resolve.

## Source comparison

| Supplied filename | Project copy under `handbooks/` | Change from previous copy |
| --- | --- | --- |
| `HANDBOOK-API-BIZ-SETUP-CHECK.md` | [Business setup](handbooks/API-BIZ-SETUP-CHECK-HANDBOOK.md) | Unchanged |
| `HANDBOOK-API-PARTY-DEVELOPER.md` | [Party](handbooks/API-PARTY-DEVELOPER-HANDBOOK.md) | Included Apache rewrite rules replace the earlier MultiViews/configuration guidance |
| `HANDBOOK-API-ITEM-GROUP-DEVELOPER.md` | [Item group](handbooks/API-ITEM-GROUP-DEVELOPER-HANDBOOK.md) | Unchanged |
| `HANDBOOK-API-ITEM-DEVELOPER.md` | [Item](handbooks/API-ITEM-DEVELOPER-HANDBOOK.md) | Controller allowlist clarified; obsolete `batch_info_available`, `expiry_required`, `item_tax` neither selected nor accepted |
| `HANDBOOK-API-INVOICE-DEVELOPER.md` | [Invoice](handbooks/API-INVOICE-DEVELOPER-HANDBOOK_v2.md) | Unchanged; retained historical project filename |
| `HANDBOOK-API-LEDGER-DEVELOPER.md` | [Ledger](handbooks/API-LEDGER-DEVELOPER-HANDBOOK.md) | Newly supplied |
| `HANDBOOK-API-UOM-DEVELOPER.md` | [UOM](handbooks/API-UOM-DEVELOPER-HANDBOOK.md) | Newly supplied |

## Integration consequences

Ledger and party APIs share account records and `account_id`. Ledger uses database
field names rather than party aliases and requires separate, broader `ledger:*`
permissions. Do not switch the existing party adapter to this endpoint or copy
ledger defaults into party payloads. Ledger reads document business/group and
system-flag evidence, but no connector reader or deployed permission is verified.
System records are readable, not writable. Group changes and reactivation are
unsupported. Deactivation does not check balances or outstanding transactions.
Account-group discovery and tax posting configuration still need explicit evidence;
ledger CRUD does not create journals or calculate balances.

UOM uses a business-scoped string code rather than a numeric ID. Prefer the
documented direct PHP query form with URL-encoded `uom_cd`. It uses existing item
scopes, has no DELETE and cannot rename codes. Descriptions/UQC are metadata, not
conversion factors. Database collation controls code equality; retain canonical
returned codes and confirmed mappings rather than inventing case normalization.
There is no update audit column or documented change feed.

The current party reader, validator and create payload builder were inspected.
Party fields, limits, response shapes and lifecycle rules did not change. Direct
PHP routing remains appropriate. No production item/ledger/UOM adapter currently
needs a code migration. No obsolete item fields were found in source, tests or
scripts. Existing fixtures and historical live evidence are retained unchanged.

## Follow-up gates

BAH-008 now tracks deployment validation and scoped ledger/UOM readers, rather
than requesting those missing handbooks. Prepare sanitized contract fixtures,
business isolation, pagination, code encoding/collation and permission checks
before enabling those resources. A future ledger-backed party protection check
must validate the same binding/account identity and handle unavailable scopes
explicitly; it must not silently remove the current review safeguard.

Receipt/Payment contracts, idempotent create/outcome lookup, conditional versions,
change capture and cross-PC ownership remain unresolved. This refresh enables no
new runtime feature and satisfies no live milestone gate. The current owner
party-workspace checklist remains the next operational task.

## Verification

All seven project copies were checked against supplied files using SHA-256.
Changed Markdown was checked for local links/anchors, balanced code fences and
diff whitespace. No runtime behavior changed; runtime tests, live API calls,
server commands, database migrations and builds were not run. The project Python
launcher was unavailable in the sandbox (base interpreter access denied), so
document comparison and validation used PowerShell/Git.
