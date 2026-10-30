# Item Group API

Endpoint: `/web-api/api-item-group.php` or `/web-api/api-item-group` with the included Apache rewrite rules.
Uses the supplied `product_group` table without schema changes, shared Bearer authentication and the existing item permissions.

| Method | Route | Scope | Result |
| --- | --- | --- | --- |
| GET | `/api-item-group` | `item:read` | Paginated list |
| GET | `/api-item-group/123` or `?id=123` | `item:read` | Single group |
| POST | `/api-item-group` | `item:create` | Create, HTTP 201 |
| PATCH | `/api-item-group/123` or `?id=123` | `item:update` | Update, HTTP 200 |

DELETE, PUT and OPTIONS return 405. The table has no deactivation column; this endpoint does not delete groups.
Send `Authorization: Bearer <API_KEY>` and JSON bodies with `Content-Type: application/json`.

```json
{
  "grp_name": "Electronics",
  "grp_desc": "Electronic products",
  "hsn_code": "8543",
  "gst": "18",
  "parent_grp_id": 0,
  "taxability_type": "Taxable",
  "cess": "0.00",
  "disp_seq": 500
}
```

Create requires `grp_name`, `grp_desc`, `hsn_code` and `gst`. Name must be nonblank; the other strings allow empty values as permitted by the supplied table. Maximum lengths are 64, 256, 10 and 10 respectively. GST remains a string, matching the schema. Taxability accepts `Taxable`, `Exempt`, `Nil Rated` or `Non-GST`. Cess accepts null or a nonnegative decimal with at most four integer and two decimal digits. Send decimal strings to preserve precision. `disp_seq` accepts null or a signed 32-bit JSON integer. Omitted fields use table defaults.

`parent_grp_id` is a nonnegative 32-bit JSON integer; zero denotes a root. Nonzero parents must exist in the authenticated business. Updates cannot introduce a hierarchy cycle. On MyISAM, hierarchy checks and writes are not atomic; concurrent hierarchy edits require application-level coordination.

The server supplies `biz_id`, `grp_id`, UTC `created_dtm` and `created_by=api:<integration_id>`. These fields are not writable. PATCH preserves creation metadata; this table has no update audit columns. All reads, reference checks and writes are scoped to the authenticated business. Group names are not required to be unique because the table has no such constraint.

List supports `page` (1–100000, default 1), `limit` (1–200, default 50), `parent_grp_id` (including zero), `taxability_type`, and `search` (up to 100 characters, literal name/HSN substring). Results sort by `disp_seq`, then `grp_id`, with the standard `success`, `data` and `pagination` envelope.

Run `php tests/item-group-api-test.php` for SQLite-backed controller checks. These checks do not verify live Apache/MySQL deployment.
