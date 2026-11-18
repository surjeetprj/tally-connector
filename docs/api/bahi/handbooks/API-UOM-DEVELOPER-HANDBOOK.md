# Product UOM API

Uses the supplied `product_uom` schema, shared Bearer authentication, and existing item permissions. The resource key is `(authenticated biz_id, uom_cd)`; there is no numeric ID.

| Method | Route | Scope | Result |
| --- | --- | --- | --- |
| GET | `/web-api/api-uom` | `item:read` | Paginated list |
| GET | `/web-api/api-uom/KG` | `item:read` | One UOM |
| POST | `/web-api/api-uom` | `item:create` | Create, HTTP 201 |
| PATCH | `/web-api/api-uom/KG` | `item:update` | Partial update, HTTP 200 |

The `.php` routes also work, for example `/web-api/api-uom.php?uom_cd=KG`. A path code takes precedence over the query code. URL-encode codes in paths and query parameters. PUT, DELETE, OPTIONS, POST with a code, and PATCH without a code return 405 after authentication. No records are deleted.

## Create

Send `Authorization: Bearer <API_KEY>` and `Content-Type: application/json`:

```json
{
  "uom_cd": "KG",
  "uom_desc": "Kilogram",
  "gst_uqc": "KGS"
}
```

All three fields are required nonblank strings. Maximum character lengths are 8, 32, and 3 respectively. Control characters are rejected. Codes also reject slashes and leading/trailing whitespace. Codes are preserved as supplied; uniqueness follows the database's `utf8mb4_unicode_ci` collation, so case variants conflict within the same business. The same code can exist in different businesses. `gst_uqc` is stored as text; this endpoint does not verify it against an official UQC catalog.

The server supplies `biz_id`, UTC `created_dtm`, and `created_by=api:<integration_id>`. These fields cannot be submitted. A successful response has `success: true` and a `data` object containing the six table columns, with `biz_id` as a JSON integer.

Example create response (HTTP 201):

```json
{
  "success": true,
  "data": {
    "biz_id": 51,
    "uom_cd": "KG",
    "uom_desc": "Kilogram",
    "gst_uqc": "KGS",
    "created_dtm": "2026-11-15 10:00:00",
    "created_by": "api:3"
  }
}
```

## Read one UOM

`GET /web-api/api-uom/KG` returns HTTP 200 with the same response structure shown above. Alternatively, use `GET /web-api/api-uom.php?uom_cd=KG`. A code that exists only in another business returns 404.

## Update

```http
PATCH /web-api/api-uom/KG
```

```json
{"uom_desc":"Kilograms","gst_uqc":"KGS"}
```

Only supplied fields change. `uom_cd` is immutable, including when the submitted code matches the existing code. Creation metadata is preserved. Empty bodies and unknown fields are rejected. This table has no update audit columns.

## List

`GET /web-api/api-uom?page=1&limit=50&gst_uqc=KGS&search=kilo`

- `page`: 1–100000, default 1.
- `limit`: 1–200, default 50.
- `gst_uqc`: optional exact-match filter under the database collation.
- `search`: literal substring of code or description, up to 100 characters. `%` and `_` are escaped.

Results sort by `uom_cd`. The response includes `success`, `data`, and `pagination` (`page`, `limit`, `total`, `total_pages`). All lookups, updates, and listings are scoped to the authenticated business.

Example empty list response (HTTP 200):

```json
{
  "success": true,
  "data": [],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 0,
    "total_pages": 0
  }
}
```

## Controller methods and request flow

`api-uom.php` parses the route, checks the code format, authenticates the integration with `auth()`, and enforces the required permission with `scope()`. It then dispatches to `UomController`.

| Method | Responsibility |
| --- | --- |
| `__construct($ctx)` | Store authenticated business and integration actor |
| `validCode($code)` | Public static format check shared by the route and create validation; does not query the database |
| `fetchRecord($code)` | Private database lookup for the current business; return an array or fail with 404 |
| `validate($in, $create)` | Check writable fields, required create fields, lengths, and immutable code |
| `chkQueryParam($key, $default)` | Read a query string/default and reject array inputs; field-specific validation follows |
| `get($code)` | Fetch one record and send HTTP 200 JSON |
| `create()` | Validate body, insert with creation metadata, fetch result, and send HTTP 201 |
| `update($code)` | Check existence, validate PATCH, update supplied fields, and send HTTP 200 |
| `listing()` | Validate filters/pagination, count matches, and return a page |

`fetchRecord()` returns data so it can be reused by create and update. `get()` sends a response and ends execution through `out()`. Keeping these separate allows create to return HTTP 201 and update to check existence before writing.

For pagination, `chkQueryParam('page', '1')` returns a string. Its result is passed to `filter_var(..., FILTER_VALIDATE_INT, ...)`, which returns an integer in the permitted range or `false`. The helper checks the input type; `filter_var()` checks the numeric value.

## Errors and deployment

| Status | Code | Meaning |
| --- | --- | --- |
| 400 | INVALID_UOM_CODE | Invalid code in route/query |
| 404 | ROUTE_NOT_FOUND | URL does not match the UOM route |
| 404 | RESOURCE_NOT_FOUND | Code not found in this business |
| 405 | METHOD_NOT_ALLOWED | Unsupported method or method/code combination |
| 409 | DUPLICATE_UOM_CODE | Composite primary key already exists |
| 422 | VALIDATION_ERROR | Missing or invalid fields/query values |
| 422 | UNKNOWN_FIELD | Unsupported or server-owned field |
| 422 | IMMUTABLE_UOM_CODE | Attempt to PATCH the code |

Shared authentication/body errors follow `bootstrap.php`. Unexpected server failures return 500 without database details.

Example duplicate-code response (HTTP 409):

```json
{
  "success": false,
  "error": {
    "code": "DUPLICATE_UOM_CODE",
    "message": "UOM code already exists in this business"
  }
}
```

## Request examples

Replace the example host and key with your deployment values. In PowerShell, use `curl.exe` to select curl rather than a shell alias.

```sh
curl --request GET 'https://example.com/web-api/api-uom/KG' --header 'Authorization: Bearer <API_KEY>'
curl --request GET 'https://example.com/web-api/api-uom?page=1&limit=20&search=kilo' --header 'Authorization: Bearer <API_KEY>'
```

For create/update, save the JSON bodies shown above as `uom-create.json` and `uom-update.json`:

```sh
curl --request POST 'https://example.com/web-api/api-uom' --header 'Authorization: Bearer <API_KEY>' --header 'Content-Type: application/json' --data-binary '@uom-create.json'
curl --request PATCH 'https://example.com/web-api/api-uom/KG' --header 'Authorization: Bearer <API_KEY>' --header 'Content-Type: application/json' --data-binary '@uom-update.json'
```

## Deployment and verification

Deploy `UomController.php`, `api-uom.php`, and the updated `.htaccess`. Apply `product-uom.sql` if needed; it does not change an existing table. No live database changes are performed by adding these files. Apache must allow the included rewrite rules for extensionless URLs. Item master UOM validation is unchanged by this endpoint.

Run `php tests/uom-api-test.php` for isolated SQLite-backed checks. These cover validation, duplicate codes, partial updates, business isolation, filters, and pagination. SQLite NOCASE approximates ASCII case-insensitivity; live Apache routing, authentication, MySQL Unicode collation, and MyISAM behavior require deployment verification.
