# innoforia-tally-connector

Standalone Windows desktop connector for Innoforia Bahi REST APIs and TallyPrime.
The specified source-package structure and project metadata are established.
An offline-tested party discovery/linking core and local persistence are implemented.
Production readers, application entry point and desktop UI are not implemented yet.

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

No application launch command exists yet. Production `__main__.py`, service
bootstrap, build_exe.py and installer scripts are created with their working
milestones. Package markers define ownership without pretending those features
exist. See [test organization](tests/README.md) and [packaging](packaging/README.md).

Next: verify read-only Tally party identity/classification queries and implement
guarded readers/background review UI, then complete confirmed linking before
master writes. See [current progress](docs/STATE_AND_PROGRESS.md).
