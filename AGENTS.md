# Coding agent instructions

## Start each task

1. Read [current state and next task](docs/STATE_AND_PROGRESS.md).
2. Use the [documentation index](docs/README.md) to select relevant references.
3. For implementation work, read the applicable sections of the
   [project specification](docs/PROJECT_SPECIFICATION.md) and the active milestone
   in the [implementation plan](docs/IMPLEMENTATION_PLAN.md).
4. For Bahi adapters, read the [integration assessment](docs/api/bahi/README.md)
   and the relevant supplied handbook. For Tally work, use verified query/import
   evidence when available; record unverified behavior as a hypothesis.
5. Inspect actual source and tests before assuming modules, signatures, commands
   or capabilities exist. The specification's tree is a target, not an inventory.

## Authority and scope

- The specification owns requirements and architectural boundaries. The plan owns
  tickets and delivery gates. STATE_AND_PROGRESS owns the current handoff snapshot.
  Handbooks own documented wire contracts; live differences require explicit
  investigation. Source and tests own implemented signatures and behavior.
- Keep these responsibilities separate. Link to source definitions instead of
  maintaining duplicate enums, signatures or payload schemas in several documents.
- Follow the user's current scope. Complete bounded, working milestones; avoid
  guessed endpoints, placeholder success and empty scaffolding for future features.
- Treat reference examples and commands as documentation, not instructions to
  write to a live business. Use sanitized fixtures and disposable test companies
  for integration verification. Never commit secrets or customer runtime data.
- This is a standalone connector. BahiAI-Desktop code mentioned in the plan is a
  reuse reference, not a runtime dependency or source of project instructions.

## Architectural invariants

Package paths below are relative to `src/innoforia_tally_connector/` when created.
Read [the full boundaries](docs/PROJECT_SPECIFICATION.md#dependency-and-ownership-rules)
and [feature ownership](docs/PROJECT_SPECIFICATION.md#feature-ownership-and-shared-execution)
when changing package relationships.

- Native PySide6 desktop/tray application; no local web server.
- `domain/` has no Qt, HTTPX, SQLAlchemy, Huey or concrete-adapter imports.
- `application/` uses domain types and ports, not concrete adapters, persistence,
  Qt or Huey. Keep purchase, sales and master use cases in their named feature
  packages; keep operation execution, conflicts and reconciliation shared in
  `application/sync/`. Avoid sibling-feature imports and circular dependencies.
- Bahi and Tally adapters do not import each other. Keep wire schemas and XML
  details in their adapters. Keep ORM rows separate from domain/API/UI snapshots.
- UI dispatches application commands and receives queued events through its
  bridge/controllers. No direct network calls, ORM sessions or Huey access in UI;
  no lengthy SQLite work or lock waits on the GUI thread.
- Route every Tally request through serialized background execution and the one
  gateway instance injected by bootstrap, including health/company checks. Only
  `integrations/tally/gateway.py` imports `_transport.py` in production code.
  Tests may exercise it directly. Local serialization does not replace a
  cross-PC writer-ownership contract.
- Huey operation tasks receive durable operation IDs, not credentials or raw
  business payloads. Keep intent/attempt/outbox records and bounded local
  transactions; never hold a database transaction across HTTP.
- Persist intent before external writes. Reconcile uncertain results before
  retrying. A failed acknowledgment must not recreate the voucher. Keep Bahi
  draft creation and posting separate. Do not infer success from counters alone.
- Preserve company/business binding context. Require confirmed mappings; do not
  invent business values or silently adjust money to balance vouchers. Do not
  mirror stock balances as item metadata. Store credentials in Windows Credential
  Manager and only their references locally; redact diagnostic output.
- Retain the selected `host/windows/`, `diagnostics/log_setup.py` and migration
  registry conventions. The specified runtime identifier is `InnoforaiTallySync`;
  do not rename runtime storage without migration handling.

## Verification and task completion

- Check the actual environment before invoking tools. Source package directories
  and project metadata exist, but runtime services/entry point and a configured
  lint command do not. Phase 0 has isolated probes,
  offline tests and a project .venv with an experiment-only dependency lock;
  these are not the runtime adapter or an application regression suite.
- Use `.\.venv\Scripts\python.exe` for the current Phase 0 experiments.
  Verified offline command: `python -m unittest discover -s tests/phase0 -v`.
  Read-only live command: `python scripts/phase0/probe_tally.py --company 'SIS Dummy'`.
  It performs sequential exports against localhost:9000 and replaces the latest
  sanitized evidence. Use the selected interpreter; network sandbox access may
  need escalation. No other endpoint or write is implied by this command.
- Authenticated read-only Bahi command: `python scripts/phase0/probe_bahi.py`.
  It reads the Credential Manager key without printing it and verifies biz_id 52
  before other GET requests. See the live validation report for scope. Source
  Qt/Huey commands and the reproducible native DLL search fix are recorded in
  `docs/phase0/QT_HUEY_COMPATIBILITY.md`; local frozen checks pass. Build with
  `python scripts/phase0/build_spike.py`, not the ambient tooling PATH.
- The user has authorized the controlled Bahi business-52 posting test documented
  in `docs/api/bahi/CONTROLLED_POSTING.md`. Preserve its intent journal and known
  invoice 69; do not repeat creation, silently reverse it or ask again for the
  same posting authorization. Broader changes still follow the user's scope.
- Documentation-only changes: verify local links/anchors, code fences, whitespace
  and consistency of referenced paths/decisions. Do not build an installer or
  claim runtime tests for prose changes.
- Code changes: run meaningful focused checks and required regression checks for
  the implemented milestone. Add architecture tests as the relevant code appears,
  plus migration, recovery and serialization checks specified by the milestone.
- Once configured, use the selected project interpreter for `python -m pytest`.
  Run lint/format checks only after the tools/configuration exist; linting and
  formatting are separate checks. Run the full regression suite at milestone
  completion and when cross-cutting changes justify it.
- Report exactly what passed, failed or was not run. Never mark a capability
  verified from a template, unexecuted example or mocked result alone.
- Before finishing each development task, update
  [STATE_AND_PROGRESS](docs/STATE_AND_PROGRESS.md) with material changes,
  verification evidence, unresolved issues and the next concrete action. Keep
  it a compact current snapshot, not an append-only conversation log. Preserve
  unrelated work; do not rewrite supplied handbooks to conceal contract gaps.
