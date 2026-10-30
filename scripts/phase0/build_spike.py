"""Build the Phase 0 executable with an isolated native DLL search PATH."""
import os
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[2]
    windows = Path(os.environ["SystemRoot"])
    env = os.environ.copy()
    # Do not let unrelated tooling (e.g. Poppler/LibreOffice) contribute native
    # libraries with the same basename as Windows system dependencies.
    env["PATH"] = os.pathsep.join(map(str, [Path(sys.executable).parent,
        Path(sys.base_prefix), Path(sys.base_prefix) / "DLLs", windows / "System32", windows]))
    return subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm",
                           "--distpath", str(root / "build/phase0-fixed-dist"),
                           "--workpath", str(root / "build/phase0-fixed-work"),
                           str(root / "scripts/phase0/qt_huey_spike.spec")],
                          cwd=root, env=env, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
