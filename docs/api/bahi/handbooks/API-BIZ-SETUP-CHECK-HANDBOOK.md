# Check API Business Setup

Endpoint: `GET /web-api/check_api_biz_setup.php`.
The extensionless URL `/web-api/check_api_biz_setup` uses the included `.htaccess` and requires Apache rewrite support.

Send the API key in the Authorization header:

```http
GET /web-api/check_api_biz_setup.php HTTP/1.1
Authorization: Bearer <API_KEY>
Accept: application/json
```

No body, business ID parameter or additional scope is required. The business is always resolved from the authenticated API key. Shared authentication checks the integration, its status, expiry, business status and scopes configuration.

Successful response (example):

```json
{
  "success": true,
  "message": "API setup okay with Biz_id: 51, Biz_name: Example Business",
  "data": {
    "biz_id": 51,
    "biz_name": "Example Business"
  }
}
```

A successful check confirms this endpoint can authenticate the key, connect to the configured database and retrieve its active business. It does not validate customer/supplier group mappings, other endpoint permissions, or stock/accounting posting configuration.

Failures use the shared JSON error envelope: 401 for missing/invalid/disabled/expired credentials; 403 for inactive business or invalid scopes configuration; 405 for unsupported methods; 500 for unexpected server/database failures. Secrets and raw database errors are not returned.

Run `php tests/check-api-biz-setup-test.php` for isolated endpoint/authentication checks against SQLite fixtures. Live Apache/MySQL verification is separate.
