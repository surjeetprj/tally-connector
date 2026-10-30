# Phase 0 build only; not the production application packaging specification.
from pathlib import Path
import os
import sys
from PyInstaller.utils.hooks import copy_metadata

probe_dir = Path(SPECPATH)
datas = [(str(probe_dir / 'spike_assets'), 'spike_assets')]
datas += copy_metadata('huey') + copy_metadata('PySide6')
a = Analysis([str(probe_dir / 'qt_huey_spike.py')], pathex=[], binaries=[],
             datas=datas, hiddenimports=['PySide6.QtSvg'], hookspath=[],
             hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False)
# Qt on the tested Windows host resolves ICU from System32. A same-name ICU
# from an unrelated tool can have incompatible version-suffixed exports.
# Never silently ship that library; build_spike.py isolates the search PATH.
if sys.platform == 'win32':
    windows = Path(os.environ['SystemRoot']).resolve()
    for destination, source, kind in a.binaries:
        if Path(destination).name.lower() == 'icuuc.dll' and not Path(source).resolve().is_relative_to(windows):
            raise RuntimeError('Non-system ICU collision: build with scripts/phase0/build_spike.py')
    a.binaries = [entry for entry in a.binaries if Path(entry[0]).name.lower() != 'icuuc.dll']
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='ConnectorPhase0',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='ConnectorPhase0')
