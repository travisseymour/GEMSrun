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

from PySide6.QtCore import QSettings

from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

from gemsrun.gui.paramdialog import Ui_paramDialog
from munch import Munch
from pathlib import Path
from functools import partial

ERROR = "background : red;"
NORMAL = ""


# {'fname': 'myenvironment.yaml', 'user': 'User1', 'skipdata': True, 'overwrite': True,
# 'debug': None, 'skipmedia': None, 'skipgui': None}


class ParamDialog(QDialog):
    def __init__(self, params: Munch):
        super(ParamDialog, self).__init__()
        self.ok = False
        self.ui = Ui_paramDialog()
        self.ui.setupUi(self)
        self.params = params

        self.settings = QSettings()

        # load icon
        # pixmap = QtGui.QPixmap(get_resource('images', 'Icon.ico'))
        # self.ui.labelIcon.setPixmap(pixmap)

        # setup initial validations for text fields

        self.ui.envLineEdit.setStyleSheet(ERROR if not self.ui.envLineEdit.text() else NORMAL)
        self.ui.userLineEdit.setStyleSheet(ERROR if not self.ui.userLineEdit.text() else NORMAL)

        # create change handlers for text fields

        self.ui.envLineEdit.textChanged.connect(partial(self.text_changing, self.ui.envLineEdit, "fname"))
        self.ui.userLineEdit.textChanged.connect(partial(self.text_changing, self.ui.userLineEdit, "user"))

        # create change handlers for checkboxes

        self.ui.skipdataCheckBox.stateChanged.connect(partial(self.check_changing, "skipdata"))
        self.ui.overwriteCheckBox.stateChanged.connect(partial(self.check_changing, "overwrite"))
        self.ui.debugCheckBox.stateChanged.connect(partial(self.check_changing, "debug"))
        self.ui.skipmediaCheckBox.stateChanged.connect(partial(self.check_changing, "skipmedia"))
        self.ui.fullscreenCheckBox.stateChanged.connect(partial(self.check_changing, "fullscreen"))

        # Enter orig values into each widget

        self.ui.envLineEdit.setText(self.params.fname)
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
        widget.setStyleSheet(ERROR if not content else NORMAL)
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
            self.ui.envLineEdit.setText(file_name)

    def quit(self):
        self.ok = False
        self.close()

    def start(self):
        validated_widgets = (self.ui.envLineEdit, self.ui.userLineEdit)
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

        self.ok = True
        self.close()
