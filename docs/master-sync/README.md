# Master synchronization preparation

Prepared: 31 October 2026. Status: implementation design, not implemented capability.

The first feature milestone is **SUPERVISED MASTER TRANSFER**, before invoices.
The user selects records and a direction, confirms links and proposed changes,
and reviews verified results. Automatic bidirectional mutation remains gated.

## Reading order

| Document | Purpose |
| --- | --- |
| [Design](MASTER_SYNC_DESIGN.md) | Scope, direction, dependencies, execution and decisions |
| [Field mapping](MASTER_FIELD_MAPPING.md) | Semantic field mapping and representation limits |
| [Matching rules](MASTER_MATCHING_RULES.md) | Link existing records, create new records and handle ambiguity |
| [UI flow](MASTER_SYNC_UI_FLOW.md) | Screens, preview, confirmation and result handling |
| [Sequence diagrams](MASTER_SYNC_SEQUENCES.md) | Message order for linking, successful transfer and uncertain-write recovery |
| [Operation state diagram](MASTER_SYNC_STATES.md) | Normal progress, blocked/conflicting work and reconciliation |
| [Validation](MASTER_SYNC_VALIDATION.md) | Controlled experiments, acceptance cases and evidence |
| [Implementation tasks](../IMPLEMENTATION_PLAN.md#master-first-work-packages) | Ordered work packages and delivery gates |

These documents elaborate the [specification](../PROJECT_SPECIFICATION.md), which
owns requirements. The [plan](../IMPLEMENTATION_PLAN.md) owns task status/gates;
[current progress](../STATE_AND_PROGRESS.md) owns the handoff. The supplied
[Bahi handbooks](../api/bahi/README.md) own wire contracts. Tally field mappings
below are semantic design targets until supported by
[live evidence](../api/tally/README.md). No production XML tags, adapter signatures
or database schemas are declared by these documents.

## Decisions before writes

Use the decision register in [the design](MASTER_SYNC_DESIGN.md#decision-register).
In particular, confirm field ownership, permitted destination party groups,
duplicate handling and which item types can be represented faithfully. A suggested
policy is not permission to write to a live business. This documentation task
does not run master creation, modification, deactivation or invoice posting.
