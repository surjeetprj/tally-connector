# Proposed Bahi sync extension contract

29 October 2026. Engineering proposal for the company-owned backend. These
capabilities are not existing APIs and have not been deployed or probed. The
authoritative source is unavailable; implementation requires that source or the
Bahi backend developer. Existing CRUD routes remain the verified integration base.

## Contract decisions

- All access remains key-derived business-scoped. Never accept a client biz_id as
  authority. Validate referenced connector/company binding against that business.
- Retain existing party/item/invoice validation and DRAFT/post separation. Sync
  metadata does not bypass accounting, stock, permission or locked-state checks.
- Use decimal strings for money/quantities, explicit dates, ISO-8601 UTC audit
  timestamps and opaque cursors/versions. Do not use desktop clocks as watermarks.
- Preserve stable source identity, origin and acknowledged canonical versions.
  Name/reference similarity is discovery evidence, not authoritative identity.

## Required operations

Route names are deliberately left for the backend routing/versioning decision.
The logical operations and acceptance guarantees below are the proposed contract.

| Operation | Required inputs/results | Acceptance requirement |
| --- | --- | --- |
| Capabilities | Schema version; supported resources/actions; limits; configuration/UOM availability | Reject unsupported features before mutation; no guessing from a reachable business endpoint |
| Register/renew binding | Connector installation ID; stable target company identity; expected lease token | One active writer per business/company binding; expired lease cannot silently replay an uncertain operation |
| Open baseline snapshot | Resource/date scope; bounded snapshot token and change-feed handoff cursor | Stable page order and coverage during concurrent updates; explicit retention/expiry behavior |
| Read change page | Cursor; bounded limit; resource filter | Immutable event ID, entity ID/type, monotonic entity version, operation, origin and next cursor; include cancellation/deactivation events |
| Apply external change | Binding/source entity identity; source version; idempotency key; body hash; expected target version; canonical supported payload | Atomic conflict check and business write; repeat same key/body returns same identity/result; changed body with same key conflicts |
| Lookup operation outcome | Business/binding/idempotency key | Durable authoritative outcome: not applied, in progress, applied, rejected or unknown; no-match is not automatically safe to replay while the original can still commit |
| Acknowledge export | Event ID/version; binding; verified target identity/version/hash | Idempotent acknowledgment; failure retries acknowledgment only, not target creation |
| Read configuration/UOMs | Authenticated business scope | Stable IDs/codes, active state and supported ledger/setup capabilities; no secret configuration exposure |

Example logical external-change envelope (not a current CRUD request):

```json
{
  "schema_version": 1,
  "binding_id": "server-issued-binding-id",
  "operation_id": "client-durable-operation-uuid",
  "source": {
    "system": "TALLY",
    "company_id": "verified-company-guid",
    "entity_type": "INVOICE",
    "entity_id": "verified-voucher-guid",
    "version": "observed-source-version"
  },
  "expected_target_version": null,
  "payload_hash": "canonical-payload-sha256",
  "origin_operation_id": "client-durable-operation-uuid",
  "payload": {}
}
```

`payload` must use an agreed resource schema; the empty object illustrates only
the envelope and is not a valid invoice. Idempotency key scope must include the
authenticated business/binding and action, including separate DRAFT and POST
operations. A hash is an integrity check, not business identity or authorization.

## Persistence and failure semantics

Define a server-side transaction/locking design covering business changes,
external-identity uniqueness, idempotency results and emitted change events.
Current handbook MyISAM compensation is insufficient for crash-atomic guarantees.
Do not claim reliable sync because these records exist in separate tables.

State the supported retention period for event cursors and operation outcomes.
Expired cursors require a controlled rebaseline; expired idempotency history must
not silently permit old creates to be applied again. Imported origin must survive
feed publication so the connector can suppress echoes without hiding later edits.

Version conflicts must return the current target version and an actionable code;
use a documented 409/412 policy. Validation/permission errors retain structured
codes. Rate limits define Retry-After behavior. Ambiguous failures require outcome
lookup, not automatic mutation replay. No source delete/cancellation is applied
automatically until its accounting/reversal policy is agreed.

## Contract acceptance tests before automatic mode

1. Two identical concurrent creates produce one business effect and one identity.
2. Same idempotency key with a different body is rejected without mutation.
3. Process/database failure at every write/result/event boundary loses no committed
   change and never reports uncommitted data as applied.
4. Concurrent updates with the same expected version permit one winner and return
   a conflict for the other.
5. Snapshot-to-feed handoff covers concurrent changes, ties, cancellation and
   retrying a page; cursors cannot cross business/resource scope.
6. A second PC cannot become a competing writer; lease recovery reconciles an
   existing in-flight result before it may issue another write.
7. Echoed changes retain origin; a subsequent accountant edit generates a new
   version that is not mistakenly suppressed.
8. Repeated acknowledgment never creates a voucher; retention expiry is explicit.

This proposal supplies the backend handoff for Phase 0. Product/accounting and
backend approval are pending; no implementation is inferred. Supervised purchase
work can proceed on verified CRUD contracts with visible uncertain outcomes.

See [live CRUD evidence](LIVE_VALIDATION.md) and
[Phase 0 checklist](../../phase0/CONTRACT_VALIDATION.md).
