# Product Item API

Endpoint: `http://localhost/A2509/bahi/web-api/api-item.php`

Uses the shared `bootstrap.php`, PDO connection from `../include/dbo.php`, Bearer API keys, active-business checks and JSON response/error envelopes. No schema changes are needed. The supplied DROP/CREATE statements have not been executed.

| Method | Route | Permission | Behavior |
| --- | --- | --- | --- |
| POST | `/api-item.php` | `item:create` | Create item |
| GET | `/api-item.php` | `item:read` | Paginated list |
| GET | `/api-item.php/123` | `item:read` | Retrieve item |
| PATCH | `/api-item.php/123` | `item:update` | Update supplied fields |
| DELETE | `/api-item.php/123` | `item:delete` | Set `avail_status=N` |

An ID may alternatively be passed as `?id=123`. Extensionless `/api-item` routes need the same Apache configuration as `/api-party`. PUT and OPTIONS are unsupported. Assign the listed permissions in the integration's JSON `scopes` array before use.

Send `Authorization: Bearer <API_KEY>` and `Content-Type: application/json` for POST/PATCH. Request size limit: 64 KiB.

## Create example

```json
{
  "item_name": "Widget A",
  "item_disp_name": "Widget A",
  "item_desc": "Example product",
  "item_grp_id": 2,
  "manu_code": "M001",
  "item_type": "GOODS",
  "item_uom": "PCS",
  "item_sale_price": "125.50",
  "tax_source": "ITEM",
  "hsn_sac_code": "12345678",
  "gst_rate": "18.00"
}
```

Required: `item_name`, `item_desc`, `item_grp_id`, `manu_code`, `item_type`, `item_uom`, `item_sale_price`. Omitted fields use the product_item table defaults. Group 2 and UOM PCS must already exist for the authenticated business; no group or UOM is created automatically.

Writable fields use the exact product_item column names, excluding `item_id`, `biz_id`, `created_dtm`, `created_by`, `update_dtm` and `updated_by`. The server owns those fields, uses UTC timestamps, and records the actor as `api:<integration_id>`.

Validation enforces schema lengths, nullability, enum values, integer ranges, and decimal precision/scale. Integer fields require JSON integers. Send decimal strings to retain exact monetary precision; responses preserve decimal strings. Prices and GST are nonnegative, GST is at most 100, and inventory quantity may be negative. Nullable fields can explicitly be cleared with null. Required text must be nonblank.

`item_grp_id` must match `product_group.grp_id` within the same business. `item_uom` is interpreted as `product_uom.uom_cd` (maximum 8 characters), also within the same business. Reference checks run on create and whenever the corresponding field is patched. Manufacturer validation is limited to the supplied column definition.

Tax fields are stored as supplied, with database defaults for omitted fields. This API does not calculate effective tax or copy group GST/HSN into item columns when `tax_source=GROUP`; consumers must resolve group tax from product_group. It does not calculate inventory movements, process image uploads, or create batch/serial records. Image fields are metadata strings.

## List and update

List query parameters: `page` (1–100000, default 1), `limit` (1–200, default 50), `search` (up to 100 characters; literal matching against name, display name and barcode), `item_type`, `avail_status` (`Y` or `N`), and positive `item_grp_id`. Both available and unavailable items are listed unless filtered. Results sort by item_id descending and include `pagination` with page, limit, total and total_pages.

PATCH example: `{"item_sale_price":"149.00","avail_status":"Y"}`. Patching an unavailable item is allowed, including reactivation. DELETE is repeatable and keeps the row and inventory quantity intact.

Create returns 201; successful reads, updates and deactivations return 200. Missing or other-business IDs return 404. Invalid fields/references return 422. Duplicate item names within a business return 409 with `DUPLICATE_ITEM_NAME`. Authentication and permission failures use the shared 401/403 responses.

## Verification

Run `php tests/item-api-test.php` for isolated validation, reference scoping, update and soft-delete checks with a fake database. Run `php -l api-item.php` and `php -l ItemController.php` for syntax checks. Live MySQL/Apache requests have not been verified. MyISAM does not provide transactions or foreign-key enforcement; concurrent changes to reference tables can occur after API validation.
