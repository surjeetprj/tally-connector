# Account Ledger API

## Purpose and naming

`api-ledger` manages account master records in the existing `account_ledger` table. It includes customers, suppliers, expense, income, bank, and other ledgers when their account group exists and is active for the authenticated business. It does not create journal transactions or calculate balances. `api-account-ledger` is a more explicit alternative name; this implementation uses the shorter `api-ledger`, consistent with `api-party` and `api-item`.

`api-party.php` and `PartyController.php` are unchanged. They continue to expose only configured customer/supplier groups using party field aliases. Both APIs share the underlying records: ledger edits to customer/supplier accounts are visible through the party API and vice versa.

## Routes and authentication

Send `Authorization: Bearer <API_KEY>` on every request and `Content-Type: application/json` on POST/PATCH.

| Method | Route | Required scope | Result |
| --- | --- | --- | --- |
| GET | `/web-api/api-ledger` | `ledger:read` | Paginated list |
| GET | `/web-api/api-ledger/123` | `ledger:read` | Single ledger |
| POST | `/web-api/api-ledger` | `ledger:create` | Create, HTTP 201 |
| PATCH | `/web-api/api-ledger/123` | `ledger:update` | Partial update, HTTP 200 |
| DELETE | `/web-api/api-ledger/123` | `ledger:delete` | Soft deactivate, HTTP 200 |

`.php` routes also work, including `/web-api/api-ledger.php?id=123`. A path ID takes precedence over a query ID. IDs must be positive signed 32-bit integers. PUT, OPTIONS, POST with an ID, and PATCH/DELETE without an ID are unsupported. Authenticated unsupported requests return 405.

Assign the new `ledger:*` scopes explicitly in the integration's existing scopes list. Party permissions do not grant ledger access; ledger access is broader. No integration permissions are changed automatically.

## Input fields

This API uses database column names, not the party API aliases. For example, use `ac_disp_name`, `phone_num`, and `contact_person_name` rather than `display_name`, `phone`, and `contact_person`.

| Field | Maximum characters | Rules |
| --- | --- | --- |
| ac_group_code | 32 | Required on create; active account group in this business; immutable on PATCH |
| account_name | 128 | Required on create; nonblank; unique within business |
| ac_disp_name | 128 | Nullable |
| phone_num | 16 | Nullable text |
| address | 255 | Nullable |
| state | 64 | Nullable |
| pincode | 6 | Nullable; empty or six digits |
| email | 255 | Nullable; empty or valid email format |
| gstin | 16 | Nullable; empty or 15-character GSTIN format |
| pan | 10 | Nullable; empty or PAN format |
| contact_person_name | 64 | Nullable |
| relation_mgr | 64 | Nullable |
| profile_tag | 256 | Nullable |
| gst_reg_type | 32 | Nonblank when supplied; default `Regular` |
| note | 256 | Nullable |
| indus_seg | 64 | Nullable |
| indus_subseg | 64 | Nullable |
| country | 64 | Nonblank when supplied; default `India` |
| custom_fld1 | 64 | Nullable |

All supplied non-null values must be strings. Empty strings are accepted for optional fields. PAN/GSTIN checks validate format only. Pincode validation follows the party API's Indian six-digit convention even when another country is supplied. No GST registration type enum is invented; the schema stores free text.

Server-owned fields are `biz_id`, `account_id`, `created_by`, `created_dtm`, `updated_by`, `updated_dtm`, `is_system`, `is_active`, and `deactivated_dtm`. Submitting them or any unknown field returns 422. Group changes are deliberately disallowed to avoid silently reclassifying an existing account.

## Create and update examples

```http
POST /web-api/api-ledger
```

```json
{
  "ac_group_code": "EXPENSE",
  "account_name": "Office Rent",
  "ac_disp_name": "Rent",
  "note": "Monthly office rent",
  "custom_fld1": "RENT-01"
}
```

`EXPENSE` is illustrative; supply an actual active `account_group.group_code`. The group is checked using business ID and stored using its canonical database spelling. The controller does not require customer/supplier mappings. New ledgers are active, non-system records. Creation audit uses UTC time and `api:<integration_id>`.

```http
PATCH /web-api/api-ledger/123
```

```json
{"account_name":"Office Rent - Main Branch","relation_mgr":"Accounts Team","email":null}
```

PATCH updates only supplied fields and records the update actor/time. Nullable fields can be cleared with null. Empty requests are rejected. Inactive ledgers cannot be updated. System ledgers can be read/listed but cannot be changed or deactivated. Reactivation is not implemented.

## Responses and listing

Create/get/update/deactivate return `{"success":true,"data":{...}}`. Data contains all 28 supplied table columns. `account_id` and `biz_id` are integers; `is_active` and `is_system` are booleans. Other fields retain their database values, including nulls. Repeated DELETE returns the already inactive record without changing its deactivation timestamp. Records and historical journal entries are not physically deleted.

List supports:

- `page`: 1–100000, default 1.
- `limit`: 1–200, default 50.
- `ac_group_code`: exact group filter under the database collation.
- `status`: `ACTIVE` or `INACTIVE` (case-insensitive input).
- `is_system`: `0` or `1`.
- `search`: up to 100 characters; literal substring of account name, display name, phone, or GSTIN. SQL wildcard characters are escaped.

All filters combine with AND. Default listing includes active/inactive and system/non-system ledgers. Rows sort by descending account ID. Pagination returns `page`, `limit`, `total`, and `total_pages` alongside the `data` array. All lookups/writes/listings use the authenticated business ID, including system records.

## Errors

| HTTP | Code | Meaning |
| --- | --- | --- |
| 400 | INVALID_ID | Invalid query/path ID value |
| 404 | ROUTE_NOT_FOUND | Unknown route |
| 404 | RESOURCE_NOT_FOUND | Ledger not found in this business |
| 403 | PROTECTED_ACCOUNT | Attempt to change/deactivate system ledger |
| 409 | INACTIVE_ACCOUNT | Attempt to update inactive ledger |
| 409 | DUPLICATE_ACCOUNT_NAME | Business already has this account name, including inactive/system accounts |
| 422 | INVALID_ACCOUNT_GROUP | Group missing, inactive, or owned by another business |
| 422 | IMMUTABLE_LEDGER_GROUP | PATCH includes ac_group_code |
| 422 | UNKNOWN_FIELD | Unsupported or server-owned field |
| 422 | VALIDATION_ERROR | Invalid field, empty body, or invalid query filter |
| 405 | METHOD_NOT_ALLOWED | Unsupported method/resource combination |

Shared authentication/body errors come from `bootstrap.php`; unexpected failures return 500 `INTERNAL_ERROR`. Errors use `{"success":false,"error":{"code":"...","message":"..."}}`.

## Schema review and deployment

The supplied schema supports this API without changes. `account_id` is globally unique, while the API additionally scopes access by `biz_id`. The unique `(biz_id,account_name)` index applies across account groups and inactive/system records. MySQL's `utf8mb4_unicode_ci` controls name equality, so case variants can conflict.

MyISAM provides neither transactional rollback nor foreign key enforcement. This API performs single-statement mutations, but the separate group check/read/write steps are not atomic; concurrent administrative group/account changes need coordination. System/active predicates are included in mutation SQL to prevent writes to records whose protection/status changed after the initial read. Deactivation does not check balances or outstanding transactions and is a master-status change only. A future migration to InnoDB and business-aware foreign keys should be reviewed separately with the related schema; no engine or schema migration is performed here.

Deploy `LedgerController.php`, `api-ledger.php`, and updated `.htaccess`. Required existing tables are `account_ledger`, `account_group` (including `biz_id`, `group_code`, `is_active`), `api_integrations`, and `biz_establishment`. Existing bootstrap requires PDO and mbstring. Enable the intended ledger scopes on authorized integrations.

Run `php tests/ledger-api-test.php`. Tests use isolated SQLite data for business isolation, account groups, fields, duplicate names, protection rules, audit, soft deactivation, and pagination. They do not verify live authentication, Apache rewrites, MySQL Unicode collation, or MyISAM concurrency.
