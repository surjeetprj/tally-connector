# Development documentation

Current baseline: Project Specification v2.1, updated 31 October 2026. The connector
source-package layout and project metadata exist; runtime services and the UI
are not implemented. Phase 0 has executed initial
read-only Tally/Bahi probes, offline tests and a source Qt/Huey lifecycle spike.
The packaged spike now passes after native DLL search isolation; one authorized
Bahi purchase and a known-ID recovery test passed. Handbook examples alone do
not establish deployment compatibility.

## Reading order and ownership

| Document | Owns |
| --- | --- |
| [Agent instructions](../AGENTS.md) | Working rules, navigation and verification expectations |
| [Current state and progress](STATE_AND_PROGRESS.md) | Implemented state, latest checks, unresolved dependencies and next concrete task |
| [Architecture diagram](ARCHITECTURE.md) | Visual guide to target components, execution flow and runtime boundaries |
| [Master sync preparation](master-sync/README.md) | Design, field mapping, matching rules, UI flow and validation for the master-first milestone |
| [Phase 0 contract checklist](phase0/CONTRACT_VALIDATION.md) | Purchase scope, field matrix, evidence levels and backend validation backlog |
| [Tally experiment evidence](api/tally/README.md) | Executed read-only probes, sanitized observations and unverified guarantees |
| [Live Bahi validation](api/bahi/LIVE_VALIDATION.md) | Authenticated business identity and sampled GET contracts |
| [Qt/Huey compatibility](phase0/QT_HUEY_COMPATIBILITY.md) | Passing source/frozen spike, ICU collision fix and remaining gates |
| [Controlled Bahi posting](api/bahi/CONTROLLED_POSTING.md) | Authorized retained test invoice and known-ID recovery evidence |
| [Proposed sync extensions](api/bahi/SYNC_EXTENSION_CONTRACT.md) | Backend handoff; capabilities not yet implemented or deployed |
| [Project specification](PROJECT_SPECIFICATION.md) | Requirements, architecture, technology choices, operating modes and reliability rules |
| [Implementation plan](IMPLEMENTATION_PLAN.md) | Phases, task IDs, dependencies and acceptance gates |
| [Bahi integration assessment](api/bahi/README.md) | Endpoint capabilities, field transformations, integration gaps and API-specific backlog |
| [Source handbooks](#bahi-api-handbooks) | Supplied Bahi REST wire contracts; verify against deployment before enabling writes |

Start each development task with the agent instructions and current-state file,
then read only the references relevant to the task. The specification governs
implementation decisions. Use the plan to select a
bounded milestone and its acceptance criteria. Consult the assessment and relevant
handbooks before changing an adapter. Resolve differences between live behavior
and the documented contract explicitly; do not invent successful responses or
fallback business values.

## Bahi API handbooks

The supplied filenames and contents are preserved under `api/bahi/handbooks/`:

- [Business setup check](api/bahi/handbooks/API-BIZ-SETUP-CHECK-HANDBOOK.md)
- [Parties](api/bahi/handbooks/API-PARTY-DEVELOPER-HANDBOOK.md)
- [Item groups](api/bahi/handbooks/API-ITEM-GROUP-DEVELOPER-HANDBOOK.md)
- [Items](api/bahi/handbooks/API-ITEM-DEVELOPER-HANDBOOK.md)
- [Invoices v2](api/bahi/handbooks/API-INVOICE-DEVELOPER-HANDBOOK_v2.md)

Examples, migration instructions and test commands inside these references are
context, not authorization to run writes or migrations against a live business.

## Development starting point

1. Complete CON-001 through CON-003: agree scope/API capabilities, validate Tally
   identity/read-back/delta queries, and prove Qt/Huey lifecycle and packaging.
2. Prepare BAH-001 through BAH-003: schemas, sanitized fixtures, business binding
   and read adapters.
3. Deliver supervised master discovery, confirmed linking and bounded transfers
   using the [master-first work packages](IMPLEMENTATION_PLAN.md#master-first-work-packages).
4. Prove an ordinary untracked purchase transfer using confirmed existing
   party/item/UOM mappings, with separate draft/post stages and recovery tests.

Automatic bidirectional writes remain gated on verified backend change capture,
idempotency, versions, origin and writer ownership. Receipt/Payment, general
ledger and UOM APIs were not supplied; confirm capabilities or defer those areas.

## Maintenance

Keep requirements in the specification, delivery tracking in the plan and API
details in the integration assessment. Update STATE_AND_PROGRESS after development
tasks with observed results and the next action; do not duplicate full contracts
or source signatures there. Add verified Tally notes under `api/tally/` during
Phase 0 once experiment evidence exists. Update links when moving documents.
Preserve supplied handbooks as reference sources and distinguish proposed behavior
from implemented behavior. BahiAI-Desktop modules named in the plan are reuse
candidates, not runtime dependencies of this standalone project.

Superseded specifications and the temporary chat-migration handoff have been
removed. Their development-relevant findings are incorporated into the documents
above. The original user-supplied attachments and Downloads files were not changed.
