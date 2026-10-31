# Master sync design

Status: planned. See [the preparation index](README.md) for authority and reading order.

## Scope and release boundaries

| Master | Initial supervised support | Boundary |
| --- | --- | --- |
| **CUSTOMERS** | Link existing records; create and allowlisted updates in either selected direction | Map CUSTOMER to an explicitly confirmed debtor-ledger classification |
| **SUPPLIERS** | Link existing records; create and allowlisted updates in either selected direction | Map SUPPLIER to an explicitly confirmed creditor-ledger classification |
| **ITEM GROUPS** | Link/create groups; verify hierarchy and supported metadata | Bahi tax attributes do not automatically have a Tally stock-group equivalent |
| **ITEMS** | Link/create supported untracked GOODS after group/unit mapping | Missing manufacturer, sale price or type blocks Bahi creation |
| **UNITS** | Link existing units only | No supplied Bahi UOM API; obtain confirmed codes from the business owner |

SERVICE/CHARGE representation needs separate live/accounting validation; never
convert these to inventory stock items by default. The current Bahi sample item
84 is SERVICE, so it is not evidence for a GOODS transfer. Treat unsupported
tracking, compound units, multiple price lists and nonrepresentable tax details
as blocking issues until a specific contract is approved and tested.

Exclude invoice/voucher creation, opening/running balances, stock quantities,
automatic deactivation/deletion, general ledger CRUD and automatic lifecycle
propagation. Existing inactive/system parties are not update candidates.

## Direction and ownership

The first release offers **BAHI TO TALLY** and **TALLY TO BAHI** as separate
supervised runs. Neither direction is selected silently. Each preview identifies
the source, destination and exact fields affected.

Suggested conservative policy: record a source owner per master type and a
per-field allowlist for each binding. Reversing the direction requires reviewing
that policy; it must not silently overwrite destination-owned fields. The product
owner must confirm this policy before mutation is enabled. Simultaneous changes
are conflicts, not last-write-wins. Link-only operations establish identity and
baseline observations, not permission to overwrite differing content later.

## Execution and dependencies

For a visual walkthrough, use the [sequence diagrams](MASTER_SYNC_SEQUENCES.md)
and [operation states](MASTER_SYNC_STATES.md). These explain the shared design,
not implemented signatures or tested remote behavior.

1. Verify the authenticated Bahi business and Tally company identity. Capture
   that binding/generation on each operation; reject stale results after switching.
2. Read available lists/details and label snapshot freshness/completeness.
   Resolve party classifications, parent groups and existing unit codes.
3. Generate suggestions using [matching rules](MASTER_MATCHING_RULES.md).
   Require explicit linking or creation decisions and validate required fields.
4. Preview field differences using [the mapping matrix](MASTER_FIELD_MAPPING.md).
   Persist selected intent, expected identities/versions/content and dispatch
   entries in one short metadata transaction; enqueue durable operation IDs.
5. Before sending, re-read dependencies and destination content. Invalidate a
   stale preview or conflicting mapping. A preflight read reduces risk but is
   not atomic conditional-write protection against concurrent remote edits.
6. Process groups parent-first and items only after group/unit confirmation.
   Party operations can proceed independently. A blocked parent blocks its
   descendants, not unrelated records. Tally Primary is a built-in root, never
   a group to create. Changing a parent requires cycle/conflict checks.
7. Save the external attempt before IO. Apply one master at a time initially;
   verify company-scoped identity and supported content by read-back. Commit
   the mapping/result only after verification. No transaction spans HTTP.
8. Publish queued UI events and retain operation-level results. Repeated clicks
   and redispatch must not produce repeated business effects.

Master use cases live in `application/masters/`; shared durable execution,
reconciliation and conflicts live in `application/sync/`. Ports separate these
from persistence and concrete adapters. Every Tally request uses the shared
serialized gateway, including discovery and read-back. UI uses bridge/controllers
and background services; it never directly accesses HTTP, ORM sessions or Huey.

## Recovery and update safety

Known returned IDs permit targeted read-back. A timeout/crash after send creates
an uncertain result, even when no ID was saved. Searching names or seeing no
candidate does not prove that another POST is safe. Retain uncertainty visibly
until authoritative outcome lookup, verified identity evidence or explicit
administrative reconciliation resolves it. Retry only actions proved safe.

Bahi party creation explicitly lacks idempotency/external reference support;
equivalent guarantees for group/item creation are not verified. Conditional
updates are also missing. Supervised experiments can expose these limitations;
they cannot certify unattended duplicate-free or conflict-free operation.
Use the shared lifecycle in the specification, not a new master-only state enum.

## Finding later changes

- First scans establish observed identities and supported content, with explicit
  handling of pre-existing records. An unfamiliar ID means newly discovered,
  not necessarily newly created.
- Bahi scans follow documented pagination and compare normalized allowlisted
  content hashes. Item-group creation dates cannot detect edits; the group table
  has no update audit columns. Concurrent paging is not a stable snapshot.
- Tally GUID identifies a record; AlterID filters are candidate discovery only.
  New/edit coverage, ordering, page boundaries and restore behavior remain open.
  Keep company/type-scoped capture checkpoints and durable blocked outcomes.
- Imported content must not immediately echo back as a new edit. Compare against
  the acknowledged baseline; do not discard every future edit to an imported ID.
- Missing records are investigation candidates, not evidence authorizing deletion.

## Backend contract gaps for masters

Extend the existing [sync proposal](../api/bahi/SYNC_EXTENSION_CONTRACT.md), without
inventing another deployed route family:

| Capability | Master-specific need |
| --- | --- |
| Snapshot/change feed | Business/type-scoped party/group/item changes, hierarchy edits and lifecycle events; stable baseline handoff |
| Idempotency/outcome lookup | Durable create key and authoritative result lookup for each master type |
| Conditional versions | Reject stale party/item/group updates, including concurrent hierarchy changes |
| Origin/ack | Distinguish imported changes from subsequent human edits |
| Writer ownership | Reject competing connector writers for the same binding |
| Configuration/UOM lookup | Read permitted existing codes, party groups and item creation prerequisites |

No backend source is available. These are backend-owner deliverables; no local
testing directory substitutes for authoritative implementation or live evidence.

## Decision register

All decisions below are **OPEN**. Implement read-only capabilities while they
are unresolved; block only dependent writes rather than inventing defaults.

| ID | Decision needed | Proposed starting point | Reviewer |
| --- | --- | --- | --- |
| MD-01 | Direction and field ownership | One selected direction per supervised run; explicit field allowlist | Product/business owner |
| MD-02 | Customer/supplier classification | Confirm permitted Tally ledger groups and Bahi group setup; dual-role cases need review | Accounting owner |
| MD-03 | Duplicate and identity policy | Confirm links; ambiguous candidates require review | Business owner |
| MD-04 | Item creation prerequisites | Existing units/groups; explicit manufacturer, type and price values | Product/business owner |
| MD-05 | Tax and service representation | Enable only fields/types with round-trip evidence | Accounting + connector |
| MD-06 | Rename, parent and unit/group changes | Preview renames; block existing item unit/group changes in this slice | Accounting + product |
| MD-07 | Safe automated writes | Implement version, idempotency and ownership contracts before unattended mode | Backend + connector |

Track execution in [the implementation plan](../IMPLEMENTATION_PLAN.md#master-first-work-packages),
not in a second checklist here.
