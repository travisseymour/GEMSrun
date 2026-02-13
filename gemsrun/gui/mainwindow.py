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

import contextlib
import timeit

from munch import Munch
from PySide6.QtCore import QRect, QSize, Qt, QTimer
from PySide6.QtGui import QCloseEvent, QKeyEvent, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

import gemsrun
from gemsrun import log
from gemsrun.gui.infowindow import InfoDialog
from gemsrun.gui.viewpanel import ViewPanel
from gemsrun.gui.viewpanelobjects import ViewPocketObject

_TRANSITION_MAP = {
    "none": None,
    "fade": "dissolve",
    "dissolve": "dissolve",
    "wipe-left": "wipe-left",
    "wipe-right": "wipe-right",
}


class MainWin(QMainWindow):
    def __init__(self, db: Munch):
        super().__init__(None)
        self.db = db
        self.options = db.Global.Options
        self.current_view_id: int = self.options.Startview
        self.next_view_id: int = -1
        self.view_window: ViewPanel | None = None
        self.pocket_objects: dict[int, ViewPocketObject] | None = None
        self.note_window = None
        self._transition_overlay: QLabel | None = None
        self._transition_clip = None
        self._before_pixmap: QPixmap | None = None
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

        if (
            self.options.DisplayType.lower() not in ("maximized", "fullscreen")
            and self.db.Global.Options.Debug
        ):
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
                self.setStyleSheet(
                    "QMainWindow{" + f"background-color:rgba({r},{g},{b},{a});" + "}"
                )
        except Exception as e:
            log.warning(f"Unable to set stage color: ({e})")

    def load_next_view(self):
        log.debug(f"Loading Next View #{self.current_view_id}")
        self.view_window: ViewPanel = ViewPanel(
            parent=self, view_id=self.current_view_id
        )
        # self.setCentralWidget(self.view_window)

    def shutdown_view(self):
        log.debug(f"Shutting Down Existing View #{self.current_view_id}")
        has_pending_transition = self._before_pixmap is not None

        if self.view_window:
            self.view_window.close()

        if self.next_view_id >= 0:
            log.debug(f"Starting Next View #{self.next_view_id}")
            self.current_view_id = self.next_view_id
            self.next_view_id = -1
            self.load_next_view()
            if has_pending_transition and self.view_window:
                # Re-raise overlay — new ViewPanel's show() pushed it underneath
                if self._transition_overlay:
                    self._transition_overlay.raise_()
                self._start_transition_after_render()
        else:
            self._before_pixmap = None
            log.debug("Shutting Down Environment!")
            self.close()

    def _resolve_transition(self) -> str | None:
        """Return the transition_clip name, or None for instant switch."""
        duration = int(getattr(self.options, "TransitionDuration", 400))
        if duration <= 0:
            return None
        raw = getattr(self.options, "Roomtransition", "None") or "None"
        result = _TRANSITION_MAP.get(raw.strip().lower())
        if result is None and raw.strip().lower() != "none":
            log.warning(
                f'Unrecognized Roomtransition value "{raw}", defaulting to no transition.'
            )
        return result

    def prepare_transition(self, before_pixmap: QPixmap):
        """Store a screenshot and show overlay immediately to prevent flash."""
        # Cancel any in-progress transition
        if self._transition_clip:
            self._transition_clip.stop()
        if self._transition_overlay:
            self._transition_overlay.hide()
            self._transition_overlay.deleteLater()
            self._transition_overlay = None
            self._transition_clip = None

        self._before_pixmap = before_pixmap

        # Create overlay NOW so it covers the view switch
        overlay = QLabel(self)
        overlay.setGeometry(0, 0, self.width(), self.height())
        overlay.setStyleSheet("background-color: black;")
        overlay.setScaledContents(True)
        overlay.setPixmap(before_pixmap)
        overlay.show()
        overlay.raise_()
        self._transition_overlay = overlay

    def _start_transition_after_render(self):
        """Defer transition playback until the new view is fully painted."""
        QApplication.processEvents()
        if self._transition_overlay:
            self._transition_overlay.raise_()
        QTimer.singleShot(50, self._play_room_transition)

    def _play_room_transition(self):
        """Capture the after-pixmap and play the room transition."""
        from gemsrun.gui.transition_clip import make_transition

        before_pixmap = self._before_pixmap
        self._before_pixmap = None

        if (
            before_pixmap is None
            or not self.view_window
            or not self._transition_overlay
        ):
            return

        transition_name = self._resolve_transition()
        if not transition_name:
            if self._transition_overlay:
                self._transition_overlay.hide()
                self._transition_overlay.deleteLater()
                self._transition_overlay = None
            return

        after_pixmap = self.view_window.grab()

        duration_ms = max(
            100, min(2000, int(getattr(self.options, "TransitionDuration", 400)))
        )

        overlay = self._transition_overlay
        overlay.raise_()

        log.debug(f"Playing room transition: {transition_name} ({duration_ms}ms)")

        clip = make_transition(
            before_pixmap, after_pixmap, transition_name, duration_ms
        )

        clip.frameChanged.connect(overlay.setPixmap)

        def on_transition_finished():
            clip.stop()
            overlay.hide()
            overlay.deleteLater()
            self._transition_overlay = None
            self._transition_clip = None

        clip.finished.connect(on_transition_finished)

        self._transition_clip = clip
        clip.start(loop=False)

    def task_elapsed(self):
        return timeit.default_timer() - self.task_start_time

    def update_notes(self, text: str):
        if self.note_window:
            self.note_window.notes.SetLabel(text)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._transition_clip:
            self._transition_clip.stop()
            self._transition_clip = None
        if self._transition_overlay:
            self._transition_overlay.hide()
            self._transition_overlay = None
        with contextlib.suppress(Exception):
            self.info_window.close()
        event.accept()

    @classmethod
    def get_key_modifiers(cls):
        """
        Helper to return string version of current keyboard modifier buttons being pressed
        """
        q_modifiers = QApplication.keyboardModifiers()
        modifiers = []
        if (
            q_modifiers & Qt.KeyboardModifier.ShiftModifier
        ) == Qt.KeyboardModifier.ShiftModifier:
            modifiers.append("shift")
        if (
            q_modifiers & Qt.KeyboardModifier.ControlModifier
        ) == Qt.KeyboardModifier.ControlModifier:
            modifiers.append("control")
        if (
            q_modifiers & Qt.KeyboardModifier.AltModifier
        ) == Qt.KeyboardModifier.AltModifier:
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
