# Test organization

The existing executable offline checks remain under `phase0/`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests/phase0 -v
```

Run the complete configured offline suite (including Phase 0) with
`.\.venv\Scripts\python.exe -m pytest -q`. Party discovery/linking, metadata
transactions/migrations and architecture checks now have executable tests; they
use synthetic observations and temporary databases, with no live adapter calls.

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
