import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    pathEX = Path(sys._MEIPASS)
else:
    pathEX = Path(__file__).parent

from loguru import logger as log  # noqa: F401

CONFIG_PATH: Optional[Path] = None
LOG_PATH: Optional[Path] = None

APPLICATION: Optional[QApplication] = None
SETTINGS: Optional[QSettings] = None

app_short_name = "GEMSrun"
app_long_name = "GEMS Runner"
