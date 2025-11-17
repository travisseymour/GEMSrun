from pathlib import Path

from loguru import logger as log  # noqa: F401
from PySide6.QtCore import QSettings
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

CONFIG_PATH: Path | None = None
LOG_PATH: Path | None = None

APPLICATION: QApplication | None = None
SETTINGS: QSettings | None = None

app_short_name = "GEMSrun"
app_long_name = "GEMS Runner"

default_font: QFont = QFont()
