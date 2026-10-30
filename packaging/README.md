# Application packaging

`pyinstaller/` owns the future production connector.spec and `inno_setup/` the
future installer.iss. They will be implemented when an application entry point
and its install/upgrade behavior exist. See the
[specification](../docs/PROJECT_SPECIFICATION.md#10-packaging-and-support).

The validated experimental build remains in `scripts/phase0/`. Run it with:

```powershell
.\.venv\Scripts\python.exe scripts/phase0/build_spike.py
```

Its executable is a local lifecycle experiment, not the production connector.
Carry forward the isolated native-library search and foreign-ICU guard when
implementing application packaging. See the
[compatibility evidence](../docs/phase0/QT_HUEY_COMPATIBILITY.md).
