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

from typing import Optional, Dict

from PySide6.QtWidgets import QMainWindow, QApplication
from PySide6.QtCore import QSize, QRect, Qt
from PySide6.QtGui import QCloseEvent, QKeyEvent

import gemsrun
from gemsrun.gui.viewpanel import ViewPanel
from munch import Munch
from gemsrun.gui.infowindow import InfoDialog
import timeit
from gemsrun import log

from gemsrun.gui.viewpanelobjects import ViewPocketObject


class MainWin(QMainWindow):
    def __init__(self, db: Munch):
        super(MainWin, self).__init__(None)
        self.db = db
        self.options = db.Global.Options
        self.current_view_id: int = self.options.Startview
        self.next_view_id: int = -1
        self.view_window: Optional[ViewPanel] = None
        self.pocket_objects: Optional[Dict[int, ViewPocketObject]] = None
        self.note_window = None
        self.setWindowTitle(db.Name)

        # Center
        if self.options.DisplayType.lower() not in ("maximized", "fullscreen"):
            # if here, DisplayType is likely 'Windowed'
            self.setFixedSize(QSize(*self.options.EnvDims))
            screen_size = gemsrun.APPLICATION.primaryScreen().size()
            self.setGeometry(
                QRect(
                    screen_size.width() // 2 - self.width() // 2,
                    screen_size.height() // 2 - self.height() // 2,
                    self.width(),
                    self.height(),
                )
            )

        self.InitUI()

        if self.options.DisplayType.lower() not in ("maximized", "fullscreen") and self.db.Global.Options.Debug:
            self.info_window = InfoDialog(self, db)
            self.info_window.move(10, 10)
            self.info_window.hide()

        self.task_start_time = timeit.default_timer()

        self.load_next_view()

    def InitUI(self):
        # adjust window size so env images FULLY fit within client area!
        # TODO: work on this later -- solution in PySide6 may be much simpler!
        # width, height = self.GetSize()
        # rect = self.GetRect()
        # client_x, client_y = self.ClientToScreen((0, 0))
        # border_width = client_x - rect.x
        # title_bar_height = client_y - rect.y
        # new_width = width + (border_width * 2)
        # new_height = height + (border_width * 2) + title_bar_height
        # self.SetSize(wx.Size(width=new_width, height=new_height))

        self.setStyleSheet("QMainWindow{background:black;}")
        try:
            stage_color = str(self.options.StageColor).strip()
            if stage_color[0] + stage_color[-1] == "[]":
                # going in reverse in case color name is not 1st value.
                # no matter what, expect last 4 values of list to be integers for rgba
                stage_color = list(reversed(eval(stage_color)))
                a, b, g, r, *other = stage_color
                self.setStyleSheet("QMainWindow{" + f"background-color:rgba({r},{g},{b},{a});" + "}")
        except Exception as e:
            log.warning(f"Unable to set stage color: ({e})")

    def load_next_view(self):
        log.debug(f"Loading Next View #{self.current_view_id}")
        self.view_window = ViewPanel(parent=self, view_id=self.current_view_id)
        # self.setCentralWidget(self.view_window)

    def shutdown_view(self):
        log.debug(f"Shutting Down Existing View #{self.current_view_id}")
        if self.view_window:
            self.view_window.close()

        if self.next_view_id >= 0:
            log.debug(f"Starting Next View #{self.next_view_id}")
            self.current_view_id = self.next_view_id
            self.next_view_id = -1
            self.load_next_view()
        else:
            log.debug("Shutting Down Environment!")
            self.close()

    def task_elapsed(self):
        return timeit.default_timer() - self.task_start_time

    def update_notes(self, text: str):
        if self.note_window:
            self.note_window.notes.SetLabel(text)

    def closeEvent(self, event: QCloseEvent) -> None:
        try:
            self.info_window.close()
        except:
            pass

        event.accept()

    @classmethod
    def get_key_modifiers(cls):
        """
        Helper to return string version of current keyboard modifier buttons being pressed
        """
        QModifiers = QApplication.keyboardModifiers()
        modifiers = []
        if (QModifiers & Qt.KeyboardModifier.ShiftModifier) == Qt.KeyboardModifier.ShiftModifier:
            modifiers.append("shift")
        if (QModifiers & Qt.KeyboardModifier.ControlModifier) == Qt.KeyboardModifier.ControlModifier:
            modifiers.append("control")
        if (QModifiers & Qt.KeyboardModifier.AltModifier) == Qt.KeyboardModifier.AltModifier:
            modifiers.append("alt")
        return tuple(modifiers)

    def keyPressEvent(self, keycode: QKeyEvent) -> None:
        if keycode.key() == Qt.Key.Key_X and keycode.modifiers() == (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        ):
            # User wants to manually quit
            log.info(
                dict(
                    Kind="UserQuitCtrlShiftX",
                    Type="User",
                    View=self.view_window.View.Name if self.view_window else "NA",
                    TimeTime=self.task_elapsed(),
                    ViewTime=self.view_window.view_elapsed(),
                )
            )
            self.close()
        elif keycode.key() == Qt.Key.Key_I and keycode.modifiers() == (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        ):
            log.debug("INFO WINDOW")
            try:
                if self.info_window.isHidden():
                    self.info_window.show()
                else:
                    self.info_window.hide()
            except AttributeError:
                ...
        else:
            if self.view_window:
                self.view_window.handle_key_press(key_code=keycode)
            keycode.accept()
