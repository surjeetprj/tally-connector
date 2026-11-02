"""Selected runtime identifier; never fall back to the current directory."""
import os
from pathlib import Path


def runtime_directory():
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise OSError("Windows Local AppData is unavailable")
    path = Path(local) / "InnoforaiTallySync"
    path.mkdir(parents=True, exist_ok=True)
    return path
