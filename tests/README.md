# Test organization

The existing executable offline checks remain under `phase0/`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests/phase0 -v
```

Application test packages follow the
[specification](../docs/PROJECT_SPECIFICATION.md#3-project-layout). Their package
markers establish ownership only; they do not count as implemented tests.

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
