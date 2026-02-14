"""
GEMSrun: Environment Runner for GEMS (Graphical Environment Management System)
Copyright (C) 2025 Travis L. Seymour, PhD

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

from functools import partial
from pathlib import Path
import threading

from munch import Munch
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtGui import QFontMetrics, QResizeEvent
from PySide6.QtWidgets import QComboBox, QDialog, QFileDialog, QMessageBox, QSizePolicy

from gemsrun.gui.paramdialog import Ui_paramDialog
from gemsrun.session.version import (
    __version__,
    check_latest_github_version,
    version_less_than,
)

ERROR = "background : red;"
NORMAL = ""


def shorten_path(path: str, max_length: int) -> str:
    """Shorten a path by truncating the middle if it exceeds max_length."""
    if max_length <= 0 or len(path) <= max_length:
        return path
    # Keep the beginning and end, insert ... in the middle
    keep_chars = (max_length - 3) // 2  # 3 for "..."
    if keep_chars <= 0:
        return path
    return f"{path[:keep_chars]}...{path[-keep_chars:]}"


# {'fname': 'myenvironment.yaml', 'user': 'User1', 'skipdata': True, 'overwrite': True,
# 'debug': None, 'skipmedia': None, 'skipgui': None}


class ParamDialog(QDialog):
    def __init__(self, params: Munch):
        super().__init__()
        self.ok = False
        self._env_valid = False  # Track validation state explicitly
        self._user_valid = False
        self.ui = Ui_paramDialog()
        self.ui.setupUi(self)
        self.setWindowTitle(f"GEMSrun v{__version__}")
        self._check_for_update()
        self.resize(1200, 400)
        self.params = params

        self.settings = QSettings()
        self.recent_envs: list[str] = self._load_recent_envs()

        # load icon
        # pixmap = QtGui.QPixmap(get_resource('images', 'Icon.ico'))
        # self.ui.labelIcon.setPixmap(pixmap)

        # setup initial validations for text fields

        self.ui.envLineEdit.setStyleSheet(NORMAL if self.ui.envLineEdit.text() else ERROR)
        self.ui.userLineEdit.setStyleSheet(NORMAL if self.ui.userLineEdit.text() else ERROR)

        # create change handlers for text fields
        self.ui.userLineEdit.textChanged.connect(partial(self.text_changing, self.ui.userLineEdit, "user"))

        # create change handlers for checkboxes

        self.ui.skipdataCheckBox.stateChanged.connect(partial(self.check_changing, "skipdata"))
        self.ui.overwriteCheckBox.stateChanged.connect(partial(self.check_changing, "overwrite"))
        self.ui.debugCheckBox.stateChanged.connect(partial(self.check_changing, "debug"))
        self.ui.skipmediaCheckBox.stateChanged.connect(partial(self.check_changing, "skipmedia"))
        self.ui.fullscreenCheckBox.stateChanged.connect(partial(self.check_changing, "fullscreen"))

        # dropdown of recent environment files
        self.ui.envLineEdit.hide()  # replace with dropdown
        self.env_history_combo = QComboBox(self)
        self.env_history_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.env_history_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.env_history_combo.setMinimumContentsLength(40)
        self.env_history_combo.setInsertPolicy(QComboBox.NoInsert)
        self.env_history_combo.currentTextChanged.connect(self._env_selected)
        self._populate_env_combo()
        self.ui.horizontalLayout_4.insertWidget(2, self.env_history_combo, 1)  # stretch factor of 1

        # Enter orig values into each widget

        self._set_env_from_history(self.params.fname)
        self.ui.userLineEdit.setText(self.params.user)
        self._user_valid = bool(self.params.user and self.params.user.strip())
        self.ui.userLineEdit.setStyleSheet(NORMAL if self._user_valid else ERROR)
        self.ui.skipdataCheckBox.setChecked(self.params.skipdata)
        self.ui.overwriteCheckBox.setChecked(self.params.overwrite)
        self.ui.debugCheckBox.setChecked(self.params.debug)
        self.ui.skipmediaCheckBox.setChecked(self.params.skipmedia)
        self.ui.fullscreenCheckBox.setChecked(self.params.fullscreen)

        # setup buttons
        self.ui.cancelPushButton.clicked.connect(self.quit)
        self.ui.startPushButton.clicked.connect(self.start)
        self.ui.toolButton.clicked.connect(self.load_envfile)

    def _check_for_update(self):
        """Check GitHub for a newer version in a background thread, amend window title if found."""

        def _do_check():
            latest = check_latest_github_version()
            if latest and version_less_than(__version__, latest):
                QTimer.singleShot(
                    0,
                    lambda: self.setWindowTitle(f"GEMSrun v{__version__}    [GEMSrun version {latest} available]"),
                )

        threading.Thread(target=_do_check, daemon=True).start()

    def check_changing(self, key: str, state: bool):
        self.params[key] = bool(state)

    def text_changing(self, widget, key: str, content: str):
        # highlight bad data
        widget.setStyleSheet(NORMAL if content else ERROR)
        # update data
        if widget == self.ui.envLineEdit:
            is_valid = Path(content.strip()).is_file()
            self.ui.envLineEdit.setStyleSheet(NORMAL if is_valid else ERROR)
            self.params[key] = content.strip()
        elif widget == self.ui.userLineEdit:
            is_valid = bool(content.strip())
            self._user_valid = is_valid
            self.ui.userLineEdit.setStyleSheet(NORMAL if is_valid else ERROR)
            self.params[key] = content.strip()

    def load_envfile(self):
        options = QFileDialog.Options()
        # options |= QFileDialog.DontUseNativeDialog
        file_name, a = QFileDialog.getOpenFileName(
            self,
            "QFileDialog.getOpenFileName()",
            "",
            "GEMS Environment Files (*.yaml);;All Files (*)",
            options=options,
        )
        if file_name:
            self._add_recent_env(file_name)

    def quit(self):
        self.ok = False
        self.close()

    def start(self):
        import sys

        if sys.platform == "win32":
            print(f"[DEBUG] Start pressed: env_valid={self._env_valid}, user_valid={self._user_valid}")
            print(f"[DEBUG] fname={self.params.fname!r}, user={self.params.user!r}")

        if not self._env_valid or not self._user_valid:
            # Build specific error message
            issues = []
            if not self._env_valid:
                issues.append(f"Environment file not found: {self.params.fname}")
            if not self._user_valid:
                issues.append("User ID is empty")
            QMessageBox.warning(
                self,
                "Validation Alert",
                "Please fix the following issues before pressing START:\n\n"
                + "\n".join(f"• {issue}" for issue in issues),
                QMessageBox.StandardButton.Ok,
            )
            return

        if sys.platform == "win32":
            print("[DEBUG] Validation passed, closing dialog...")

        self._add_recent_env(self.params.fname)
        self._persist_recent_envs()
        self.ok = True
        self.close()

    def _normalize_path(self, path_str: str) -> str:
        """Normalize a path string for consistent cross-platform handling."""
        if not path_str:
            return ""
        # Resolve the path to handle forward/backward slashes and normalize
        try:
            resolved = str(Path(path_str.strip()).resolve())
            # Debug: print path resolution on Windows
            import sys

            if sys.platform == "win32":
                is_file = Path(resolved).is_file()
                print(f"[DEBUG] Path: {path_str!r} -> {resolved!r}, is_file={is_file}")
            return resolved
        except (OSError, ValueError) as e:
            import sys

            if sys.platform == "win32":
                print(f"[DEBUG] Path normalize failed: {path_str!r}, error: {e}")
            return path_str.strip()

    def _load_recent_envs(self) -> list[str]:
        stored = self.settings.value("recent_env_paths", defaultValue=[], type=list)
        if stored is None:
            stored = []
        if isinstance(stored, str):
            stored = [stored]
        envs = []
        for env in stored:
            env_str = self._normalize_path(str(env))
            if env_str and env_str not in envs:
                envs.append(env_str)
        normalized_fname = self._normalize_path(self.params.fname) if self.params.fname else ""
        if normalized_fname and Path(normalized_fname).is_file() and normalized_fname not in envs:
            envs.insert(0, normalized_fname)
        return envs[:10]

    def _calc_max_path_chars(self) -> int:
        """Calculate max characters that fit in the combo box based on its current width."""
        combo_width = self.env_history_combo.width()
        # Account for dropdown button and padding (approximately 40 pixels)
        available_width = combo_width - 40
        if available_width <= 0:
            return 60  # Default fallback
        # Use font metrics to estimate characters that fit
        fm = QFontMetrics(self.env_history_combo.font())
        avg_char_width = fm.averageCharWidth()
        if avg_char_width <= 0:
            return 60
        return max(20, available_width // avg_char_width)

    def _populate_env_combo(self):
        """Populate the combo box with shortened display text and full path as data."""
        current_index = self.env_history_combo.currentIndex()
        max_chars = self._calc_max_path_chars()
        self.env_history_combo.blockSignals(True)
        self.env_history_combo.clear()
        for env_path in self.recent_envs:
            self.env_history_combo.addItem(shorten_path(env_path, max_chars), env_path)
        if current_index >= 0 and current_index < self.env_history_combo.count():
            self.env_history_combo.setCurrentIndex(current_index)
        self.env_history_combo.blockSignals(False)

    def _set_env_from_history(self, full_path: str):
        full_path = self._normalize_path(full_path)
        self.env_history_combo.blockSignals(True)
        if full_path:
            # Find by item data (full path)
            for i in range(self.env_history_combo.count()):
                if self.env_history_combo.itemData(i) == full_path:
                    self.env_history_combo.setCurrentIndex(i)
                    break
        self.env_history_combo.blockSignals(False)
        self.params["fname"] = full_path
        self._update_env_style(full_path)
        self._update_env_tooltip(full_path)

    def _env_selected(self, display_text: str):
        # Get the full path from item data
        full_path = self._normalize_path(self.env_history_combo.currentData() or "")
        self.params["fname"] = full_path
        self._update_env_style(full_path)
        self._update_env_tooltip(full_path)

    def _add_recent_env(self, env_path: str):
        env_path = self._normalize_path(env_path)
        if not env_path:
            return
        envs = [env_path] + [env for env in self.recent_envs if env != env_path]
        self.recent_envs = envs[:10]
        self._populate_env_combo()
        self._set_env_from_history(env_path)

    def _update_env_tooltip(self, full_path: str):
        """Update the combo box tooltip to show the full path."""
        self.env_history_combo.setToolTip(full_path if full_path else "Recently used GEMS environment files")

    def _persist_recent_envs(self):
        self.settings.setValue("recent_env_paths", self.recent_envs)

    def _update_env_style(self, env_path: str):
        is_valid = bool(env_path and Path(env_path).is_file())
        self._env_valid = is_valid
        self.env_history_combo.setStyleSheet(NORMAL if is_valid else ERROR)

    def resizeEvent(self, event: QResizeEvent):
        """Update path display when dialog is resized."""
        super().resizeEvent(event)
        # Refresh combo box display with new width-appropriate shortening
        self._populate_env_combo()
