# Invoice API

Endpoint: `/web-api/api-invoice.php` or `/web-api/api-invoice` with the included Apache rewrite rules. Uses the supplied `table_invoice_header` and `table_invoice_details` schema, shared Bearer authentication, and the existing invoice permissions in the integration management screen.

| Method | Route | Required scope | Behavior |
| --- | --- | --- | --- |
| GET | `/api-invoice` | `invoice:read` | Paginated headers |
| GET | `/api-invoice/123` or `?id=123` | `invoice:read` | Header with `items` |
| POST | `/api-invoice` | `invoice:create` | Create DRAFT, HTTP 201 |
| PATCH | `/api-invoice/123` or `?id=123` | `invoice:update` | Edit DRAFT, HTTP 200 |
| POST | `/api-invoice/123/post` | `invoice:post` | Post stock/ledger and set ACTIVE |
| DELETE | `/api-invoice/123` or `?id=123` | `invoice:cancel` | Cancel draft, or reverse an API-posted active invoice |

All routes also accept `.php`. Posting requires a path ID; `/api-invoice?id=123` does not post. PUT and OPTIONS are unsupported. Use `Authorization: Bearer <API_KEY>` and `Content-Type: application/json` for create/update. The shared body limit is 64 KiB. Enable Apache `mod_rewrite` and `AllowOverride FileInfo` (or All), and deploy the updated `.htaccess` for extensionless routing.

## Create a sales invoice

```json
{
  "txn_type": "SALES",
  "invoice_dt": "2026-10-25",
  "invoice_cust_id": 123,
  "items": [
    {
      "item_id": 456,
      "qty": "2.000",
      "gst_pct": "18.00",
      "hsn_code": "8543",
      "discount_mode": "AMT",
      "discount_amt": "5.00"
    }
  ]
}
```

IDs above are examples: use active account/item IDs from the API key's business. Creating a draft has no stock or accounting effect. Post it using `POST /api-invoice/{invoice_id}/post` (no body needed). Repeating that request returns the active invoice without another posting. Active/cancelled invoices cannot be edited or reopened through this API.

`invoice_cust_id` and 1–200 `items` are required for ordinary invoices/notes. If `invoice_dt` is omitted on create, it defaults to the current date in Asia/Kolkata, independently of the PHP server timezone. Supplied dates are preserved and validated; null/empty dates are invalid. A PATCH that omits the date preserves the stored date. The API field is `invoice_dt`; no `invoice_date` alias is accepted. `txn_type` defaults to SALES and accepts SALES, PURCHASE, SALES_RETURN and PURCHASE RETURN. Returns can omit the party ID because it is inherited from the original invoice. `invoice_cust_id` accepts a positive 32-bit JSON integer or its decimal string representation. Sales require an active customer; purchases require an active supplier, using `bootstrap.php`'s group mapping. Legacy SALES RETURN input is normalized to SALES_RETURN; PURCHASE_RETURN input is normalized to PURCHASE RETURN.

`invoice_num` is optional. If absent, the controller calls `nextDocNumber($dbh, $biz_id, $txn_type)` from InvoiceNumbering.php, using the same helper contract and sequence lookup as the sales/purchase entry pages. It loads `doc_prefix`, `sno_len`, `sno_start` and `sno_pad` from `config_doc_prefix`, finds the latest invoice by invoice_id for that business/transaction type/prefix, and increments its numeric suffix. It does not scan for the maximum suffix across all transaction types. Defaults are INV- for SALES, PUR- for PURCHASE, CN- for SALES_RETURN and DN- for PURCHASE RETURN, with width three/start one/zero padding. Sales returns also recognize a legacy SALES RETURN numbering configuration. Numbers are allocated under the header write lock. Unlike the entry pages' suffix truncation, the helper allows the numeric width to grow instead of wrapping and reusing numbers. Supplying `invoice_num` uses manual numbering; duplicates return 409. The table's uniqueness constraint still applies across transaction types within a business, so use different configured prefixes for separate series. Manual numbering can affect the next automatically selected suffix.

Party name, state, address, PIN, phone and GSTIN are copied from the account if omitted. These snapshots can be supplied explicitly within the header schema's length limits. If an account value is longer than its corresponding invoice column, supply a shorter snapshot. GST mode is derived using the same business/bill-to-state rule as `saleBS-add.php`: blank or same state means local, otherwise interstate. An explicitly supplied conflicting `gst_txn_type` is rejected. Shipping information is stored separately and does not change this reference rule.

## Pricing, discounts and tax

The existing `Pricing::resolveSalesPrice()` service resolves sales prices by date, party price level and quantity. The pricing tables (`product_item_price`, `product_item_level_price`, `price_level`) and the product columns selected by that service must be deployed. A supplied sales price is ignored unless the line explicitly sets `"price_override":"Y"`. With an override, `price` is required. Explicit overrides also allow operation on installations that do not have the newer pricing tables. Purchases always require a supplied price.

The supplied invoice table stores price as DECIMAL(9,2); resolved prices are rounded to that precision before calculations. The agreed price is stored in `price`. Pricing rule IDs, system-price metadata and override flags are not stored because those columns are absent from the supplied schema. Header-only PATCH preserves the stored price; replacing `items` resolves sales prices again unless overridden. Posting validates stored price snapshots rather than repricing a previously agreed draft.

Each item requires `item_id`, positive `qty` and explicit `gst_pct`; price is required for purchases/overrides. The item must be active and belong to the business. Database item type and stock UOM are authoritative; mismatching submitted values are rejected. Item name/UOM default from the item. Optional line fields include `item_note`, `hsn_code`, `discount_mode`, `discount_amt` and `discount_pct`.

Purchases may identify an existing item by `item_name` instead of `item_id`. The name must resolve to exactly one active item in the authenticated business; the API does not create item masters. Serial purchase quantity is derived from the serial list, so `qty` can be omitted and a supplied quantity is replaced with the serial count.

## Purchase references and tracked purchase items

Only the canonical fields `ref_doc_no` and `ref_doc_date` are accepted. There are no aliases such as `reference_doc_no`, `ref_date` or `Ref_date`.

| Transaction | ref_doc_no | ref_doc_date |
| --- | --- | --- |
| SALES | Customer purchase-order number | Customer purchase-order date |
| PURCHASE | Supplier invoice number | Supplier invoice date |

These are separate from `invoice_num` (the internal Bahi voucher number) and `invoice_dt` (the transaction date). A reference number requires a valid reference date; without a reference number the reference date is cleared. Ordinary purchases reject an existing supplier/reference-number/reference-date combination, including an earlier cancelled voucher, matching the duplicate supplier-invoice check in purchase-add.php. Notes and linked returns retain their separate reference rules.

Example purchase with one batch and one serial item:

```json
{
  "txn_type": "PURCHASE",
  "invoice_dt": "2026-10-26",
  "invoice_cust_id": 102,
  "ref_doc_no": "SUP-INV-0042",
  "ref_doc_date": "2026-10-24",
  "items": [
    {
      "item_name": "Batch widget",
      "tracking_mode": "BATCH",
      "qty": "10.000",
      "price": "80.00",
      "gst_pct": "18.00",
      "batch_no": "B-2026-01",
      "batch_mfg_date": "2026-10-01",
      "batch_expiry_date": "2027-10-01"
    },
    {
      "item_name": "Serial widget",
      "tracking_mode": "SERIAL",
      "price": "100.00",
      "gst_pct": "18.00",
      "serial_numbers": ["SN-001", "SN-002"]
    }
  ]
}
```

Use actual supplier/item names and IDs. The item master's tracking mode is authoritative. Batch numbers are required for BATCH, limited to 64 characters, and canonical batch IDs are server controlled. Dates are optional unless already established in inventory; supplied dates cannot contradict the existing batch or place expiry before manufacture. Disabled batches and repeated item/batch lines are rejected. Posting uses the shared `Inventory::stockIn()` service and updates the invoice with the resulting canonical batch ID/expiry snapshot.

SERIAL purchases accept 1–500 nonblank serial strings per item line, up to 80 characters each. Duplicate serials, duplicate serial item lines, and serials already present in inventory history are rejected. The serial request is saved with the draft. Posting uses shared `Inventory::stockInSerials()` and records purchase document/detail linkage. Cancellation uses `Inventory::removeInboundSerials()` and succeeds only while every original serial remains IN and belongs to that purchase detail. Batch cancellation checks remaining batch stock and uses shared stockOut. Failures restore tracked inventory and draft snapshots under the existing compensation workflow.

Apply the reviewed `sql/invoice-tracked-purchases.sql` migration before using tracked purchases if those columns/tables are missing. It adds only missing fields/tables, does not run automatically, and preserves existing stock-column precision. It includes draft-only storage needed for serial lists and batch manufacturing dates, beyond the original invoice table definition. Missing capability returns INVOICE_SCHEMA_INCOMPLETE rather than guessing identities. Existing core invoice/product/stock-journal tables must already exist; configure the item master as BATCH or SERIAL explicitly. Do not infer tracking mode from a request alone.

Discount modes follow the reference form:

| Mode | Calculation |
| --- | --- |
| NONE | Unit price × quantity |
| AMT | (Unit price − discount_amt) × quantity; amount is per unit |
| PCT | Unit price × (1 − discount_pct/100) × quantity |

For PCT, send `discount_pct`, and omit or zero `discount_amt`. For AMT, send `discount_amt`, and omit or zero `discount_pct`. Values conflicting with the selected mode, discounts above unit price, and percentages outside 0–100 are rejected. Stored line `discount_amt` remains the unit discount for AMT and zero for PCT, matching the sales form. Header `discount_amt` summarizes the total line discount; no additional header discount is applied.

Amounts are tax exclusive. Local GST calculates and rounds CGST/SGST independently at half the GST rate; interstate GST calculates IGST at the full rate. Each component and line taxable subtotal is rounded half up to two decimals, and the header sums those stored values. This keeps stored details and the ledger balanced, including half-paise boundaries. GST/HSN are explicit snapshots; this endpoint does not infer GST from product groups or validate statutory tax treatment.

`round_off` is a signed header decimal added after tax, equivalent to the form's rounding adjustment. Send it in the header rather than as a synthetic ROUND_OFF item. Header totals, IDs, creation metadata, status and payment status are server owned. Quantity uses at most seven integer/three fractional digits; money uses seven integer/two fractional digits. Use decimal strings or JSON integers, not floating-point JSON numbers. The server rejects overflow and negative resulting net amounts. Posting requires a nonzero balanced journal.

## Debit and credit notes

Keep `txn_type` as SALES or PURCHASE, and set `note_type` to CREDIT or DEBIT. Both `ref_doc_no` (up to 16 characters) and `ref_doc_date` are required for notes. These references are stored snapshots; they are not an ID-based relationship to another invoice.

| Transaction | Note | Party journal | GOODS stock |
| --- | --- | --- | --- |
| SALES | None / DEBIT | Debit customer; credit sales/output tax | Out |
| SALES | CREDIT | Credit customer; debit sales/output tax | In |
| PURCHASE | None / CREDIT | Credit vendor; debit purchases/input tax | In |
| PURCHASE | DEBIT | Debit vendor; credit purchases/input tax | Out |

These GOODS notes represent quantity movements. For a value-only adjustment, use an actual SERVICE/CHARGE item so stock is unaffected. Reports consuming generic notes must honor `note_type` as well as `txn_type`; reports that classify credit notes solely by SALES_RETURN strings need corresponding report changes for generic SALES/CREDIT notes.

## Returns matching the return entry workflow

Use the exact transaction values SALES_RETURN and PURCHASE RETURN. For example:

```json
{
  "txn_type": "SALES_RETURN",
  "invoice_dt": "2026-10-25",
  "ref_doc_no": "INV-001",
  "items": [
    { "item_id": 456, "qty": "1.000" }
  ]
}
```

The original invoice must be ACTIVE, in the same business, and have txn_type SALES for SALES_RETURN or PURCHASE for PURCHASE RETURN. It must be an ordinary invoice rather than another note/return. The API inherits the party, bill-to snapshots, original GST mode and reference date; a supplied party/date must match. The return date cannot precede the original invoice. The schema limits `ref_doc_no` to 16 characters, so an original invoice number longer than that requires widening this column before linked returns can be represented.

Return items accept only `item_id`, `qty` and optional `item_note`. Effective price is derived from the original taxable amount divided by quantity, matching `return-sales-entry.php`; it is not resolved from today's sales price. Tax rates and HSN are inherited. Price, discount and tax input overrides are rejected. Multiple original lines for the same item can be combined only if their effective unit price, tax, UOM and descriptive snapshots agree; otherwise the base schema needs a source-detail allocation column to distinguish them.

Remaining quantities include earlier active returns and reducing notes against the original invoice, including legacy SALES RETURN records. The limit is checked while saving drafts and again under the posting lock, preventing concurrent drafts from exceeding the original quantity when posted. Cumulative source taxable/tax amounts are allocated to the returned quantity using actual prior refund amounts, so partial returns and cancellations cannot create extra paise through unit-price rounding. A displayed two-decimal effective unit price can therefore differ slightly from the allocated line total divided by quantity. If another return changes the allocation after a draft was prepared, update that draft before posting; stale totals return INVOICE_TOTALS_CHANGED.

SALES_RETURN is automatically marked CREDIT, adds GOODS back to stock, debits sales/output tax and credits the customer. PURCHASE RETURN is marked DEBIT, removes GOODS from stock, credits purchases/input tax and debits the vendor. Posting and cancellation use the same separate actions and invoice permissions as ordinary invoices. Cancel active linked returns/notes before cancelling the original invoice. Legacy detail rows with a null biz_id can be read only through their already business-scoped parent invoice; all new API detail rows include biz_id.

## Stock and accounting

Posting writes `product_item.avail_qty`, `prod_stk_journal` and `ledger_journal`, following the reference application's posting directions. SERVICE/CHARGE items post accounting without stock. Stock-out checks are cumulative across repeated item lines and prohibit negative inventory. Quantity and resulting balances must fit the deployed stock column precision; older integer/two-decimal schemas reject incompatible fractional quantities rather than silently truncating them.

Ordinary PURCHASE entries support BATCH/SERIAL through the shared inventory service after the tracked-purchase migration/setup. Tracked sales, tracked returns and tracked generic credit/debit notes remain unsupported and return TRACKED_ITEM_UNSUPPORTED. Untracked transactions continue to use the existing posting adapter. Serial sales are also unsupported by the current shared sales inventory workflow.

System ledger lookup requires exactly one active ledger with the appropriate name in the business: Sales Revenue or Purchase Accounts; Output CGST/SGST/IGST or Input CGST/SGST/IGST when applicable; and Rounding Difference for a nonzero adjustment. Posting includes the selected party account and updates per-ledger running balances in insertion order, as the existing journal service does. It does not implement cost-of-goods or a second inventory valuation journal absent from the reference sales flow. All journal amounts and running balances must fit DECIMAL(9,2).

Source types follow the existing conventions: SalesInv, PURCHASE, SalesReturn for a sales return/credit note, and PurchaseReturn for a purchase return/debit note. Entries include invoice IDs/numbers and API creation markers. The API does not post or reverse external journal entries it cannot identify as its own.

DELETE cancels a draft without journal effects. For an API-posted ACTIVE invoice it adds opposite stock/ledger movements and preserves the original entries and details. Repeating cancellation is idempotent. Cancellation can fail if reversing an inbound invoice would make stock negative, if tracking has changed, if the journal has been modified outside this workflow, or if a ledger balance would overflow. The invoice remains active on such failures.

## Persistence and deployment

No database DDL is run. Draft saves require the two invoice tables, account_ledger, product_item, biz_establishment and config_doc_prefix. Posting additionally requires the compatible stock and ledger journal tables. The database user needs LOCK TABLES as well as the normal SELECT/INSERT/UPDATE/DELETE permissions.

Production writes take explicit table locks. MyISAM does not support rollback, so the API snapshots affected data and compensates caught failures while holding those locks. This does not provide crash atomicity: a killed PHP process, lost database connection or failed compensation can still require administrator reconciliation. `INVOICE_RECOVERY_FAILED` is logged with business/invoice IDs and requires review. Use transactional tables and a fully transactional posting workflow when crash atomicity is required. Table locks also serialize operations across businesses and can limit throughput.

## Listing and errors

List parameters: `page` (1–100000, default 1), `limit` (1–200, default 50), `txn_type`, `invoice_status` (DRAFT/ACTIVE/CANCELLED/VOID), `date_from`, `date_to`, and literal `search` on invoice number/customer name (up to 100 characters). Lists return headers and pagination; retrieve a specific invoice for its items. All access is scoped to the API key's business.

Responses use the shared `success`, `data`, `error` envelopes. Invalid input/references return 422, missing/other-business invoices return 404, duplicate numbers/invalid transitions/insufficient stock return 409, and missing ledger/pricing/schema configuration returns 503. Unexpected server exceptions remain generic 500 responses with details in the server error log.

Tests: `php tests/invoice-api-test.php`. The suite exercises actual SQL through SQLite, the existing pricing resolver, and an emulated nontransactional path for table-lock cleanup and compensation. It covers sales/purchases, notes, discounts, GST, tenancy, repeated operations and injected write failures. It does not substitute for live MySQL/MyISAM/Apache deployment verification.
