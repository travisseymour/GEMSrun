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

from munch import Munch
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QComboBox, QDialog, QFileDialog, QMessageBox

from gemsrun.gui.paramdialog import Ui_paramDialog

ERROR = "background : red;"
NORMAL = ""


# {'fname': 'myenvironment.yaml', 'user': 'User1', 'skipdata': True, 'overwrite': True,
# 'debug': None, 'skipmedia': None, 'skipgui': None}


class ParamDialog(QDialog):
    def __init__(self, params: Munch):
        super().__init__()
        self.ok = False
        self.ui = Ui_paramDialog()
        self.ui.setupUi(self)
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
        self.env_history_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.env_history_combo.setInsertPolicy(QComboBox.NoInsert)
        self.env_history_combo.setToolTip("Recently used GEMS environment files")
        self.env_history_combo.addItems(self.recent_envs)
        self.env_history_combo.currentTextChanged.connect(self._env_selected)
        self.ui.horizontalLayout_4.insertWidget(2, self.env_history_combo)

        # Enter orig values into each widget

        self._set_env_from_history(self.params.fname)
        self.ui.userLineEdit.setText(self.params.user)
        self.ui.skipdataCheckBox.setChecked(self.params.skipdata)
        self.ui.overwriteCheckBox.setChecked(self.params.overwrite)
        self.ui.debugCheckBox.setChecked(self.params.debug)
        self.ui.skipmediaCheckBox.setChecked(self.params.skipmedia)
        self.ui.fullscreenCheckBox.setChecked(self.params.fullscreen)

        # setup buttons
        self.ui.cancelPushButton.clicked.connect(self.quit)
        self.ui.startPushButton.clicked.connect(self.start)
        self.ui.toolButton.clicked.connect(self.load_envfile)

    def check_changing(self, key: str, state: bool):
        self.params[key] = bool(state)

    def text_changing(self, widget, key: str, content: str):
        # highlight bad data
        widget.setStyleSheet(NORMAL if content else ERROR)
        # update data
        if widget == self.ui.envLineEdit:
            if not Path(content.strip()).is_file():
                self.ui.envLineEdit.setStyleSheet(ERROR)
            else:
                self.ui.envLineEdit.setStyleSheet(NORMAL)
            self.params[key] = content.strip()
        elif widget == self.ui.userLineEdit:
            if not content.strip():
                self.ui.userLineEdit.setStyleSheet(ERROR)
            else:
                self.ui.userLineEdit.setStyleSheet(NORMAL)
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
        validated_widgets = (self.env_history_combo, self.ui.userLineEdit)
        if any(widget.styleSheet() == ERROR for widget in validated_widgets):
            QMessageBox.warning(
                self,
                "Validation Alert",
                "Please fill in missing or invalid information (red background) before pressing START "
                "(or you can press CANCEL).",
                QMessageBox.StandardButton.Ok,
            )

            return

        # self.settings.value("environment_file", defaultValue="")
        # self.settings.setValue()

        self._add_recent_env(self.params.fname)
        self._persist_recent_envs()
        self.ok = True
        self.close()

    def _load_recent_envs(self) -> list[str]:
        stored = self.settings.value("recent_env_paths", defaultValue=[], type=list)
        if stored is None:
            stored = []
        if isinstance(stored, str):
            stored = [stored]
        envs = []
        for env in stored:
            env_str = str(env).strip()
            if env_str and env_str not in envs:
                envs.append(env_str)
        if self.params.fname and Path(self.params.fname).is_file() and self.params.fname not in envs:
            envs.insert(0, self.params.fname)
        return envs[:10]

    def _set_env_from_history(self, text: str):
        self.env_history_combo.blockSignals(True)
        if text:
            index = self.env_history_combo.findText(text)
            if index >= 0:
                self.env_history_combo.setCurrentIndex(index)
        self.env_history_combo.blockSignals(False)
        self.params["fname"] = text
        self._update_env_style(text)

    def _env_selected(self, env_path: str):
        env_path = (env_path or "").strip()
        self.params["fname"] = env_path
        self._update_env_style(env_path)
        if env_path and self.env_history_combo.findText(env_path) == -1:
            self.env_history_combo.addItem(env_path)

    def _add_recent_env(self, env_path: str):
        env_path = str(env_path).strip()
        if not env_path:
            return
        envs = [env_path] + [env for env in self.recent_envs if env != env_path]
        self.recent_envs = envs[:10]
        self.env_history_combo.blockSignals(True)
        self.env_history_combo.clear()
        self.env_history_combo.addItems(self.recent_envs)
        self.env_history_combo.blockSignals(False)
        self._set_env_from_history(env_path)

    def _persist_recent_envs(self):
        self.settings.setValue("recent_env_paths", self.recent_envs)

    def _update_env_style(self, env_path: str):
        if env_path and Path(env_path).is_file():
            self.env_history_combo.setStyleSheet(NORMAL)
        else:
            self.env_history_combo.setStyleSheet(ERROR)
