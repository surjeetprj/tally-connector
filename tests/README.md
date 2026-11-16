# Test organization

The default party workspace now has offline batch/auto-restore coverage:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_party_batches.py tests/ui/test_workspace_batches.py tests/ui/test_batch_review_controls.py tests/persistence/test_batch_migration.py tests/unit/application/masters/test_restore.py
```

These cover saved policy/identity restoration, exact Ready-subset approval, both
types/directions, migration v5 rollback, source/binding reservations, cancelled and
expired approval, known-ID reconciliation, lost acknowledgments, dispatch gaps,
atomic audit recovery, GUI heartbeat and restart without creating. All services
are fake and SQLite databases temporary. Computer-use/live verification is owner-run.

The existing executable offline checks remain under `phase0/`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests/phase0 -v
```

Run the complete configured offline suite (including Phase 0) with
`.\.venv\Scripts\python.exe -m pytest -q`. Party discovery/linking, metadata
transactions/migrations and architecture checks now have executable tests; they
use synthetic observations and temporary databases, with no live adapter calls.

Actual-party transfer coverage now includes all four direction/type combinations
through Qt/controller/Huey/bootstrap/adapters/SQLite and restart using fake remote
systems, plus reservations, atomic mapping audits, exclusions, history and v4
migration recovery. These are unit/offline integration tests, not computer-use
automation or live field verification. Focused commands:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_party_transfers.py tests/ui/test_party_transfer_flow.py tests/ui/test_party_drag_review.py
.\.venv\Scripts\python.exe -m pytest -q tests/persistence/test_transfer_migration_recovery.py tests/contract/bahi/test_party_transfer_payload.py tests/contract/tally/test_party_transfer_xml.py
```

The [manual checklist](../docs/master-sync/MANUAL_PARTY_TRANSFER_CHECKLIST.md)
defines owner screenshots and remaining live gates. Do not run live creates in
automated tests or infer Tally tax support from mock responses.

The read-only desktop milestone adds guarded HTTP/XML contracts, migration v2
backups, durable dispatch/recovery, Qt responsiveness and native-screen
link/restart tests. The default suite skips the opt-in live check. Run it only
when the known test pair and credential are available:

```powershell
$env:CONNECTOR_LIVE_READS = '1'
.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_live_party_discovery.py
Remove-Item Env:CONNECTOR_LIVE_READS
```

That check performs only Bahi GETs and Tally exports and writes sanitized evidence
to a temporary directory. See [usage/evidence](../docs/master-sync/READ_ONLY_DISCOVERY.md).
Windows' offscreen Qt plugin lacks system fonts; UI tests explicitly load an OS
font for readable captures without redistributing font files. The native Windows
platform walkthrough also passed separately.

Application test packages follow the
[specification](../docs/PROJECT_SPECIFICATION.md#3-project-layout). Their package
markers alone establish ownership; they do not count as implemented tests.

- `unit/domain/`: canonical business rules and validation.
- `unit/application/{purchases,sales,masters,sync}/`: feature use cases and shared
  execution, with controlled fakes.
- `architecture/`: layer imports, feature boundaries and gateway-only transport.
- `contract/{bahi,tally}/`: wire payloads and external-response behavior.
- `persistence/`: transactions, constraints and migration recovery.
- `recovery/`: write boundaries, uncertainty, idempotency and restart behavior.
- `ui/`: Qt models, queued events and window/tray lifecycle.
- `integration/`: explicitly enabled disposable live environments.
- `packaging/`: frozen imports, assets and clean-system behavior.
- `fakes/`: controllable test adapters; `fixtures/{bahi,tally}/`: sanitized examples.

Pytest discovery is restricted to `tests/` in pyproject.toml. Live Phase 0 scripts
under `scripts/phase0/` are invoked explicitly and must not become collected
tests. No network or accounting writes run as part of the offline command above.
