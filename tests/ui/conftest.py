import os
from pathlib import Path

import pytest
from PySide6.QtGui import QFont, QFontDatabase


@pytest.fixture(autouse=True)
def readable_test_fonts(qapp):
    # Windows' offscreen plugin has no system font database. Load the OS font
    # explicitly for deterministic visual tests; never redistribute it.
    if not QFontDatabase.families():
        font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/segoeui.ttf"
        if font.exists():
            QFontDatabase.addApplicationFont(str(font))
    qapp.setFont(QFont("Segoe UI", 10))
