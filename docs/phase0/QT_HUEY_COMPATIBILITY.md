# Qt/Huey compatibility experiment

Updated 29 October 2026. **Local source and fresh frozen execution pass.**
The original QtCore startup failure is resolved. This remains an experiment,
not a complete application or a clean-machine installer validation.

## Tested environment

Python 3.12.8, PySide6 6.11.1, Huey 3.5.3, PyInstaller 6.21.0 and packaging hooks
2026.6, in the isolated project .venv on this Windows 11 host. See experiment-only
[requirements](../../scripts/phase0/requirements.txt) and
[resolved lock](../../scripts/phase0/requirements-lock.txt). These pins establish
the tested spike baseline, not a blanket supported-platform/security guarantee.

## Root cause and reproducible fix

PyInstaller's dependency search collected `icuuc.dll` from the tooling runtime's
Poppler directory, instead of allowing Qt to resolve Windows' system ICU library.
The collected library had incompatible version-suffixed exports. Source Qt used
`C:\Windows\System32\icuuc.dll`; the copied library shadowed it in the executable.
Analysis-00.toc identified the foreign source. Changing Qt alone did not fix it.

[build_spike.py](../../scripts/phase0/build_spike.py) now gives PyInstaller an
explicit PATH containing the selected Python environment and Windows directories,
excluding unrelated native tools. The [spec](../../scripts/phase0/qt_huey_spike.spec)
rejects foreign ICU collisions and does not redistribute the Windows ICU DLL.
The supported-OS matrix must account for that system dependency.

The fixed build was produced into a fresh output/work directory. It contained no
bundled icuuc.dll and passed without manual edits. No Windows system file changed.
The earlier VC runtime replacement experiment did not fix the failure and is not
part of this recipe. Failed artifacts under other ignored build directories remain
historical test outputs, not releases. A slow 6.10.2 download was abandoned before
installation. A consistent 6.11.1 environment was then installed from cached wheels.

## Runtime checks

[qt_huey_spike.py](../../scripts/phase0/qt_huey_spike.py) uses three synthetic local
operation IDs, separate metadata/queue SQLite files and no credentials/network.
Its small schema and retry policy are not the production outbox/recovery system.
Consumer.start() runs on the process main thread before Qt's event loop; a single
thread worker executes tasks. The consumer stops after the tested queue is idle.

Both source and frozen runs verified eleven assertions:

- Three operations completed; one worker task active at a time, off the Qt thread.
- Three queued completion signals arrived on the Qt main thread.
- Duplicate dispatch of a completed operation had no extra effect.
- An intentional first-attempt failure retried once and completed.
- Qt heartbeat continued, event loop exited normally and idle stop was bounded.
- The packaged XML template loaded and SVG icon rendered via __file__-relative paths.

The seed process exited before the consumer started; a separate run process used
its persisted queue. The no-console onedir executable was launched from the temp
working directory, with an absolute runtime path and no external Python command.

Evidence:

- [Passing source run, 6.11.1](evidence/qt-huey-source-6111.json)
- [Passing fresh frozen run](evidence/qt-huey-frozen-fixed.json)
- [Earlier 6.12 source experiment](evidence/qt-huey-source.json)

The injected RuntimeError in source console logs is intentional; final assertions
passed. No in-flight shutdown or uncertain network-write guarantee is inferred.

## Reproduction

Use fresh runtime folders for repeats; completed records are retained.

```powershell
.\.venv\Scripts\python.exe scripts/phase0/qt_huey_spike.py --runtime-dir .phase0-runtime/source-new --mode seed
.\.venv\Scripts\python.exe scripts/phase0/qt_huey_spike.py --runtime-dir .phase0-runtime/source-new --mode run
.\.venv\Scripts\python.exe scripts/phase0/build_spike.py
```

Executable: `build/phase0-fixed-dist/ConnectorPhase0/ConnectorPhase0.exe`.
Run with an absolute --runtime-dir and modes seed/run. Do not replace the isolated
build command with an ambient-PATH invocation that can recollect unrelated DLLs.

## Remaining validation

Clean supported Windows installation, in-flight shutdown/crash recovery, scheduler
coalescing, production gateway concurrency, tray behavior and installer/login
startup remain separate checks. This host-level packaging fix does not implement
the connector, its adapters or its external-write state machine.

References: [Huey embedding](https://huey.readthedocs.io/en/stable/api.html),
[Qt timers](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QTimer.html),
[PyInstaller resources](https://pyinstaller.org/en/stable/runtime-information.html).
