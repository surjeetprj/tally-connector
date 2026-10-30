# Bahi Party API — Developer Handbook

Updated: 23 October 2026. Based on the root `api-party.php`, `PartyController.php` and `bootstrap.php`. Examples describe code behavior; database-backed requests have not been verified end to end.

## 1. Connection and deployment

Preferred local endpoint:

```text
https://www.innoforia.com/201/h-bahi/bahi/web-api/api-party
```

Direct PHP endpoint:

```text
https://www.innoforia.com/201/h-bahi/bahi/web-api/api-party.php
```

No `.htaccess` is required by the PHP code. However, the extensionless endpoint requires Apache configuration that resolves `api-party` to `api-party.php`, such as an applicable MultiViews configuration. If it returns an Apache 404, test the direct `.php` endpoint and ask the server administrator to configure extensionless resolution. PHP route matching occurs only after Apache invokes the script. Use HTTPS for remote deployments.

Intended layout:

```text
bahi/
├── include/
│   └── dbo.php
└── web-api/
    ├── api-party.php
    ├── bootstrap.php
    └── PartyController.php
```

`api-party.php` loads the root bootstrap and controller. The old nested package is not the source of routing for this endpoint. `/api/v1/parties` is not supported by this root entry point.

### Bootstrap setup

Root `bootstrap.php` defines API settings in its `$config` array and includes `__DIR__ . '/../include/dbo.php'`. Its shared `db()` function lazily creates and reuses a `new dbo()` instance per request. The controller delegates its connection to that same function. Database connection settings are managed by `../include/dbo.php`.

Runtime requirements: PHP 8.3+, PDO MySQL, mbstring, and the Bahi tables `api_integrations`, `biz_establishment`, `account_group` and `account_ledger` with the columns used by the API.

Party group codes are set directly in root `bootstrap.php`: `CUSTOMER` is `'customer'` and `SUPPLIER` is `'supplier'`. Server environment variables `BAHI_CUSTOMER_GROUP_CODE` and `BAHI_SUPPLIER_GROUP_CODE` are not used. Both codes must refer to active `account_group` records for the authenticated business. One configured pair currently applies across businesses. All party operations, including reads, validate both mappings.

The configured request body limit is 65,536 bytes (64 KiB). API responses set `Content-Type: application/json; charset=utf-8` and `Cache-Control: no-store` when the API response helper runs. Apache errors and failures during bootstrap loading can produce a different response format.

## 2. Authentication and business isolation

Send this header on every request:

```http
Authorization: Bearer YOUR_API_KEY
```

Issued keys use `eb_live_` followed by 64 hexadecimal characters. Send the issued key exactly as provided. The API hashes it using SHA-256 and matches `api_integrations.key_hash`. There is no key-issuance endpoint here: obtain a provisioned key from the integration administrator.

The integration must have status `ACTIVE`, be unexpired, and belong to a business with `biz_establishment.disp_status = 'Y'`. Scopes are stored as a JSON array, for example:

```json
["party:create", "party:read", "party:update", "party:delete"]
```

Business identity comes from the integration record. Do not submit `biz_id`. Reads and writes are restricted to that business and its configured customer/supplier groups. An ID outside that boundary returns 404.

Use keys from a confidential backend. The API has no CORS support, rejects OPTIONS, and is not configured for direct browser application integration. Keep keys out of source control, URLs and logs.

## 3. Endpoint reference

In this handbook, `BASE_URL` means the full URL ending in `/api-party` or `/api-party.php`.

| Method | URL | Required scope | Successful result |
| --- | --- | --- | --- |
| GET | `BASE_URL` | `party:read` | 200, paginated parties |
| GET | `BASE_URL?id=123` | `party:read` | 200, one party |
| POST | `BASE_URL` | `party:create` | 201, created party |
| PATCH | `BASE_URL?id=123` | `party:update` | 200, updated party |
| DELETE | `BASE_URL?id=123` | `party:delete` | 200, deactivation result |

POST and PATCH bodies must be JSON objects. Send `Content-Type: application/json`. GET and DELETE do not require a body. PUT, HEAD and OPTIONS are unsupported. PATCH and DELETE require an ID; POST must not include an ID. GET without an ID lists parties; it is not a separate authentication diagnostic.

IDs must be positive decimal integers within the PHP integer range, without leading zeros. The router also recognizes `/api-party/123` and `/api-party.php/123` if Apache forwards these paths, but query-string IDs avoid that additional server dependency. If both are present, the path ID takes precedence.

## 4. Create and update fields

All supplied values below must be strings or permitted nulls. Keep phone numbers and pincodes as strings. Limits are checked with `mb_strlen`.

| Field | Maximum characters | Rules |
| --- | ---: | --- |
| `party_type` | — | Required on create: exactly `CUSTOMER` or `SUPPLIER`. Cannot be patched. |
| `account_name` | 128 | Required on create; nonblank; cannot be null. |
| `display_name` | 128 | Optional; nullable. |
| `phone` | 16 | Optional; nullable; no additional format validation. |
| `email` | 255 | Optional; nullable; nonempty values must pass email validation. |
| `address` | 255 | Optional; nullable. |
| `state` | 64 | Optional; nullable. |
| `pincode` | 6 | Optional; nullable; nonempty values must contain exactly six digits. |
| `country` | 64 | Optional; cannot be null when supplied. |
| `gstin` | 16 | Optional; nullable; nonempty values must match the implemented 15-character GSTIN pattern. |
| `pan` | 10 | Optional; nullable; nonempty values must match five letters, four digits, one letter. |
| `gst_reg_type` | 32 | Optional; cannot be null when supplied; no enum validation. |
| `contact_person` | 64 | Optional; nullable. |
| `note` | 256 | Optional; nullable. |

Empty strings are accepted except for `account_name`. PAN and GSTIN patterns are case-insensitive; values are not automatically converted to uppercase. Validation checks format only. Account names are checked for blankness but are not trimmed before storage.

Unknown body fields return 422. Do not send `account_id`, `biz_id`, `ac_group_code`, `is_active`, `is_system`, timestamps or audit fields. API names such as `display_name` and `phone` differ from their database column names; always use the API names above.

On create, omitted optional columns are left to the database defaults and constraints. On PATCH, omitted fields remain unchanged; use JSON null to clear nullable fields. Supply at least one supported field. Currently an empty object `{}` is rejected by the body parser with `INVALID_BODY`.

## 5. Calling examples

These PowerShell examples use `Invoke-RestMethod`. Replace the placeholder key, and use an actual party ID returned by creation. Examples that create, update or delete records modify the selected business.

```powershell
$baseUrl = 'https://www.innoforia.com/201/h-bahi/bahi/web-api/api-party'
$apiKey = 'REPLACE_WITH_ISSUED_API_KEY'
$headers = @{ Authorization = "Bearer $apiKey" }
```

### Create a customer

```powershell
$body = @{
    party_type = 'CUSTOMER'
    account_name = 'Demo Customer'
    display_name = 'Demo Customer'
    phone = '9876543210'
    email = 'accounts@example.com'
    address = '10 Example Road'
    state = 'Delhi'
    pincode = '110001'
    country = 'India'
    contact_person = 'Accounts Team'
    note = 'Created through Bahi API'
} | ConvertTo-Json

$created = Invoke-RestMethod -Method Post -Uri $baseUrl `
    -Headers $headers -ContentType 'application/json' -Body $body
$partyId = $created.data.account_id
```

For a supplier, use `"party_type": "SUPPLIER"`. The minimum body is:

```json
{"party_type":"CUSTOMER","account_name":"Demo Customer"}
```

### Read one party

```powershell
Invoke-RestMethod -Method Get -Uri "${baseUrl}?id=$partyId" -Headers $headers
```

### List and search

```powershell
Invoke-RestMethod -Method Get `
    -Uri "${baseUrl}?type=CUSTOMER&status=ACTIVE&page=1&limit=50&search=Demo" `
    -Headers $headers
```

| Query parameter | Behavior |
| --- | --- |
| `page` | Default 1. Invalid/nonpositive values fall back to 1. Values above 100,000 return 422. |
| `limit` | Default 50; valid range 1–200. Invalid/out-of-range values fall back to 50. |
| `type` | Optional `CUSTOMER` or `SUPPLIER`; case-insensitive. Other values return 422. |
| `status` | Optional `ACTIVE` or `INACTIVE`; case-insensitive. Omitted means both. Other values return 422. |
| `search` | Optional substring search across account name, phone and GSTIN. Trimmed and truncated to 100 bytes; SQL wildcard characters are escaped. URL-encode user input. |

Results are ordered by `account_id` descending. Search case sensitivity follows the database collation. Adding `id` switches GET to a single-party read, so listing filters no longer apply.

### Update selected fields

```powershell
$changes = @{
    phone = '9876501234'
    note = $null
} | ConvertTo-Json

Invoke-RestMethod -Method Patch -Uri "${baseUrl}?id=$partyId" `
    -Headers $headers -ContentType 'application/json' -Body $changes
```

Updating an inactive party returns 409. Updating a system account returns 403. Party classification cannot be changed through PATCH.

### Deactivate

```powershell
Invoke-RestMethod -Method Delete -Uri "${baseUrl}?id=$partyId" -Headers $headers
```

DELETE sets `is_active=0`; it does not remove the database record. Deactivated parties remain readable and appear in unfiltered lists. Deleting an already inactive party returns 200 with `"message":"Party already inactive"` and no `data` field. System accounts cannot be deactivated. There is no reactivation endpoint or outstanding-invoice check in this implementation.

### Postman

1. Create variables `baseUrl` and `apiKey` using the values above.
2. Set Authorization to Bearer Token with `{{apiKey}}`.
3. Select the method and use `{{baseUrl}}`, adding `?id=123` for individual records.
4. For POST/PATCH, choose Body → raw → JSON and provide supported fields.
5. Inspect the HTTP status and JSON response. Replace example IDs with real IDs.

The collection in the old nested package uses the old route structure; update its URLs before using it with this endpoint.

## 6. Response formats

Create (201), read (200) and update (200) return the same party shape. This is an illustrative payload, not a captured response; optional defaults and timestamp nullability depend on the database:

```json
{
  "success": true,
  "data": {
    "account_id": 123,
    "party_type": "CUSTOMER",
    "is_active": true,
    "account_name": "Demo Customer",
    "display_name": "Demo Customer",
    "phone": "9876543210",
    "email": "accounts@example.com",
    "address": "10 Example Road",
    "state": "Delhi",
    "pincode": "110001",
    "country": "India",
    "gstin": null,
    "pan": null,
    "gst_reg_type": "",
    "contact_person": "Accounts Team",
    "note": "Created through Bahi API",
    "created_dtm": "2026-10-23 10:00:00",
    "updated_dtm": null
  }
}
```

`account_id` is an integer and `is_active` is a boolean. The API writes timestamps using MySQL `UTC_TIMESTAMP()`, but returns database timestamp strings without a timezone suffix. Existing records retain their stored timestamp conventions. Business IDs, group codes, system flags, deactivation timestamps and audit actors are not exposed in the party response.

An empty list returns:

```json
{
  "success": true,
  "data": [],
  "pagination": {"page": 1, "limit": 50, "total": 0, "total_pages": 0}
}
```

Nonempty lists put party objects in `data`. Successful first-time deactivation returns:

```json
{
  "success": true,
  "message": "Party deactivated",
  "data": {"account_id": 123, "is_active": false}
}
```

API errors use:

```json
{
  "success": false,
  "error": {"code": "RESOURCE_NOT_FOUND", "message": "Party not found"}
}
```

## 7. Error reference

| HTTP | Error code | Meaning / action |
| --- | --- | --- |
| 400 | `INVALID_ID` | Send a positive integer ID. |
| 400 | `INVALID_JSON` | Correct malformed or missing JSON. |
| 400 | `INVALID_BODY` | Send a nonempty JSON object, not a list, scalar or null. |
| 401 | `AUTH_MISSING_OR_INVALID` | Supply a correctly formatted Bearer header. |
| 401 | `AUTH_INVALID` | Key hash was not found; verify the issued key. |
| 401 | `AUTH_DISABLED` | Integration is not ACTIVE. |
| 401 | `AUTH_EXPIRED` | Obtain a valid key from the administrator. |
| 403 | `BUSINESS_INACTIVE` | Business is not active. |
| 403 | `INVALID_SCOPES` | Administrator must correct stored scope JSON. |
| 403 | `ACCESS_DENIED` | Integration lacks the required scope. |
| 403 | `PROTECTED_ACCOUNT` | System account cannot be modified/deactivated. |
| 404 | `ROUTE_NOT_FOUND` | URL does not match the PHP router. |
| 404 | `RESOURCE_NOT_FOUND` | ID is absent or outside the integration's business/group boundary. |
| 405 | `METHOD_NOT_ALLOWED` | Method or method/ID combination is unsupported. |
| 409 | `DUPLICATE_ACCOUNT_NAME` | Create/update encountered a database duplicate-key error mapped to this code. |
| 409 | `INACTIVE_ACCOUNT` | PATCH cannot update an inactive party. |
| 413 | `BODY_TOO_LARGE` | Reduce JSON body to the configured byte limit. |
| 422 | `UNKNOWN_FIELD` | Remove unsupported fields. |
| 422 | `VALIDATION_ERROR` | Correct field values or listing parameters using the error message. |
| 500 | `DATABASE_ERROR` | Create/update database operation failed; administrator should inspect logs. |
| 500 | `INTERNAL_ERROR` | Unexpected error caught by the entry point; inspect server logs. |
| 503 | `GROUP_CONFIGURATION_MISSING` | Configure both party group codes. |
| 503 | `GROUP_CONFIGURATION_INVALID` | Verify distinct codes and active groups for the business. |

Checks run in sequence: route/ID validation, authentication, method/scope validation, group mapping, then the operation. Requests with several problems may report the first encountered error. An Apache 404 is distinct from JSON `ROUTE_NOT_FOUND`.

## 8. Client behavior and integration testing

There is no idempotency-key or external-reference support. After a POST timeout, search/read before retrying: the first request may already have created the party. Duplicate-name behavior depends on the database unique constraints and collation; the controller maps MySQL duplicate-key error 1062 to `DUPLICATE_ACCOUNT_NAME`.

Before releasing a client, verify on a test business:

1. Direct `.php` and preferred extensionless routing, and forwarding of Authorization to PHP.
2. Missing/invalid/disabled/expired keys and each missing scope.
3. Both customer and supplier creation, followed by read, filtered pagination, PATCH and DELETE.
4. Invalid JSON, unsupported fields, nullable fields and validation boundaries.
5. A second business cannot access or modify the first business's party IDs.
6. System and inactive account restrictions; repeated DELETE behavior.

Successful linting alone does not verify database schema compatibility, group configuration, authorization forwarding or CRUD behavior.
