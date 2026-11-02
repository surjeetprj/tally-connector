# innoforia-tally-connector

Standalone Windows desktop connector for Innoforia Bahi REST APIs and TallyPrime.
The specified source-package structure and project metadata are established.
A native source application now reads parties from the existing Bahi/Tally test
pair, reviews matching suggestions and saves explicitly confirmed local links.
Remote master changes and accounting transfers remain disabled. See
[read-only discovery](docs/master-sync/READ_ONLY_DISCOVERY.md) for usage/evidence.

Start with the [documentation index](docs/README.md).

- [Agent instructions](AGENTS.md) and [current progress](docs/STATE_AND_PROGRESS.md):
  working rules, verified state and the next development task.
- [Project specification v2.1](docs/PROJECT_SPECIFICATION.md): requirements,
  architecture, supported modes and reliability rules.
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md): phased backlog, dependencies,
  tasks and acceptance gates.
- [Bahi API integration](docs/api/bahi/README.md): documented endpoints, mappings,
  limitations and the five source handbooks.

The repository follows the [specified layout](docs/PROJECT_SPECIFICATION.md#3-project-layout):

```text
src/innoforia_tally_connector/  # Application package ownership and boundaries
tests/                        # Application test packages and existing phase0 checks
scripts/phase0/               # Explicit experiments, including authorized live tests
packaging/                    # Production PyInstaller/Inno Setup ownership
docs/                         # Specifications, progress, contracts and evidence
```

`requirements.txt` is the runtime dependency source read by pyproject.toml.
Development/build requirements are separate. The production `requirements-lock.txt`
will be generated after the complete runtime set is installed and validated;
the existing Phase 0 lock remains scoped to its experiment. The new
`requirements-dev-lock.txt` records the repaired Python 3.13 source/test environment;
see the [read/link slice](docs/master-sync/READ_LINK_FOUNDATION.md#environment-repair).

Run all configured offline checks with:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Launch the native source application with:

```powershell
.\.venv\Scripts\python.exe -m innoforia_tally_connector
```

The initial profile verifies business 52 and SIS Dummy, using the existing Windows
credential reference. Confirm the observed classification roots in the screen;
there is no automatic party linking. Runtime storage remains
`%LOCALAPPDATA%\InnoforaiTallySync\`. Source readiness does not certify an installer
or frozen build. See [test organization](tests/README.md) and
[packaging](packaging/README.md).

Next: owner review of actual party identities and separate write/read-back policy
experiments before enabling master changes. See [current progress](docs/STATE_AND_PROGRESS.md).
