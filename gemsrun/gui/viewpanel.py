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

from __future__ import annotations

from functools import lru_cache, partial
from itertools import chain
from pathlib import Path
import re
import string
import subprocess
import sys
import tempfile
import textwrap
import timeit
from typing import TYPE_CHECKING
import webbrowser

from gtts import gTTS
from munch import Munch
from PySide6.QtCore import QEventLoop, QPoint, QRect, Qt, QTimer
from PySide6.QtGui import (
    QCloseEvent,
    QCursor,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QImage,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import QInputDialog, QLabel, QMessageBox, QWidget

import gemsrun
from gemsrun import log
from gemsrun.gui import uiutils
from gemsrun.gui.viewpanelobjects import (
    AnimationObject,
    ExternalImageObject,
    NavImageObject,
    TextBoxObject,
    VideoObject,
    ViewImageObject,
    ViewPocketObject,
)
from gemsrun.gui.viewpanelutils import get_custom_cursors
from gemsrun.utils import audiocache, audioutils, gemsutils as gu
from gemsrun.utils.apputils import get_resource
from gemsrun.utils.safestrfunc import func_str_parts, get_param, is_safe_value

if TYPE_CHECKING:  # Avoid circular import at runtime
    from .mainwindow import MainWin

VALID_CONDITIONS = [
    "VarValueIs",
    "VarValueIsNot",
    "VarExists",
    "VarMissing",
    "VarCountEq",
    "VarCountGtEq",
    "VarCountLtEq",
    "KeyBufferContains",
    "KeyBufferContainsIgnoreCase",
    "KeyBufferLacks",
    "HasViewTimePassed",
    "HasTotalTimePassed",
]
VALID_TRIGGERS = ["ViewTimePassed", "TotalTimePassed"]
VALID_ACTIONS = [
    "SetVariable",
    "DelVariable",
    "VarIncrease",
    "VarDecrease",
    "ClearKeyBuffer",
    "TextBox",
    "ShowObject",
    "HideObject",
    "PortalTo",
    "ShowImage",
    "ShowImageWithin",
    "PlaySound",
    "StopSound",
    "StopAllSounds",
    "PlayBackgroundMusic",
    "StopBackgroundMusic",
    "PlayVideo",
    "PlayVideoWithin",
    "StopVideo",
    "StopAllVideos",
    "AllowTake",
    "DisallowTake",
    "TextDialog",
    "InputDialog",
    "SayText",
    "ShowURL",
    "Quit",
    "HideMouse",
    "ShowMouse",
    "HidePockets",
    "ShowPockets",
    "NavRight",
    "NavLeft",
    "NavTop",
    "NavBottom",
    "TextBoxHTML",
    "RunProgram",
    "ChangeViewImages",
]


class SoundPlayer:
    def __init__(self, sound_file: str, volume: int = 50, loop=False):
        self._sound_file = sound_file
        self._volume = volume / 100.0  # Convert to 0-1 range
        self._loop = loop
        self._player = None

        # Import the cross-platform audio player
        from gemsrun.utils.audioutils import CrossPlatformAudioPlayer

        try:
            self._player = CrossPlatformAudioPlayer(
                sound_file=sound_file, volume=self._volume, loop=loop
            )
            log.debug(f"Created cross-platform audio player for {sound_file}")
        except Exception as e:
            log.error(f"Failed to create audio player: {e}")
            self._player = None

    def play(self):
        if self._player:
            try:
                success = self._player.play()
                if not success:
                    log.warning(f"Audio playback failed for {self._sound_file}")
            except Exception as e:
                log.error(f"Error playing audio: {e}")
        else:
            log.error("No audio player available")

    def stop(self):
        if self._player:
            try:
                self._player.stop()
            except Exception as e:
                log.error(f"Error stopping audio: {e}")

    def duration(self) -> int:
        if self._player:
            try:
                return self._player.duration()
            except Exception as e:
                log.error(f"Error getting duration: {e}")
        return 0

    def is_playing(self) -> bool:
        if self._player:
            try:
                return self._player.is_playing()
            except Exception as e:
                log.error(f"Error checking playing state: {e}")
        return False

    def handle_position_changed(self, position):
        # This method is kept for compatibility but may not be used
        # depending on the audio backend
        pass


@lru_cache
def geom_x_adjust(value: int | float, scale_x: float) -> int:
    return int(value * scale_x)


@lru_cache
def geom_y_adjust(value: int | float, scale_y: float) -> int:
    return int(value * scale_y)


class ViewPanel(QWidget):
    _nav_panel_cache: dict[str, QImage] = {}
    _nav_generation_cache: set[tuple[str, int, int, int]] = set()
    _pocket_bitmap_cache: dict[tuple[str, int, int], QImage] = {}

    def __init__(self, parent: MainWin, view_id: int):
        super().__init__(parent=parent)

        self.db: Munch = parent.db
        self.options: Munch = self.db.Global.Options
        self.view_id: int = view_id
        self.View: Munch | None = None
        self.background = QLabel(self)  # QLabel that holds the background image
        self.foreground_image: QImage | None = (
            None  # is a QImage, we'll get object images from it
        )
        self.nav_image: QImage | None = None
        self.pocket_bitmap: QImage | None = None
        self.view_is_fullscreen = self.options.DisplayType.lower() == "fullscreen"

        self.sleep_event_loop = (
            QEventLoop()
        )  # useful for synchronous GEMS actions -- blocks ui until done.

        # holders for various view objects
        self.object_pics: dict[int, ViewImageObject] = {}  # indexed by obj number
        self.overlay_pics = {}  # indexed by overlay filename stem
        self.external_pics = {}  # indexed by pic filename stem
        self.nav_pics = (
            {}
        )  # indexed by direction name (i.e., NavTop, NavLeft, NavBottom, NavRight)
        self.sound_controls = {}  # indexed by filename stem
        self.video_controls = {}  # indexed by filename stem
        self.text_boxes = {}  # indexed by hash

        self.nav_extent: int = 40

        self.hover_object = None

        self.dragging = False  # True if we're currently in a drag
        self.dragging_icon = None
        self.dragging_object = None  # Object we're currently dragging from
        self.drag_object_bitmap = (
            None  # Hold drag object bitmap whilst dragging..avoids re-lookup
        )
        self.draw_pos = QPoint(0, 0)

        self.setAcceptDrops(True)  # allow drops to nothing
        cursors = get_custom_cursors()
        self.arrow_cursor = cursors.get("arrow")
        if self.arrow_cursor:
            self.setCursor(self.arrow_cursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

        screen = gemsrun.APPLICATION.primaryScreen()
        self.screen_rect = screen.availableGeometry()
        self.orig_image_rect: QRect = (
            self.screen_rect
        )  # temp, until first bg image is loaded
        self.background_scale: list[float] = [
            1.0,
            1.0,
        ]  # temp, until self.view_image_rect is determined
        self.view_top_left_adjustment: list[int] = [
            0,
            0,
        ]  # temp, until self.background is potentially scaled

        self.init_ui()

        # Preload compressed audio for this view if Preloadresources is False
        # (If True, audio was already preloaded at app start)
        if not self.options.Preloadresources:
            self._preload_view_audio_with_overlay()

        self.view_start_time: float = timeit.default_timer()
        self.key_buffer: str = ""

        # Defer start_timers to allow GUI to render first
        QTimer.singleShot(0, self.start_timers)

        # Z-Order = bg, object, external, pocket, overlay, nav

        self.create_object_pics()

        if self.parent().pocket_objects:
            self.reload_pockets()
        else:
            self.create_pockets()

        self.load_overlays()

        self.create_nav_pics()

        self.reset_z_pos()

        self.show()

    def _set_parent_geometry(self, x, y, width, height):
        def apply_geometry():
            self.parent().setGeometry(x, y, width, height)
            for pocket in (self.parent().pocket_objects or {}).values():
                pocket.position_pockets()

        if int(self.view_id) == int(self.options.Startview):
            QTimer.singleShot(500, self, apply_geometry)
        else:
            apply_geometry()

    def _preload_view_audio_with_overlay(self):
        """Preload compressed audio files for this view with a loading overlay."""
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtWidgets import QFrame

        # Find audio files for this view
        audio_files = audiocache.find_playsound_files_for_view(
            self.db, self.view_id, self.options.MediaPath
        )

        if not audio_files:
            return  # Nothing to preload

        # Parse StageColor from options (format: "['Black',0,0,0,255]" or similar)
        stage_color = "black"
        try:
            if hasattr(self.options, "StageColor") and self.options.StageColor:
                # StageColor format: "['ColorName',r,g,b,a]"
                import ast

                color_data = ast.literal_eval(self.options.StageColor)
                if len(color_data) >= 4:
                    r, g, b = color_data[1], color_data[2], color_data[3]
                    stage_color = f"rgb({r},{g},{b})"
        except Exception:
            pass  # Use default black

        # Create loading overlay
        overlay = QFrame(self)
        overlay.setStyleSheet(f"background-color: {stage_color};")
        overlay.setGeometry(0, 0, self.width() or 800, self.height() or 600)

        # Create loading label (black text on silver background)
        loading_label = QLabel("Loading...", overlay)
        loading_label.setStyleSheet(
            "background-color: rgb(192, 192, 192); "
            "color: black; "
            "padding: 10px 20px; "
            "font-size: 16px; "
            "font-weight: bold;"
        )
        loading_label.move(10, 10)
        loading_label.adjustSize()

        overlay.show()
        overlay.raise_()
        QCoreApplication.processEvents()

        # Preload each audio file
        for i, file_path in enumerate(audio_files):
            loading_label.setText(f"Loading audio ({i + 1}/{len(audio_files)})...")
            loading_label.adjustSize()
            QCoreApplication.processEvents()

            audiocache.ensure_cached(file_path)

        # Remove overlay
        overlay.hide()
        overlay.deleteLater()

    def geom_x_adjust(self, value: int | float) -> int:
        return self.view_top_left_adjustment[0] + geom_x_adjust(
            value, self.background_scale[0]
        )

    def geom_y_adjust(self, value: int | float) -> int:
        return self.view_top_left_adjustment[1] + geom_y_adjust(
            value, self.background_scale[1]
        )

    def geom_x_scale(self, value: int | float) -> int:
        return geom_x_adjust(value, self.background_scale[0])

    def geom_y_scale(self, value: int | float) -> int:
        return geom_y_adjust(value, self.background_scale[1])

    def fail_dialog(self, caption: str, message: str):
        QMessageBox.critical(self, caption, message, QMessageBox.StandardButton.Ok)
        self.parent().close()

    def _resolve_env_asset(self, filename: str) -> Path:
        """
        Return a Path to an asset, preferring the current environment media folder,
        otherwise falling back to packaged resources.
        """
        media_candidate = Path(self.options.MediaPath, filename)
        if media_candidate.is_file():
            return media_candidate.resolve()
        try:
            return get_resource("images", filename)
        except Exception as e:  # pragma: no cover - catastrophic missing resource
            log.critical(f"Missing required asset '{filename}': {e}")
            raise

    def sleep(self, msec: int):
        """
        A pyqt friendly version of time.sleep()
        There can be only one. Uses global sleep_event_loop and quits existing before starting a new loop.
        :param msec: int time in ms
        :return: None
        """
        if self.sleep_event_loop.isRunning():
            self.sleep_event_loop.quit()
        QTimer.singleShot(msec, self, self.sleep_event_loop.quit)
        self.sleep_event_loop.exec()

    @classmethod
    def _nav_cache_key(
        cls, nav_panel: Path, width: int, height: int, nav_extent: int
    ) -> tuple[str, int, int, int]:
        return (str(nav_panel.resolve()), width, height, nav_extent)

    @classmethod
    def _get_nav_panel_image(cls, nav_panel: Path) -> QImage:
        key = str(nav_panel.resolve())
        if key not in cls._nav_panel_cache:
            cls._nav_panel_cache[key] = QImage(str(nav_panel))
        return cls._nav_panel_cache[key]

    @classmethod
    def _get_pocket_bitmap(
        cls, pocket_pic: Path, stage_width: int, stage_height: int
    ) -> QImage:
        cache_key = (str(pocket_pic.resolve()), stage_width, stage_height)
        if cache_key in cls._pocket_bitmap_cache:
            return cls._pocket_bitmap_cache[cache_key]

        pocket_bitmap = QImage(str(pocket_pic))
        try:
            max_pocket_w = max(50, int(stage_width * 0.25))
            max_pocket_h = max(50, int(stage_height * 0.25))
            if (
                pocket_bitmap.width() > max_pocket_w
                or pocket_bitmap.height() > max_pocket_h
            ):
                pocket_bitmap = pocket_bitmap.scaled(
                    max_pocket_w,
                    max_pocket_h,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
        except Exception:
            ...

        cls._pocket_bitmap_cache[cache_key] = pocket_bitmap
        return pocket_bitmap

    def init_ui(self):
        # color the stage using the value in options
        self.setStyleSheet("{background:black}")
        try:
            stage_color = str(self.options.StageColor).strip()
            if stage_color[0] + stage_color[-1] == "[]":
                # going in reverse in case color name is not 1st value.
                # no matter what, expect last 4 values of list to be integers for rgba
                stage_color = list(reversed(eval(stage_color)))
                a, b, g, r, *other = stage_color
                self.setStyleSheet(
                    "QWidget{" + f"background-color:rgba({r},{g},{b},{a});" + "}"
                )
        except Exception as e:
            log.warning(f"Unable to set stage color: ({e})")

        # grab info about the current view and store it locally (assuming it exists)
        try:
            self.View = self.db.Views[str(self.view_id)]
        except KeyError:
            log.critical(f"Unable to find view #{self.view_id} in environment db!")
            self.fail_dialog(
                "Unrecoverable Error",
                f"Unable to find view #{self.view_id} in environment db!",
            )

        # set the current view background image as the form background
        bg_path = Path(self.options.MediaPath, self.View.Background)
        try:
            if not bg_path.is_file():
                raise FileNotFoundError
            display_type = self.options.DisplayType.lower()
            stage_width: int
            stage_height: int

            if display_type in ("maximized", "fullscreen"):
                available_geom = (
                    gemsrun.APPLICATION.primaryScreen().geometry()
                    if display_type == "fullscreen"
                    else gemsrun.APPLICATION.primaryScreen().availableGeometry()
                )
                stage_width, stage_height = (
                    available_geom.width(),
                    available_geom.height(),
                )
                available_top_left = available_geom.topLeft()
                self._set_parent_geometry(
                    available_top_left.x(),
                    available_top_left.y(),
                    stage_width,
                    stage_height,
                )
            else:
                # Use the size of the Start View (EnvDims) for all other views in windowed mode
                try:
                    stage_width, stage_height = (
                        int(self.options.EnvDims[0]),
                        int(self.options.EnvDims[1]),
                    )
                except Exception:
                    stage_width, stage_height = (
                        self.screen_rect.width(),
                        self.screen_rect.height(),
                    )

            # Always size the view panel to the chosen stage size; individual images are letterboxed within.
            self.setGeometry(0, 0, stage_width, stage_height)

            pixmap = QPixmap.fromImage(QImage(str(bg_path.resolve())))
            self.orig_image_rect = pixmap.rect()  # save rect of unaltered bg_image

            scale_factor = min(
                stage_width / self.orig_image_rect.width(),
                stage_height / self.orig_image_rect.height(),
            )
            scaled_width = int(self.orig_image_rect.width() * scale_factor)
            scaled_height = int(self.orig_image_rect.height() * scale_factor)

            self.background_scale = [scale_factor, scale_factor]

            self.view_top_left_adjustment = [
                max(0, (stage_width - scaled_width) // 2),
                max(0, (stage_height - scaled_height) // 2),
            ]

            pixmap = pixmap.scaled(
                scaled_width,
                scaled_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.background.setPixmap(pixmap)
            self.background.setGeometry(
                self.view_top_left_adjustment[0],
                self.view_top_left_adjustment[1],
                pixmap.width(),
                pixmap.height(),
            )

        except Exception as e:
            log.critical(
                f"Unable to load background image for view # {self.view_id}: {e}"
            )
            self.fail_dialog(
                "Unrecoverable Error",
                f"Unable to load background image ({str(bg_path)}) for view # {self.view_id}: {e}",
            )

        # obtain current foreground image
        fg_path = Path(self.options.MediaPath, self.View.Foreground)
        try:
            if not fg_path.is_file():
                raise FileNotFoundError
            fg_image = QImage(str(fg_path.resolve()))
            fg_image = fg_image.scaled(
                int(fg_image.width() * self.background_scale[0]),
                int(fg_image.height() * self.background_scale[1]),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

            staged_fg = QImage(
                self.width(),
                self.height(),
                QImage.Format.Format_ARGB32_Premultiplied,
            )
            staged_fg.fill(Qt.GlobalColor.transparent)

            painter = QPainter(staged_fg)
            painter.drawImage(
                self.view_top_left_adjustment[0],
                self.view_top_left_adjustment[1],
                fg_image,
            )
            painter.end()

            self.foreground_image = staged_fg
        except Exception as e:
            log.critical(
                f"Unable to load foreground image for view # {self.view_id}: {e}"
            )
            self.fail_dialog(
                "Unrecoverable Error",
                f"Unable to load foreground image ({str(bg_path)}) for view # {self.view_id}: {e}",
            )

        # either load custom nav panel image from env media folder, or use default one
        nav_panel = self._resolve_env_asset("nav_panel.png")
        self.nav_image = self._get_nav_panel_image(nav_panel)

        nav_cache_key = self._nav_cache_key(
            nav_panel=nav_panel,
            width=self.width(),
            height=self.height(),
            nav_extent=self.nav_extent,
        )

        if nav_cache_key not in self._nav_generation_cache:
            if result := uiutils.create_nav_pics(
                nav_panel_image=self.nav_image,
                temp_folder=self.options.TempFolder,
                view_width=self.width(),
                view_height=self.height(),
                nav_extent=self.nav_extent,
            ):
                self.fail_dialog("Problem Generating Nav Images From Panel", result)
            else:
                self._nav_generation_cache.add(nav_cache_key)

        # either load custom pocket image from env media folder, or use default one
        pocket_pic = self._resolve_env_asset("pocket.png")
        self.pocket_bitmap = self._get_pocket_bitmap(
            pocket_pic, self.width(), self.height()
        )

    def reset_z_pos(self):
        # maintain relative z-pos
        self.activateWindow()
        for object_set in (
            self.parent().pocket_objects,
            self.overlay_pics,
            self.nav_pics,
        ):
            for object_ in object_set.values():
                object_.raise_()

    def env_info(self):
        if self.db.Variables:
            _vars = "\n".join(
                [f"{key}={value}" for key, value in self.db.Variables.items()]
            )
        else:
            _vars = "None"
        text = f"------ VARIABLES ------\n{_vars}\n"
        return textwrap.dedent(text.strip())

    def load_overlays(self):
        """
        Draws both global and view-specific overlay images.
        Overlays are drawn from the upper right corner. There is currently no way to really position them.
        """
        overlay_files = (self.View.Overlay, self.db.Global.Options.Globaloverlay)
        for overlay_file in overlay_files:
            if not overlay_file:
                continue

            overlay_stem = Path(overlay_file).stem
            if overlay_stem in self.overlay_pics:
                # Avoid recreating the same overlay multiple times (can be triggered by repeated calls).
                continue

            try:
                overlay_path = Path(self.options.MediaPath, overlay_file).resolve()
                overlay = QPixmap(str(overlay_path))
                x_ratio, y_ratio = self.background_scale
                overlay = overlay.scaled(
                    int(overlay.width() * x_ratio),
                    int(overlay.height() * y_ratio),
                    Qt.AspectRatioMode.KeepAspectRatio,
                )
                label = QLabel(self)
                label.setPixmap(overlay)

                overlay_rect = QRect(
                    self.width() - overlay.width(),
                    0,
                    overlay.width(),
                    overlay.height(),
                )

                style_sheet = "QLabel{ " + "background-color: rgba(0,0,0,0%); }"
                # handle image transparency
                label.setStyleSheet(style_sheet)

                label.setGeometry(overlay_rect)
                self.overlay_pics[overlay_stem] = label
            except Exception as e:
                log.error(f"Unable to load overlay image {overlay_file}: {e}")

    # def eventFilter(self, watched, event):
    #     if event.type() == QEvent.MouseMove:
    #         if not self.geometry().contains(QCursor.pos()):
    #             QCursor.setPos(QPoint(QCursor.pos().x(), QCursor.pos().y()))
    #     return super().eventFilter(watched, event)

    def dragMoveEvent(self, ev: QDragMoveEvent) -> None:
        """
        Make sure user can't drag object outside view window (can escape if move is fast/wild enough).
        NOTE: If this isn't enough, try having drag start enable a 1 sec timer that checks
              QCurosr.pos() for x,y values outside of current view geometry.
        """

        if self.dragging:
            x, y = ev.position().x(), ev.position().y()
            x_offset, y_offset = self.view_top_left_adjustment
            g = self.rect()  # local coords
            buffer = 50

            bg_width = (
                self.background.pixmap().width()
                if self.background.pixmap()
                else g.width()
            )
            bg_height = (
                self.background.pixmap().height()
                if self.background.pixmap()
                else g.height()
            )

            # Constrain to the scaled image area inside the stage, not the whole stage
            min_x = x_offset + buffer
            max_x = x_offset + bg_width - buffer
            min_y = y_offset + buffer
            max_y = y_offset + bg_height - buffer

            nu_x = gu.boundary(min_x, x, max_x)
            nu_y = gu.boundary(min_y, y, max_y)

            if (x, y) != (nu_x, nu_y):
                global_pos = self.mapToGlobal(QPoint(int(nu_x), int(nu_y)))
                self.cursor().setPos(global_pos)

        ev.accept()

    def dragEnterEvent(self, ev: QDragEnterEvent) -> None:
        # NOTE: This code is essential, even though it doesn't look essential!
        #       So DON'T REMOVE THIS METHOD...even if the only code is ev.accept()!!
        self.dragging = True
        log.debug("dragging marked as started")
        ev.accept()

    def dragLeaveEvent(self, ev: QDragLeaveEvent) -> None:
        self.dragging = False
        log.debug("dragging marked as stopped")
        ev.accept()

    def dropEvent(self, ev: QDropEvent) -> None:
        log.debug(f'"{ev.mimeData().text()}" was dropped onto nothing in particular.')
        log.debug("dragging marked as stopped")

        log.info(
            dict(
                Kind="Mouse",
                Type="DragOntoNothing",
                View=self.View.Name,
                Source=(
                    self.dragging_object.object.Id
                    if hasattr(self.dragging_object, "object")
                    else "???"
                ),
                Result="Invalid|NoTarget",
                TimeTime=self.parent().task_elapsed(),
                ViewTime=self.view_elapsed(),
            )
        )

        self.dragging = False
        if self.dragging_object:
            self.dragging_object.show()
        self.dragging_object = None
        ev.accept()

    def create_object_pics(self):
        for _object in self.View.Objects.values():
            # object_rect = QRect(_object.Left, _object.Top, _object.Width, _object.Height)
            adjusted_object_rect = QRect(
                self.geom_x_adjust(_object.Left),
                self.geom_y_adjust(_object.Top),
                self.geom_x_scale(_object.Width),
                self.geom_y_scale(_object.Height),
            )
            pixmap = QPixmap.fromImage(self.foreground_image.copy(adjusted_object_rect))
            self.object_pics[_object.Id] = ViewImageObject(
                self, obj_id=_object.Id, pixmap=pixmap, scale=self.background_scale
            )
            self.object_pics[_object.Id].setGeometry(adjusted_object_rect)

    def make_action_timer(self, condition: str, action: str, when_secs: float):
        log.debug(
            f'SETTING A TIMER TO "{action}" in {when_secs * 1000} ms if condition "{condition}" is met.'
        )
        QTimer.singleShot(
            int(when_secs * 1000),
            self,
            partial(self.do_action, condition=condition, action=action),
        )

    def start_timers(self):
        """Launch timers for any view or env actions with timed triggers"""
        # first check any global timers
        for action in chain(
            self.db.Global.GlobalActions.values(), self.View.Actions.values()
        ):
            if not action.Enabled:
                continue
            # make sure action parts are valid and also get breakdown for each
            condition_info = self.valid_api_call(expression=action.Condition)
            trigger_info = self.valid_api_call(expression=action.Trigger)
            action_info = self.valid_api_call(expression=action.Action)
            if (
                trigger_info
                and action_info
                and (condition_info or not action.Condition)
            ):
                func, params = trigger_info
                if func == "TotalTimePassed":
                    log.debug("Handling TotalTimePassed Events:")
                    trigger_time_secs = float(params[0])
                    passed_so_far_secs = (
                        timeit.default_timer() - self.parent().task_start_time
                    )
                    if passed_so_far_secs >= trigger_time_secs:
                        # Defer to next event loop iteration to avoid blocking timer setup
                        self.make_action_timer(
                            condition=action.Condition,
                            action=action.Action,
                            when_secs=0,
                        )
                    else:
                        self.make_action_timer(
                            condition=action.Condition,
                            action=action.Action,
                            when_secs=trigger_time_secs - passed_so_far_secs,
                        )
                    # Once a global timed action fires, it is disabled.
                    if action in self.db.Global.GlobalActions.values():
                        self.db.Global.GlobalActions[str(action.Id)].Enabled = False
                elif func == "ViewTimePassed":
                    trigger_time_secs = float(params[0])
                    passed_so_far_secs = timeit.default_timer() - self.view_start_time
                    log.debug(
                        f"ViewTimePassed trigger: {trigger_time_secs}s, elapsed: {passed_so_far_secs:.3f}s, action: {action.Action}"
                    )
                    if passed_so_far_secs >= trigger_time_secs:
                        # Defer to next event loop iteration so we finish setting up ALL timers first.
                        # This prevents synchronous actions (like PlaySound with async=False) from
                        # blocking the rest of the timer setup.
                        log.debug("  -> Deferring immediate execution")
                        self.make_action_timer(
                            condition=action.Condition,
                            action=action.Action,
                            when_secs=0,
                        )
                    else:
                        delay = trigger_time_secs - passed_so_far_secs
                        log.debug(f"  -> Setting timer for {delay:.3f}s")
                        self.make_action_timer(
                            condition=action.Condition,
                            action=action.Action,
                            when_secs=delay,
                        )

    def create_pockets(self):
        log.debug("Creating pockets...")
        # make sure self.options.Pocketcount is properly specified
        try:
            assert isinstance(self.options.Pocketcount, int)
        except (KeyError, AssertionError):
            self.options["Pocketcount"] = 4
            log.warning(
                f'Global.Options.Pocketcount was set to an invalid value "{self.options.Pocketcount}", setting to 4.'
            )

        self.parent().pocket_objects = Munch(
            {i: ViewPocketObject(self, i) for i in range(self.options.Pocketcount)}
        )
        for pocket in self.parent().pocket_objects.values():
            pocket.show()
            pocket.raise_()

        log.debug("Pockets created.")

    def reload_pockets(self):
        log.debug(f"Reloading pockets: {self.parent().pocket_objects}")
        for pocket_object in self.parent().pocket_objects.values():
            pocket_object.init_pocket_image()
            pocket_object.setParent(self)
            pocket_object.show()
            pocket_object.raise_()
        log.debug("Pockets reloaded.")

    def create_nav_pics(self):
        # create all the nave images
        for nav_type in ("NavLeft", "NavRight", "NavTop", "NavBottom"):
            actions = [
                action
                for action in self.View.Actions.values()
                if action.Trigger.startswith(nav_type)
            ]
            if actions:
                nav_pic = NavImageObject(
                    self,
                    nav_type=nav_type,
                    nav_actions=actions,
                    nav_image_folder=self.options.TempFolder,
                )

                self.nav_pics[nav_type] = nav_pic

        # position them
        positions = dict(
            zip(
                ("NavTop", "NavBottom", "NavLeft", "NavRight"),
                (
                    QPoint(0, 0),
                    QPoint(0, self.height() - self.nav_extent),
                    QPoint(0, 0),
                    QPoint(self.width() - self.nav_extent, 0),
                ),
                strict=False,
            )
        )
        for nav_id, nav_pic in self.nav_pics.items():
            nav_pic.move(positions[nav_id])
            nav_pic.show()

    def view_elapsed(self):
        return timeit.default_timer() - self.view_start_time

    def on_media_stop(self, event, name: str = "unknown"):
        if name in self.video_controls and self.video_controls[name].Looped:
            self.video_controls[name].Controller.Seek(
                where=self.video_controls[name].Start
            )
            self.video_controls[name].Controller.Play()
            event.Veto()
        else:
            self.video_controls[name].Controller.Stop()
            self.video_controls[name].Window.Hide()
            event.Skip()

    def cleanup_view(self):
        # Remove Objects
        # NOTE: Unlike in wx, this cleanup might not be necessary!
        self.dragging_object, self.hovering_object = None, None
        for object_pic in self.object_pics.values():
            object_pic.close()
        # Remove Nav images
        for nav_pic in self.nav_pics.values():
            nav_pic.close()
        # Remove Overlay images
        for overlay_pic in self.overlay_pics.values():
            overlay_pic.close()
        # Remove External images
        for external_pic in self.external_pics.values():
            external_pic.close()
        for text_box in self.text_boxes.values():
            text_box.close()
        # Remove Audio Controllers
        for sound_player in self.sound_controls.values():
            sound_player.stop()
        # Remove Video Controllers
        for video_object in self.video_controls.values():
            video_object.pause()
            video_object.stop()
            video_object.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        try:
            self.ttimer.stop()
        except Exception:
            ...

        if self.sleep_event_loop.isRunning():
            self.sleep_event_loop.quit()
        log.debug(f"View {self.view_id} is closing!")
        self.cleanup_view()
        log.debug(f"View {self.view_id} has been cleanup up!")
        event.accept()

    def play_sound(
        self,
        sound_file: str,
        asynchronous: bool = True,
        loop: bool = False,
        volume: float = 1.0,
    ):
        sound_path = (
            Path(sound_file)
            if Path(sound_file).is_file()
            else Path(self.options.MediaPath, sound_file)
        )
        sound_name = sound_path.stem

        if sound_name in self.sound_controls:
            self.sound_controls[sound_name].stop()
            self.sound_controls[sound_name].play()
            return

        # Check cache for pre-converted WAV version of compressed audio
        playback_path = audiocache.get_playback_path(sound_path)

        # Log whether playing from cache or original
        if playback_path != sound_path:
            log.debug(
                f">>> AUDIO PLAYBACK: Playing from CACHE: {playback_path.name} (original: {sound_path.name})"
            )
        else:
            log.debug(
                f">>> AUDIO PLAYBACK: Playing from MEDIA FOLDER: {sound_path.name}"
            )

        try:
            player = SoundPlayer(
                sound_file=str(playback_path.absolute()),
                volume=self.options.Volume * volume * 100,
                loop=loop,
            )

            self.sound_controls[sound_name] = player
            player.play()

            if not asynchronous:
                self.sleep(
                    msec=500
                )  # it takes a moment to get going, only then is duration available.
                time_left = player.duration() - 500
                if time_left > 0 and player.is_playing():
                    self.sleep(msec=time_left)

        except Exception as e:
            log.error(f'Playback of sound "{sound_path.name}" failed: {e}')

    # -------------------------------------------------
    # >>>>>>>>> Action Trigger Handlers <<<<<<<<<<<<<<
    # -------------------------------------------------

    @staticmethod
    def valid_api_call(expression: str) -> tuple:
        if not expression:
            return ()

        try:
            func, params = func_str_parts(cmd=expression)
        except Exception:
            return ()

        if func in chain(VALID_CONDITIONS, VALID_ACTIONS, VALID_TRIGGERS):
            return func, params
        log.warning(f"The GEMS API does not expose any method called '{func}'.")
        return ()

    def safe_eval(self, expression: str):
        # get parts
        try:
            fn, param_list = func_str_parts(cmd=expression)
        except Exception:
            log.critical(
                f"ERROR: '{expression}' is an Unknown or mis-parameterized function string."
            )
            return None

        # make sure it's ok to actually call this function
        try:
            ok_calls = chain(VALID_CONDITIONS, VALID_ACTIONS, VALID_TRIGGERS)
            assert (
                fn in ok_calls
            ), f"ERROR: The GEMS API does not expose a method called '{expression}'."
            assert hasattr(
                self, fn
            ), f"ERROR: GEMS API method '{expression}' is not currently available."
        except Exception as e:
            log.critical(str(e))
            return None

        # make sure params only contain values
        param_values = [get_param(item) for item in param_list]
        ok_params = [is_safe_value(val) for val in param_values]

        if all(ok_params):
            return eval(
                f"self.{expression}"
            )  # NOTE: before you freak out about eval(), see the safestrfunc module
        log.critical(
            "ERROR: The GEMS API only supports constant values as method parameters (including list items)."
        )
        return None

    def do_action(self, condition: str, action: str):
        log.debug(
            f"do_action fired for view {self.view_id} at vt+ {timeit.default_timer() - self.view_start_time:.3f}s, action: {action}"
        )
        if not condition or self.safe_eval(condition):
            self.safe_eval(action)

    def handle_object_left_click(self, object_id: int):
        # find the object that got clicked
        _object = self.View.Objects[str(object_id)]

        for action in _object.Actions.values():
            if action.Enabled and action.Trigger == "MouseClick()":
                self.do_action(action.Condition, action.Action)

    def handle_pocket_right_click(self, pocket_id: int, quiet: bool = False):
        # get handy info from pocket about object it holds
        view_id = self.parent().pocket_objects[pocket_id].object_info.view_id
        object_id = self.parent().pocket_objects[pocket_id].object_info.Id

        # empty pocket?
        if view_id == -1 or object_id == -1:
            log.info(
                dict(
                    Kind="Mouse",
                    Type="PocketRightClick",
                    View=self.View.Name,
                    **gu.func_params(),
                    Result="Invalid|EmptyPocket",
                    TimeTime=self.parent().task_elapsed(),
                    ViewTime=self.view_elapsed(),
                )
            )
            return

        if not quiet:
            log.info(
                dict(
                    Kind="Mouse",
                    Type="PocketRightClick",
                    View=self.View.Name,
                    **gu.func_params(),
                    Result="Valid",
                    TimeTime=self.parent().task_elapsed(),
                    ViewTime=self.view_elapsed(),
                )
            )

        # find relevant object in db and make it visible
        self.db.Views[str(view_id)].Objects[str(object_id)].Visible = True

        # restore object to its rightful location
        if view_id == self.View.Id:
            self.object_pics[object_id].show()

        # clear out pocket
        self.parent().pocket_objects[pocket_id].object_info = Munch(
            {"name": "", "view_id": -1, "Id": -1, "image": self.pocket_bitmap}
        )
        self.parent().pocket_objects[pocket_id].init_pocket_image()

        # self.save_pockets()

        # log.debug(f'{self.parent().pocket_objects=}')

    def handle_pocket_drop(self, dropped_object_id: str, pocket_id: int) -> bool:
        # is this pocket even available?
        if (
            pocket_id in self.parent().pocket_objects
            and not self.parent().pocket_objects[pocket_id].object_info
        ):
            log.info(
                dict(
                    Kind="Mouse",
                    Type="PocketDragDrop",
                    View=self.View.Name,
                    **gu.func_params(),
                    Source=dropped_object_id,
                    Target=self.parent().pocket_objects[pocket_id].object_info.name,
                    Result="Invalid|FullPocket",
                    TimeTime=self.parent().task_elapsed(),
                    ViewTime=self.view_elapsed(),
                )
            )
            return False

        # is this object even takeable?
        if (
            dropped_object_id in self.View.Objects
            and not self.View.Objects[dropped_object_id].Takeable
        ):
            log.info(
                dict(
                    Kind="Mouse",
                    Type="PocketDragDrop",
                    View=self.View.Name,
                    **gu.func_params(),
                    Source=dropped_object_id,
                    Target=self.parent().pocket_objects[pocket_id].object_info.name,
                    Result="Invalid|ObjNotTakeable",
                    TimeTime=self.parent().task_elapsed(),
                    ViewTime=self.view_elapsed(),
                )
            )
            return False

        # ok, then put it in the pocket!
        log.info(
            dict(
                Kind="Mouse",
                Type="PocketDragDrop",
                View=self.View.Name,
                **gu.func_params(),
                Source=dropped_object_id,
                Target=self.parent().pocket_objects[pocket_id].object_info.name,
                Result="Valid",
                TimeTime=self.parent().task_elapsed(),
                ViewTime=self.view_elapsed(),
            )
        )

        # first, remove object from view
        try:
            self.db.Views[str(self.view_id)].Objects[
                dropped_object_id
            ].Visible = False  # set object to visible in db
            self.object_pics[int(dropped_object_id)].hide()
        except Exception:
            ...

        # object appears in pocket
        # TODO: from wxpython...port this to Qt? Currently image is stretched all funny to fill pocket.
        # # bitmap = self.object_pics[source_id].Image.GetBitmap()
        # # ow, oh = self.parent().pocket_objects[pocket_id].Image.GetSize()
        # bitmap = self.drag_object_bitmap
        # ow, oh = self.pocket_bitmap.GetSize()
        # bitmap = uiutils.scale_bitmap(bitmap=bitmap, width=ow, height=oh, quality=wx.IMAGE_QUALITY_BILINEAR)
        # self.parent().pocket_objects[pocket_id].bitmap = bitmap

        # update pocket properties so object can be referenced later
        # NOTE: verify that these are getting done in VPO.dropEvent (line 250ish)     <<< Seems to be working already!?
        # self.parent().pocket_objects[pocket_id].object_info.view_id = int(self.View.Id)
        # self.parent().pocket_objects[pocket_id].object_info.Id = int(dropped_object_id)
        # self.parent().pocket_objects[pocket_id].object_info.name = self.View.Objects[str(dropped_object_id)]

        return True

    def handle_object_drop(
        self, source_id: int, target_id: int, source_view_id: int = -1
    ):
        # if there's nothing to do, bail early
        if source_id == target_id:
            return

        _source_view_id = self.view_id if source_view_id == -1 else source_view_id
        source_object = self.db.Views[str(_source_view_id)].Objects[str(source_id)]
        target_object = self.db.Views[str(self.view_id)].Objects[str(target_id)]

        trigger = f"DroppedOn({source_object.Id})"
        valid_drop = any(
            action
            for action in target_object.Actions.values()
            if action.Enabled and action.Trigger.replace(" ", "") == trigger
        )

        if valid_drop:
            log.info(
                dict(
                    Kind="Mouse",
                    Type="ObjectDragDrop",
                    View=self.View.Name,
                    **gu.func_params(),
                    Source=source_object.Id,
                    Target=target_object.Id,
                    Result="Valid|Interaction",
                    TimeTime=self.parent().task_elapsed(),
                    ViewTime=self.view_elapsed(),
                )
            )
        else:
            log.info(
                dict(
                    Kind="Mouse",
                    Type="ObjectDragDrop",
                    View=self.View.Name,
                    **gu.func_params(),
                    Source=source_object.Id,
                    Target=target_object.Id,
                    Result="Invalid|Interaction",
                    TimeTime=self.parent().task_elapsed(),
                    ViewTime=self.view_elapsed(),
                )
            )
            return

        for action in target_object.Actions.values():
            if action.Enabled and action.Trigger.replace(" ", "") == trigger:
                self.do_action(action.Condition, action.Action)

    def handle_key_press(self, key_code):
        allowed = (
            string.digits
            + string.ascii_letters
            + string.punctuation
            + string.whitespace
        )
        key, key_text = key_code.key(), key_code.text()
        if key_text in allowed:
            self.key_buffer += key_text

        # Map special keys to named versions for trigger matching
        # First check key codes for keys that don't produce text (arrow keys, etc.)
        key_code_names = {
            Qt.Key.Key_Up: "UP",
            Qt.Key.Key_Down: "DOWN",
            Qt.Key.Key_Left: "LEFT",
            Qt.Key.Key_Right: "RIGHT",
        }
        # Then check text-based special keys
        special_key_names = {
            " ": "SPACE",
            "\r": "ENTER",
            "\n": "ENTER",
            "\t": "TAB",
            "\x1b": "ESCAPE",
            "\x7f": "BACKSPACE",
            "\x08": "BACKSPACE",
        }
        key_name = key_code_names.get(key, special_key_names.get(key_text, key_text))

        log.info(
            "Keyboard",
            Type="KeyPress",
            View=self.View.Name,
            Key=key,
            KeyText=key_text,
            KeyName=key_name,
            Result="Valid" if key_text in allowed else "Invalid",
            TimeTime=self.parent().task_elapsed(),
            ViewTime=self.view_elapsed(),
        )

        # Check both the literal key text and the named version
        triggers_to_check = [f'KeyPress("{key_text}")']
        if key_name != key_text:
            triggers_to_check.append(f'KeyPress("{key_name}")')

        for action in self.View.Actions.values():
            if action.Enabled and action.Trigger in triggers_to_check:
                self.do_action(action.Condition, action.Action)

    # fmt: off

    # ---------------------------------------------------
    # FORMATTING CONDITION, TRIGGER, AND ACTION METHODS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Doc strings must have a description to be used for help-text. Multi-line is ok.
    # Doc strings also need :scope and :mtype specifiers, each on their own line.
    # Each must be followed by a space and a single contiguous lowercase character identifier and then a newline
    # ---------------------------------------------------

    # -------------------------------------------
    # >>>>>>>>> Condition Handlers <<<<<<<<<<<<<<
    # Leave these as camel case!! Eval security
    # depends on it. Also, would break compatibility
    # with old environments.
    # -------------------------------------------

    def var_in_text(self, thetext: str) -> str:
        # sourcery skip: remove-unnecessary-cast
        """
        Search for variable specifiers in input string.
        Supports two syntaxes:
          - $VarName$ : Preferred syntax, works in all contexts including action parameters
          - [VarName] : Legacy syntax, may not work in action parameters due to bracket parsing
        If the variable currently is set, specifier is replaced by contents.
        Otherwise, it is replaced by 'Unknown'
        :param thetext: text to be scanned
        :return: updated version of thetext
        """
        newtext = str(thetext)

        # First, handle $VarName$ syntax (preferred, works in action parameters)
        dollar_pattern = re.compile(r'\$([A-Za-z_][A-Za-z0-9_]*)\$')
        for match in dollar_pattern.finditer(thetext):
            varname = match.group(1)
            full = match.group(0)
            try:
                newtext = newtext.replace(full, self.db.Variables.get(varname, 'Unknown'))
            except Exception as e:
                log.error(e)

        # Then, handle legacy [VarName] syntax for backwards compatibility
        bracket_pattern = re.compile(r'(\[)([^\]]+)(\])')
        speclist = bracket_pattern.findall(newtext)  # list of all specifiers

        # if empty, return current text
        if not speclist:
            return newtext

        # loop through specs and if they specify a current variable, replace
        # spec in input string with value of current variable, otherwise 'Unknown'
        for left, varname, right in speclist:
            full = left + varname + right
            try:
                newtext = newtext.replace(full, self.db.Variables.get(varname, 'Unknown'))
            except Exception as e:
                log.error(e)

        # return the updated text
        return newtext

    def _smart_compare(self, val1, val2) -> bool:
        """
        Smart comparison: if both values can be converted to floats, compare numerically.
        Otherwise, compare as strings.
        """
        try:
            return float(val1) == float(val2)
        except (ValueError, TypeError):
            return str(val1) == str(val2)

    def VarValueIs(self, variable: str, value: str) -> bool:
        # sourcery skip: remove-unnecessary-cast
        """
        This condition returns <i>True</i> if the user created token <b><i>Variable</i></b> exists and currently has
        the value <b><i>value</i></b>.
        :scope viewobjectglobalpocket
        :mtype condition
        """
        return variable in self.db.Variables and self._smart_compare(self.db.Variables[variable], value)

    def VarValueIsNot(self, variable: str, value: str) -> bool:
        """
        This condition returns <i>True</i> if the user created token <b><i>Variable</i></b> currently
        <u>does not have</u> the value <b><i>value</i></b> or does not exist.
        :scope viewobjectglobalpocket
        :mtype condition
        """
        return (
            variable not in self.db.Variables
            or not self._smart_compare(self.db.Variables[variable], value)
        )

    def VarExists(self, variable: str) -> bool:
        """
        This condition returns <i>True</i> if the user created token <b><i>Variable</i></b> currently exists.
        :scope viewobjectglobalpocket
        :mtype condition
        """
        return variable in self.db.Variables

    def VarMissing(self, variable: str) -> bool:
        """
        This condition returns <i>True</i> if the user created token <b><i>Variable</i></b> <u>does not</u>
        currently exists.
        :scope viewobjectglobalpocket
        :mtype condition
        """
        return variable not in self.db.Variables

    def HasViewTimePassed(self, seconds: float) -> bool:
        """
        This condition returns <i>True</i> if at least <b><i>Seconds</i></b> seconds has passed since the current view
        was displayed.
        :scope viewobject
        :mtype condition
        """
        return (timeit.default_timer() - self.view_start_time) > float(seconds)

    def HasTotalTimePassed(self, seconds: float) -> bool:
        """
        This condition returns <i>True</i> if at least <b><i>Seconds</i></b> seconds has passed since the current GEMS
        environment was started.
        :scope viewobjectglobalpocket
        :mtype condition
        """
        return (timeit.default_timer() - self.parent().task_start_time) > float(seconds)

    def VarCountEq(self, count: int) -> bool:
        """
        This condition returns <i>True</i> if the number of user created variables <u>equals</u> <b><i>Count</i></b>.
        :scope viewobjectglobalpocket
        :mtype condition
        """
        return len(self.db.Variables) == int(count)

    def VarCountGtEq(self, count: int) -> bool:
        """
        This condition returns <i>True</i> if the number of user created variables is <u>greater than or equal to</u>
        <b><i>Count</i></b>.
        :scope viewobjectglobalpocket
        :mtype condition
        """
        return len(self.db.Variables) >= int(count)

    def VarCountLtEq(self, count: int) -> bool:
        """
        This condition returns <i>True</i> if the number of user created variables is <u>less than or equal to</u>
        <b><i>Count</i></b>.
        :scope viewobjectglobalpocket
        :mtype condition
        """
        return len(self.db.Variables) <= int(count)

    # FIXME: In gemsedit, make it possible to specify the ignore_case argument so we can get rid
    #        of KeyBufferContainsIgnoreCase
    # TODO: Consider making the input be a list rather than a single string so sets of strings
    #       can be searched for.
    def KeyBufferContains(self, characters: str, ignore_case: bool = False) -> bool:
        """
        This condition returns <i>True</i> when the keyboard buffer contains the characters in
        <b><i>Characters</i></b>. Use only these characters: [a-zA-Z0-9 -_./]. If ignore_case
        is <i>True</i>, then search will be case insensitive.
        :scope viewglobal
        :mtype condition
        """
        if ignore_case:
            return str(characters).lower() in self.key_buffer.lower()
        else:
            return str(characters) in self.key_buffer

    def KeyBufferContainsIgnoreCase(self, characters: str) -> bool:
        """
        This condition returns <i>True</i> when the keyboard buffer contains the characters in
        <b><i>Characters</i></b>, ignoring case. Use only these characters: [a-zA-Z0-9 -_./].
        :scope viewglobal
        :mtype condition
        """
        return str(characters).lower() in self.key_buffer.lower()

    # TODO: Consider making the input be a list rather than a single string so sets of strings
    #       can be searched for.
    def KeyBufferLacks(self, characters: str, ignore_case: bool = False) -> bool:
        """
        This condition returns <i>True</i> when the keyboard buffer lacks the characters in
        <b><i>Characters</i></b>. Use only these characters: [a-zA-Z0-9 -_./]. If ignore_case
        is <i>True</i>, then search will be case insensitive.
        :scope viewglobal
        :mtype condition
        """
        if ignore_case:
            return str(characters).lower() not in self.key_buffer.lower()
        else:
            return str(characters) not in self.key_buffer

    # --------------------------------------------
    # >>>>>>>>>>> Trigger Handlers <<<<<<<<<<<<<<<<
    # --------------------------------------------
    # Some of these aren't don't and exist as stand-alone methods and
    #   only for documentation purposes

    def ViewTimePassed(self, seconds: float) -> bool:
        """
        This trigger fires when at least <b><i>Seconds</i></b> seconds has passed since the current view was displayed.
        :scope view
        :mtype trigger
        """
        return (timeit.default_timer() - self.view_start_time) > float(seconds)

    def TotalTimePassed(self, seconds: float) -> bool:
        """
        This trigger fires when at least <b><i>Seconds</i></b> seconds has passed since the current GEMS environment
        was started.
        :scope global
        :mtype trigger
        """
        return (timeit.default_timer() - self.parent().task_start_time) > float(seconds)

    def MouseClick(self):
        """
        This trigger fires whenever the mouse is <i>left</i>-clicked on an object or pocket.
        :scope objectpocket
        :mtype trigger
        """
        pass

    def NavLeft(self):
        """
        This trigger fires whenever the mouse is <i>left</i>-clicked towards the <b><i>Left</i></b> edge of the view.
        :scope view
        :mtype trigger
        """
        pass

    def NavRight(self):
        """
        This trigger fires whenever the mouse is <i>left</i>-clicked towards the <b><i>Right</i></b> edge of the view.
        :scope view
        :mtype trigger
        """
        pass

    def NavTop(self):
        """
        This trigger fires whenever the mouse is <i>left</i>-clicked towards the <b><i>Top</i></b> edge of the view.
        :scope view
        :mtype trigger
        """
        pass

    def NavBottom(self):
        """
        This trigger fires whenever the mouse is <i>left</i>-clicked towards the <b><i>Bottom</i></b> edge of the view.
        :scope view
        :mtype trigger
        """
        pass

    def DroppedOn(self, object_id: int):
        """
        This trigger fires when <b><i>Object</i></b> is dragged and then dropped onto the associated object.
        :scope objectpocket
        :mtype trigger
        """
        pass

    def KeyPress(self, key: str):
        """
        This trigger fires when <b><i>Key</i></b> is entered on the keyboard.
        :scope viewglobal
        :mtype trigger
        """
        pass

    # --------------------------------------------
    # >>>>>>>>>>> Action Handlers <<<<<<<<<<<<<<<<
    # --------------------------------------------

    def get_task_elapsed(self):
        try:
            return self.parent().task_elapsed()
        except RuntimeError:
            return None

    def ClearKeyBuffer(self):
        """
        This action clears all characters currently in the keyboard buffer.
        :scope viewobjectglobalpocket
        :mtype action
        """
        log.info(dict(Kind='Action', Type='ClearKeyBuffer', View=self.View.Name,
                      **gu.func_params(), Target=None, Result='Valid',
                      TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))
        self.key_buffer = ''

    def SetVariable(self, variable: str, value: str):
        """
        This action set the user created token <b><i>Variable</i></b> to <b><i>Value</i></b>.
        If <b><i>Variable</i></b> does not exist, it will first be created.
        :scope viewobjectglobalpocket
        :mtype action
        """
        log.info(dict(Kind='Action', Type='SetVariable', View=self.View.Name,
                      **gu.func_params(), Target=None, Result='Valid',
                      TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))
        try:
            self.db.Variables[variable] = value
            log.debug(f'CURRENT VARS:{self.db.Variables}')
        except Exception as e:
            log.info(dict(Kind='Action', Type='SetVariable', View=self.View.Name,
                          **gu.func_params(), Target=None, Result=f'Invalid|{str(e)}',
                          TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))

    def DelVariable(self, variable: str):
        """
        This action removes the user created token <b><i>variable</i></b>, assuming it exists.
        :scope viewobjectglobalpocket
        :mtype action
        """
        log.info(dict(Kind='Action', Type='DelVariable', View=self.View.Name,
                      **gu.func_params(), Target=None, Result='Valid',
                      TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))
        try:
            if variable in self.db.Variables:
                del self.db.Variables[variable]
        except KeyError:
            log.info(dict(Kind='Action', Type='SetVariable', View=self.View.Name,
                          **gu.func_params(), Target=None, Result='Invalid|NoSuchVarExists',
                          TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))

    def VarIncrease(self, variable: str):
        """
        This action increases the value of <b><i>Variable</i></b> by 1.
        If the variable does not exist or has a non-numeric value, it will be created and set to 1.
        :scope viewobjectglobalpocket
        :mtype action
        """
        log.info(dict(Kind='Action', Type='VarIncrease', View=self.View.Name,
                      **gu.func_params(), Target=None, Result='Valid',
                      TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))
        try:
            if variable in self.db.Variables:
                current_value = self.db.Variables[variable]
                try:
                    numeric_value = float(current_value)
                    # Keep as int if it was an int
                    if numeric_value == int(numeric_value):
                        self.db.Variables[variable] = str(int(numeric_value) + 1)
                    else:
                        self.db.Variables[variable] = str(numeric_value + 1)
                except (ValueError, TypeError):
                    # Non-numeric value, set to 1
                    self.db.Variables[variable] = "1"
            else:
                # Variable doesn't exist, create and set to 1
                self.db.Variables[variable] = "1"
            log.debug(f'CURRENT VARS:{self.db.Variables}')
        except Exception as e:
            log.info(dict(Kind='Action', Type='VarIncrease', View=self.View.Name,
                          **gu.func_params(), Target=None, Result=f'Invalid|{str(e)}',
                          TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))

    def VarDecrease(self, variable: str):
        """
        This action decreases the value of <b><i>Variable</i></b> by 1.
        If the variable does not exist or has a non-numeric value, it will be created and set to 0.
        :scope viewobjectglobalpocket
        :mtype action
        """
        log.info(dict(Kind='Action', Type='VarDecrease', View=self.View.Name,
                      **gu.func_params(), Target=None, Result='Valid',
                      TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))
        try:
            if variable in self.db.Variables:
                current_value = self.db.Variables[variable]
                try:
                    numeric_value = float(current_value)
                    # Keep as int if it was an int
                    if numeric_value == int(numeric_value):
                        self.db.Variables[variable] = str(int(numeric_value) - 1)
                    else:
                        self.db.Variables[variable] = str(numeric_value - 1)
                except (ValueError, TypeError):
                    # Non-numeric value, set to 0
                    self.db.Variables[variable] = "0"
            else:
                # Variable doesn't exist, create and set to 0
                self.db.Variables[variable] = "0"
            log.debug(f'CURRENT VARS:{self.db.Variables}')
        except Exception as e:
            log.info(dict(Kind='Action', Type='VarDecrease', View=self.View.Name,
                          **gu.func_params(), Target=None, Result=f'Invalid|{str(e)}',
                          TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))

    def TextBox(self, message: str, left: int, top: int, duration: float, fgcolor: list, bgcolor: list,
                font_size: int, bold: bool = False, skiplog: bool = False):
        """
        This action causes GEMS to draw a textbox over the view containing the text in <b><i>Message</i></b>.
        The message will be positioned at (<b><i>Left</i></b>, <b><i>Top</i></b>) in pixels.
        After <b><i>Duration</i></b> seconds [default = 0 = forever], the textbox will be removed.
        Use the provided font styling parameters to style the textbox as desired.
        If left, top == -1, -1 then box will be drawn at the current cursor location, which could allow for
        popup context-like effects when an object is created.
        :scope viewobjectglobalpocket
        :mtype action
        """
        if not skiplog:
            log.info(dict(Kind='Action', Type='TextBox', View=self.View.Name, **gu.func_params(),
                          Target=None, Result='Success', TimeTime=self.get_task_elapsed(),
                          ViewTime=self.view_elapsed()))

        # convert any variable specifiers in msg
        _message = self.var_in_text(message)

        if (left, top) == (-1, -1):
            pos = self.mapFromGlobal(QCursor.pos())
            left, top = pos.x(), pos.y()

        func_call_params = [gu.func_name()] + list(dict(sorted(gu.func_params().items())).values())
        func_call_hash = gu.string_hash(str(func_call_params))

        fg = fgcolor if len(fgcolor) == 4 else fgcolor[-4:]
        bg = bgcolor if len(bgcolor) == 4 else bgcolor[-4:]

        text_box = TextBoxObject(self, message=_message, left=self.geom_x_adjust(left), top=self.geom_y_adjust(top),
                                 duration=duration, fg_color=fg, bg_color=bg, font_size=font_size, bold=bold)
        text_box.show()
        self.text_boxes[func_call_hash] = text_box

    # TODO: Need to depreciate this...in qt, basic text box can already handle html. Redirecting for now.
    def TextBoxHTML(self, message: str, left: int, top: int, duration: float, fgcolor: list, bgcolor: list,
                    font_size: int, bold: bool = False, skiplog: bool = False):
        """
        This action causes GEMS to draw a textbox over the view containing the HTML-formatted text
        in <b><i>Message</i></b>. The message will be positioned at (<b><i>Left</i></b>, <b><i>Top</i></b>) in pixels.
        After <b><i>Duration</i></b> seconds [default = 0 = forever], the textbox will be removed.
        Use the provided font styling parameters to style the textbox as desired.
        That the markup accepted by the action is limited and is described at
        <a href="bit.ly/wxpmarkup">bit.ly/wxpmarkup</a>.
        If left, top == -1, -1 then box will be drawn at the current cursor location, which could allow for
        popup context-like effects when an object is created.
        <font color="red">This Is Not Currently Implemented!</font>
        :scope viewobjectglobalpocket
        :mtype action
        """
        self.TextBox(message=message, left=self.geom_x_adjust(left), top=self.geom_y_adjust(top), duration=duration,
                     fgcolor=fgcolor, bgcolor=bgcolor, font_size=font_size, bold=bold, skiplog=skiplog)

    def ShowObject(self, object_id: int, skiplog: bool = False):
        """
        This action causes GEMS to make visible the object identified as <b><i>Object_Id</i></b>.
        :scope viewobjectglobalpocket
        :mtype action
        """
        try:
            # could be in any view!
            for view in self.db.Views.values():
                for _object in view.Objects.values():
                    if _object.Id == object_id:
                        self.db.Views[str(view.Id)].Objects[str(object_id)].Visible = True
        except Exception as e:
            if not skiplog:
                log.info(dict(Kind='Action', Type='ShowObject', View=self.View.Name,
                              **gu.func_params(), Target=None, Result="Invalid|ObjectDoesNotExist",
                              TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))
            log.debug(e)
        else:
            if str(object_id) in self.View.Objects.keys():
                self.object_pics[object_id].show()
                if not skiplog:
                    log.info(dict(Kind='Action', Type='ShowObject', View=self.View.Name,
                                  **gu.func_params(), Target=None, Result='Valid',
                                  TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))

    def HideObject(self, object_id: int, skiplog: bool = False):
        """
        This action causes GEMS to make invisible the object identified as <b><i>Ob<jectId/i></b>.
        :scope viewobjectglobalpocket
        :mtype action
        """
        # If the object in currently pocketed, put it back first
        for pocket_id, pocket in self.parent().pocket_objects.items():
            if object_id == pocket.object_info.Id:
                self.handle_pocket_right_click(pocket_id, quiet=True)

        # now actually attempt to hide it
        try:
            # could be in any view!
            for view in self.db.Views.values():
                for _object in view.Objects.values():
                    if _object.Id == object_id:
                        self.db.Views[str(view.Id)].Objects[str(object_id)].Visible = False
        except Exception as e:
            if not skiplog:
                log.info(dict(Kind='Action', Type='HideObject', View=self.View.Name,
                              **gu.func_params(), Target=None, Result="Invalid|ObjectDoesNotExist",
                              TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))
                log.debug(e)
        else:
            if str(object_id) in self.View.Objects.keys():
                self.object_pics[object_id].hide()
                if not skiplog:
                    log.info(dict(Kind='Action', Type='HideObject', View=self.View.Name,
                                  **gu.func_params(), Target=None, Result='Valid',
                                  TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))

    def AllowTake(self, object_id: int):
        """
        This action causes GEMS to make <i>takeable</i> the object identified as <b><i>ObjectId</i></b>.
        :scope viewobjectglobalpocket
        :mtype action
        """
        try:
            # could be in any view!
            for view in self.db.Views.values():
                for _object in view.Objects.values():
                    if _object.Id == object_id:
                        self.db.Views[str(view.Id)].Objects[str(object_id)].Takeable = True
            log.info(dict(Kind='Action', Type='AllowTake', View=self.View.Name,
                          **gu.func_params(), Target=None, Result='Valid',
                          TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))
        except Exception as e:
            log.info(dict(Kind='Action', Type='AllowTake', View=self.View.Name,
                          **gu.func_params(), Target=None, Result="Invalid|ObjectDoesNotExist",
                          TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))
            log.debug(e)

    def DisallowTake(self, object_id: int):
        """
        This action causes GEMS to make <i>untakeable</i> the object identified as <b><i>ObjectId</i></b>.
        :scope viewobjectglobalpocket
        :mtype action
        """
        try:
            # could be in any view!
            for view in self.db.Views.values():
                for _object in view.Objects.values():
                    if _object.Id == object_id:
                        self.db.Views[str(view.Id)].Objects[str(object_id)].Takeable = False
            log.info(dict(Kind='Action', Type='DisallowTake', View=self.View.Name,
                          **gu.func_params(), Target=None, Result='Valid',
                          TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))
        except Exception as e:
            log.info(dict(Kind='Action', Type='DisallowTake', View=self.View.Name,
                          **gu.func_params(), Target=None, Result="Invalid|ObjectDoesNotExist",
                          TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))
            log.debug(e)

    def HideImage(self, image_file: str = ''):
        """
        This action removes the image based on <b><i>ImageFile</i></b>, assuming it currently being displayed.
        :scope viewobjectpocket
        :mtype action
        """
        try:
            pic_name = Path(image_file).stem
            self.external_pics[pic_name].hide()
            log.info(dict('Action', Type='HideImage', View=self.View.Name, **gu.func_params(), Target=None,
                          Result='Valid', TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))
        except Exception as e:
            log.info(dict('Action', Type='HideImage', View=self.View.Name, **gu.func_params(), Target=None,
                          Result='Invalid|ObjectDoesNotExist', TimeTime=self.get_task_elapsed(),
                          ViewTime=self.view_elapsed()))
            log.debug(e)

    def ShowImage(self, image_file: str = '', left: int = 0, top: int = 0, duration: float = 0.0,
                  click_through: bool = False):
        """
        This action loads and displays <b><i>ImageFile</i></b> at (<b><i>Left</i></b>, <b><i>Top</i></b>) for
        <b><i>Duration</i></b> seconds [default = 0 = forever]. Click_through determines whether objects underneath
        image respond to mouse clicks (default is False)
        The image is removed when the view is changed.
        :scope viewobjectpocket
        :mtype action
        """

        log.info(dict(Kind='Action', Type='ShowImage', View=self.View.Name, **gu.func_params(),
                      Target=None, Result='Valid', TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))

        pic_path = Path(self.options.MediaPath, image_file)
        pic_name = Path(pic_path).stem

        if pic_name in self.external_pics:
            self.external_pics[pic_name].show()
            return

        try:
            x_ratio, y_ratio = self.background_scale
            image = ExternalImageObject(self, image_path=pic_path, left=self.geom_x_adjust(left),
                                        top=self.geom_y_adjust(top), duration=duration, click_through=click_through,
                                        scale=(x_ratio, y_ratio))
            image.show()
            self.external_pics[pic_name] = image

            self.reset_z_pos()

        except Exception as e:
            log.error(f'Unable to load external image from {str(pic_path.resolve())}: {e}')

    def ShowImageWithin(
        self,
        image_file: str = "",
        left: int = 0,
        top: int = 0,
        duration: float = 0.0,
        click_through: bool = False,
        within: int = -1,
        hide_target: bool = False,
        stretch: bool = False,
    ):
        """
        Like ShowImage, but if Within refers to a valid object, the image is scaled and positioned to that object's
        bounds. Otherwise it falls back to Left/Top positioning. Optionally hides the target while overlaid.
        stretch determines whether to ignore aspect ratio when fitting the target bounds.
        :scope viewobjectpocket
        :mtype action
        """

        log.info(
            dict(
                Kind="Action",
                Type="ShowImageWithin",
                View=self.View.Name,
                **gu.func_params(),
                Target=None,
                Result="Valid",
                TimeTime=self.get_task_elapsed(),
                ViewTime=self.view_elapsed(),
            )
        )

        pic_path = Path(self.options.MediaPath, image_file)
        pic_name = Path(pic_path).stem
        target = self.object_pics.get(int(within)) if within is not None else None

        try:
            pixmap = QPixmap(str(pic_path.resolve()))
        except Exception as e:
            log.error(f"Unable to load external image from {str(pic_path.resolve())}: {e}")
            return

        if pic_name in self.external_pics:
            image = self.external_pics[pic_name]
        else:
            # Start with a neutral scaled image; we will resize/position below
            image = ExternalImageObject(
                self,
                image_path=pic_path,
                left=0,
                top=0,
                duration=duration,
                click_through=click_through,
                scale=(1.0, 1.0),
            )
            self.external_pics[pic_name] = image

        if target:
            target_rect = target.geometry()
            target_was_visible = target.isVisible()
            scaled = pixmap.scaled(
                target_rect.width(),
                target_rect.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            image.setPixmap(scaled)
            image.setFixedSize(scaled.width(), scaled.height())

            if stretch:
                # center within target bounds while keeping aspect ratio
                offset_x = target_rect.left() + (target_rect.width() - scaled.width()) // 2
                offset_y = target_rect.top() + (target_rect.height() - scaled.height()) // 2
                image.move(offset_x, offset_y)
            else:
                image.move(target_rect.topLeft())
            if hide_target:
                target.hide()
                if duration and target_was_visible:
                    QTimer.singleShot(
                        int(duration * 1000),
                        self,
                        target.show,
                    )
        else:
            # Fall back to standard behavior using stage-aligned coordinates
            ratio_x, ratio_y = self.background_scale
            scaled = pixmap.scaled(
                int(pixmap.width() * ratio_x),
                int(pixmap.height() * ratio_y),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            image.setPixmap(scaled)
            image.setFixedSize(scaled.width(), scaled.height())
            image.move(self.geom_x_adjust(left), self.geom_y_adjust(top))

        image.show()
        self.reset_z_pos()

    def PortalTo(self, view_id: int, vid_file: str = ''):
        """
        This action causes GEMS to load <b><i>ViewId</i></b>. If <b><i>VidFile</i></b> is provided
        and exists, the video will play fullscreen first as a transition effect. The view change
        occurs when the video finishes or is right-clicked.

        :scope viewobjectglobalpocket
        :mtype action
        """
        if str(view_id) not in self.db.Views:
            log.info(dict(Kind='Action', Type='PortalTo', View=self.View.Name, **gu.func_params(), Target=None,
                          Result='Invalid|ViewDoesNotExist', TimeTime=self.get_task_elapsed(),
                          ViewTime=self.view_elapsed()))
            return

        def do_portal():
            """Perform the actual portal to the target view."""
            self.parent().next_view_id = view_id
            self.parent().shutdown_view()

        # Check if a transition video was specified
        if vid_file:
            video_path = Path(vid_file) if Path(vid_file).is_file() else Path(self.options.MediaPath, vid_file)
            is_gif = video_path.suffix.lower() == '.gif'

            if video_path.exists() and (self.options.PlayMedia or is_gif):
                log.info(dict(Kind='Action', Type='PortalTo', View=self.View.Name, **gu.func_params(), Target=None,
                              Result='Valid|WithTransition', TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))

                video_name = video_path.stem
                pos = QPoint(0, 0)
                size = self.size()

                try:
                    if is_gif:
                        video = AnimationObject(self, video_path=video_path, pos=pos, size=size, start=0,
                                                volume=self.options.Volume * 1000, loop=False, on_finish=do_portal)
                    else:
                        video = VideoObject(self, video_path=video_path, pos=pos, size=size, start=0,
                                            volume=self.options.Volume * 1000, loop=False, on_finish=do_portal)
                    self.video_controls[video_name] = video
                    self.reset_z_pos()
                    return
                except Exception as e:
                    log.error(f'Unable to create transition video from {str(video_path.resolve())}: {e}')
                    # Fall through to do portal without video

        # No transition video or video failed - do direct portal
        log.info(dict(Kind='Action', Type='PortalTo', View=self.View.Name, **gu.func_params(), Target=None,
                      Result='Valid', TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))
        do_portal()

    def ChangeViewImages(self, view_id: int, foreground: str = '', background: str = ''):
        """
        This action changes the Foreground and/or Background images for the specified view.
        Only valid image file paths will be applied. This is intended to alter images for a
        view the user may travel to subsequently - if the specified view is the current view,
        no refresh occurs.

        :scope viewobjectglobalpocket
        :mtype action
        """
        if str(view_id) not in self.db.Views:
            log.info(dict(Kind='Action', Type='ChangeViewImages', View=self.View.Name, **gu.func_params(),
                          Target=None, Result='Invalid|ViewDoesNotExist',
                          TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))
            return

        target_view = self.db.Views[str(view_id)]
        changes_made = []

        # Check and apply foreground if valid
        if foreground:
            fg_path = Path(foreground) if Path(foreground).is_file() else Path(self.options.MediaPath, foreground)
            if fg_path.exists() and fg_path.is_file():
                target_view.Foreground = foreground
                changes_made.append(f'Foreground={foreground}')

        # Check and apply background if valid
        if background:
            bg_path = Path(background) if Path(background).is_file() else Path(self.options.MediaPath, background)
            if bg_path.exists() and bg_path.is_file():
                target_view.Background = background
                changes_made.append(f'Background={background}')

        if changes_made:
            log.info(dict(Kind='Action', Type='ChangeViewImages', View=self.View.Name, **gu.func_params(),
                          Target=f'View{view_id}', Result=f'Valid|{",".join(changes_made)}',
                          TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))
        else:
            log.info(dict(Kind='Action', Type='ChangeViewImages', View=self.View.Name, **gu.func_params(),
                          Target=f'View{view_id}', Result='Valid|NoChanges',
                          TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))

    def PlaySound(self, sound_file: str, asynchronous: bool = True, volume: float = 1.0, loop: bool = False):
        """
        This action instructs GEMS to play the audio in <b><i>SoundFile</i></b>. If <b><i>Asynchronous</i></b> is
        <i>True</i>, the soundfile plays and returns control immediately to GEMS. Otherwise, GEMS is blocked until
        the sound finishes. If <b><i>Loop</i></b> is "True", the soundfile will loop continually (MacOS Only).
        :scope viewobjectglobalpocket
        :mtype action
        """
        if "PlayMedia" in self.db.Global.Options and not self.db.Global.Options.PlayMedia:
            log.warning("Media playback is not enabled.")
            return

        if loop:
            log.warning('NOTE: the loop parameter of PlaySound is not yet implemented')

        sound_path = Path(sound_file) if Path(sound_file).is_file() else Path(self.options.MediaPath, sound_file)
        log.info(f"Requesting audio playback: {sound_path}")

        if not sound_path.exists():
            log.error(f"Audio file does not exist: {sound_path}")
            return

        log.info(dict(Kind='Action', Type='PlaySound', View=self.View.Name, **gu.func_params(), Target=None,
                      Result='Valid', TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))

        try:
            self.play_sound(sound_file=str(sound_path.resolve()), asynchronous=asynchronous, loop=loop, volume=volume)
        except Exception as e:
            log.error(f'Error playing audio file {sound_file}: {e}')
            # Provide helpful diagnostic information
            self._log_audio_diagnostics()

    def _log_audio_diagnostics(self):
        """Log diagnostic information about audio backends"""
        try:
            from gemsrun.utils.audioutils import get_audio_backend_info
            info = get_audio_backend_info()
            log.info(f"Audio backend diagnostics: {info}")

            if not info['available_backends']:
                log.warning("No audio backends available. Consider installing:")
                log.warning("- PulseAudio (paplay) for Linux")
                log.warning("- ALSA utilities (aplay) for Linux")
                log.warning("- FFmpeg (ffplay) for cross-platform support")
        except Exception as e:
            log.error(f"Could not get audio diagnostics: {e}")

    def StopSound(self, sound_file: str):
        """
        This action instructs GEMS to stop playing audio based on <b><i>SoundFile</i></b>,
        assuming it is currently playing (MacOS Only).
        :scope viewobjectglobalpocket
        :mtype action
        """
        if "PlayMedia" in self.db.Global.Options and not self.db.Global.Options.PlayMedia:
            log.warning("Media playback is not enabled.")
            return

        sound_name = Path(sound_file).stem

        if sound_name not in self.sound_controls:
            log.info(dict(Kind='Action', Type='StopSound', View=self.View.Name, **gu.func_params(),
                          Target=None, Result='Invalid|SoundDoesNotExist', TimeTime=self.get_task_elapsed(),
                          ViewTime=self.view_elapsed()))
            return

        log.info(dict(Kind='Action', Type='StopSound', View=self.View.Name, **gu.func_params(), Target=None,
                      Result='Valid', TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))

        try:
            self.sound_controls[sound_name].stop()
        except Exception as e:
            log.error(f'Error stopping audio playback for {sound_file}: {e}')

    def StopAllSounds(self):
        """
        This action instructs GEMS to stop playing all currently playing audio (MacOS Only).
        :scope viewobjectglobalpocket
        :mtype action
        """

        if "PlayMedia" in self.db.Global.Options and not self.db.Global.Options.PlayMedia:
            log.warning("Media playback is not enabled.")
            return

        log.info(dict(Kind='Action', Type='StopAllSounds', View=self.View.Name, **gu.func_params(), Target=None,
                      Result='Valid', TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))

        for sound_player in self.sound_controls.values():
            try:
                sound_player.stop()
            except Exception as e:
                log.error(f'Error stopping audio playback: {e}')

    def PlayBackgroundMusic(self, sound_file: str, volume: float = 1.0, loop: bool = False):
        """
        This action plays <b><i>SoundFile</i></b> as background music at the specified
        <b><i>Volume</i></b>. Only one background music stream can play at a time. If background
        music is already playing, it will be stopped and the new music will start. Background
        music persists across view changes and is not affected by StopAllSounds.
        If <b><i>Loop</i></b> is True, the music will loop indefinitely.
        :scope viewobjectglobalpocket
        :mtype action
        """
        if "PlayMedia" in self.db.Global.Options and not self.db.Global.Options.PlayMedia:
            log.warning("Media playback is not enabled.")
            return

        sound_path = Path(sound_file) if Path(sound_file).is_file() else Path(self.options.MediaPath, sound_file)
        log.info(f"Requesting background music playback: {sound_path}")

        if not sound_path.exists():
            log.error(f"Background music file does not exist: {sound_path}")
            log.info(dict(Kind='Action', Type='PlayBackgroundMusic', View=self.View.Name, **gu.func_params(),
                          Target=None, Result='Invalid|FileNotFound', TimeTime=self.get_task_elapsed(),
                          ViewTime=self.view_elapsed()))
            return

        log.info(dict(Kind='Action', Type='PlayBackgroundMusic', View=self.View.Name, **gu.func_params(),
                      Target=None, Result='Valid', TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))

        # Check cache for pre-converted WAV version of compressed audio
        playback_path = audiocache.get_playback_path(sound_path)
        if playback_path != sound_path:
            log.debug(f"Using cached WAV for background music: {playback_path}")

        try:
            audioutils.play_background_music(
                sound_file=str(playback_path.resolve()),
                volume=self.options.Volume * volume,
                loop=loop
            )
        except Exception as e:
            log.error(f'Error playing background music {sound_file}: {e}')

    def StopBackgroundMusic(self):
        """
        This action stops the currently playing background music if any.
        :scope viewobjectglobalpocket
        :mtype action
        """
        if "PlayMedia" in self.db.Global.Options and not self.db.Global.Options.PlayMedia:
            log.warning("Media playback is not enabled.")
            return

        log.info(dict(Kind='Action', Type='StopBackgroundMusic', View=self.View.Name, **gu.func_params(),
                      Target=None, Result='Valid', TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))

        try:
            audioutils.stop_background_music()
        except Exception as e:
            log.error(f'Error stopping background music: {e}')

    def PlayVideo(self, video_file: str, start: int = 0, left: int = 0, top: int = 0, volume: float = 1.0, loop: bool = False):
        """
        This action instructs GEMS to play the video in <b><i>VideoFile</i></b>. The video begins playing at
        <b><i>Start</i></b> seconds, positioned at (<b><i>Left</i></b>, <b><i>Top</i></b>) with its native
        width and height.
        :scope viewobjectglobalpocket
        :mtype action
        """

        video_path = Path(self.options.MediaPath, video_file)
        video_name = Path(video_path).stem
        is_gif = video_path.suffix.lower() in {'.gif'}

        if not self.options.PlayMedia and not is_gif:
            log.warning("Media playback is not enabled.")
            return

        if video_name in self.video_controls:
            self.video_controls[video_name].close()
            self.video_controls[video_name].hide()
            del self.video_controls[video_name]

        log.info(dict(Kind='Action', Type='PlayVideo', View=self.View.Name, **gu.func_params(),
                      Target=None, Result='Valid', TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))

        pos = QPoint(int(left), int(top))
        size = None

        try:
            if is_gif:
                video = AnimationObject(self, video_path=video_path, pos=pos, size=size, start=start,
                                        volume=self.options.Volume * volume * 1000, loop=loop)
            else:
                video = VideoObject(self, video_path=video_path, pos=pos, size=size, start=start,
                                    volume=self.options.Volume * volume * 1000, loop=loop)
            self.video_controls[video_name] = video

            self.reset_z_pos()

        except Exception as e:
            log.error(f'Unable to create or play video object from {str(video_path.resolve())}: {e}')

    def PlayVideoWithin(self, video_file: str, start: int = 0, within: int = -1, volume: float = 1.0, loop: bool = False):
        """
        This action instructs GEMS to play the video in <b><i>VideoFile</i></b>. The video begins playing at
        <b><i>Start</i></b> seconds. If <b><i>Within</i></b> refers to the Id of a currently visible object,
        the video will play within that object's boundary. Otherwise, the video will play from (0, 0) with
        its native width and height.
        :scope viewobjectglobalpocket
        :mtype action
        """

        if within < 0:
            self.PlayVideo(video_file, start, 0, 0, volume, loop)
            return

        video_path = Path(self.options.MediaPath, video_file)
        video_name = Path(video_path).stem
        is_gif = video_path.suffix.lower() in {'.gif'}

        if not self.options.PlayMedia and not is_gif:
            log.warning("Media playback is not enabled.")
            return

        if video_name in self.video_controls:
            self.video_controls[video_name].close()
            self.video_controls[video_name].hide()
            del self.video_controls[video_name]

        log.info(dict(Kind='Action', Type='PlayVideoWithin', View=self.View.Name, **gu.func_params(),
                      Target=None, Result='Valid', TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))

        target = self.object_pics.get(int(within))
        if target:
            pos = target.pos()
            size = target.size()
            target.hide()
        else:
            log.warning(
                f'The "within" parameter ({within}) is not the id of an object in this view. '
                f"Showing video at (0, 0) instead."
            )
            pos = QPoint(0, 0)
            size = None

        try:
            if is_gif:
                video = AnimationObject(self, video_path=video_path, pos=pos, size=size, start=start,
                                        volume=self.options.Volume * volume * 1000, loop=loop)
            else:
                video = VideoObject(self, video_path=video_path, pos=pos, size=size, start=start,
                                    volume=self.options.Volume * volume * 1000, loop=loop)
            self.video_controls[video_name] = video

            self.reset_z_pos()

        except Exception as e:
            log.error(f'Unable to create or play video object from {str(video_path.resolve())}: {e}')

    def StopVideo(self, video_file: str):
        """
        This action instructs GEMS to stop playing the video in <b><i>VideoFile</i></b>,
        assuming it is currently playing..
        :scope viewobjectglobalpocket
        :mtype action
        """
        video_name = Path(video_file).stem

        if video_name in self.video_controls.keys():

            log.info(dict(Kind='Action', Type='StopVideo', View=self.View.Name, **gu.func_params(), Target=None,
                          Result='Valid', TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))

            try:
                self.video_controls[video_name].close()
                self.video_controls[video_name].hide()
                del self.video_controls[video_name]
            except Exception as e:
                log.error(f'Error pausing video playback for {video_file}: {e}')
        else:
            log.info(dict(Kind='Action', Type='StopVideo', View=self.View.Name, **gu.func_params(),
                          Target=None, Result='Invalid|VideoNotPlaying', TimeTime=self.get_task_elapsed(),
                          ViewTime=self.view_elapsed()))
            return

    def StopAllVideos(self):
        """
        This action instructs GEMS to stop playing any video that is currently playing.
        :scope viewobjectglobalpocket
        :mtype action
        """
        log.info(dict(Kind='Action', Type='StopAllVideos', View=self.View.Name, **gu.func_params(), Target=None,
                      Result='Valid', TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))

        for video_name in list(self.video_controls.keys()):
            try:
                self.video_controls[video_name].close()
                self.video_controls[video_name].hide()
                del self.video_controls[video_name]
            except Exception as e:
                log.error(f'Error stopping video playback for {video_name}: {e}')

    def Quit(self):
        """
        This action terminates the current GEMS environment.
        :scope viewobjectglobalpocket
        :mtype action
        """
        log.info('Action', Type='Quit', View=self.View.Name, Target=None, Result='Valid',
                 TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed())
        self.parent().next_view_id = -1
        self.parent().shutdown_view()

    def HideMouse(self):
        """
        This action hides the mouse cursor.
        :scope viewobjectglobalpocket
        :mtype action
        """
        log.info('Action', Type='HideMouse', View=self.View.Name, Target=None, Result='Valid',
                 TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed())

        try:
            self.setCursor(Qt.CursorShape.BlankCursor)
        except Exception as e:
            log.debug(f'SetCursor Failed?! ({e})')

    def ShowMouse(self):
        """
        This action unhides the mouse cursor, assuming it is currently hidden.
        :scope viewobjectglobalpocket
        :mtype action
        """
        log.info(dict(Kind='Action', Type='ShowMouse', View=self.View.Name, Target=None, Result='Valid',
                      TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))

        try:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        except Exception as e:
            log.debug(f'SetCursor Failed?! ({e})')

    def ShowURL(self, url: str):
        """
        This action shows a custom browser window over the current view and loads the page at the supplied
        <b><i>URL</i></b>. The window remains atop the GEMS environment until dismissed by the user (close button).
        :scope viewobjectglobalpocket
        :mtype action
        """
        log.info(dict(Kind='Action', Type='ShowURL', View=self.View.Name, **gu.func_params(), Target=None,
                      Result='Valid', TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))

        webbrowser.open(url)

    def RunProgram(self, application: str, parameters: str = ''):
        """
        This action launches an external application specified by <b><i>Application</i></b>.
        Optional <b><i>Parameters</i></b> can be passed to the application as command-line arguments.
        :scope viewobjectglobalpocket
        :mtype action
        """
        log.info(dict(Kind='Action', Type='RunProgram', View=self.View.Name, **gu.func_params(), Target=None,
                      Result='Valid', TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))

        if not application:
            log.warning("RunProgram called with empty application path.")
            return

        def build_command(app_path: str) -> list[str]:
            """Build the command list based on platform."""
            if sys.platform == 'darwin':  # macOS
                if parameters:
                    return ['open', '-a', app_path, '--args'] + parameters.split()
                else:
                    return ['open', '-a', app_path]
            elif sys.platform == 'win32':  # Windows
                if parameters:
                    return [app_path] + parameters.split()
                else:
                    return [app_path]
            else:  # Linux and other Unix-like systems
                # Run shell scripts through bash to handle missing/invalid shebangs
                is_shell_script = app_path.endswith(('.sh', '.bash'))
                if is_shell_script:
                    if parameters:
                        return ['bash', app_path] + parameters.split()
                    else:
                        return ['bash', app_path]
                else:
                    if parameters:
                        return [app_path] + parameters.split()
                    else:
                        return [app_path]

        try:
            # Launch the process without waiting for it to complete
            cmd = build_command(application)
            subprocess.Popen(cmd, start_new_session=True)
            log.debug(f"RunProgram launched: {application} with parameters: {parameters}")

        except FileNotFoundError:
            # Check if the application exists in the media folder
            media_path = Path(self.options.MediaPath) / application
            if media_path.is_file():
                try:
                    cmd = build_command(str(media_path))
                    subprocess.Popen(cmd, start_new_session=True)
                    log.debug(f"RunProgram launched from media folder: {media_path} with parameters: {parameters}")
                except Exception as e:
                    log.error(f"RunProgram: Failed to launch {media_path}: {e}")
            else:
                log.error(f"RunProgram: Application not found: {application}")
        except Exception as e:
            log.error(f"RunProgram: Failed to launch {application}: {e}")

    def TextDialog(self, message: str, title: str = '', dialog_kind: str = 'info'):
        """
        This action causes GEMS to display an input dialog box containing <b><i>Message</i></b>, with the title
        <b><i>Title</i></b>. The parameter <b><i>DialogKind</i></b> will determine the icon type displayed in
        the dialog box. The dialog box will remain until the user presses the SUBMIT button.
        :scope viewobjectglobalpocket
        :mtype action
        """
        log.info(dict(Kind='Action', Type='TextDialog', View=self.View.Name, **gu.func_params(), Target=None,
                      Result='Valid', TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))

        if dialog_kind not in ('info', 'warn', 'error'):
            log.info('Ignoring bad kind parameter ({kind}), using "info" instead.')

        msg = self.var_in_text(message)

        msgbox = QMessageBox(self)
        msgbox.setWindowTitle(title)
        msgbox.setText(msg)
        msgbox.setStandardButtons(QMessageBox.StandardButton.Ok)
        if dialog_kind == 'info':
            msgbox.setIcon(QMessageBox.Icon.Information)
        elif dialog_kind == 'warn':
            msgbox.setIcon(QMessageBox.Icon.Warning)
        else:
            msgbox.setIcon(QMessageBox.Icon.Critical)

        msgbox.setStyleSheet("background-color: white; color: black;")
        msgbox.exec()

    def InputDialog(self, prompt: str, variable: str, title: str = '', default: str = ''):
        """
        This action causes GEMS to display an input dialog box containing the query <b><i>Prompt</i></b> and the
        title <b><i>Title</i></b>. The dialog box will remain until the user presses the SUBMIT button.
        The entered text will be associated with the user variable <b><i>Variable</i></b> and will be initialized
        with the default value of <b><i>Default</i></b>.
        :scope viewobjectglobalpocket
        :mtype action
        """
        log.info(dict(Kind='Action', Type='InputDialog', View=self.View.Name, **gu.func_params(), Target=None,
                      Result='Valid', TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))

        _prompt = self.var_in_text(prompt)
        _title = self.var_in_text(title)
        _default = self.var_in_text(default)

        dialog = QInputDialog(self)
        dialog.setWindowTitle(_title)
        dialog.setLabelText(_prompt)
        dialog.setTextValue(_default)
        dialog.setStyleSheet("background-color: white; color: black;")
        if dialog.exec():
            self.SetVariable(variable, dialog.textValue())

    def SayText(self, message: str):
        """
        This action causes GEMS to speak the given <b><i>Message</i></b> using the default Google Text-To-Speech voice.
        :scope viewobjectglobalpocket
        :mtype action
        """
        if not self.options.PlayMedia:
            log.warning("Media playback is not enabled.")
            return
        elif not self.options.TTSEnabled:
            log.warning("Text To Speech is not enabled.")
            return

        log.info(dict(Kind='Action', Type='SayText', View=self.View.Name, **gu.func_params(), Target=None,
                      Result='Valid', TimeTime=self.get_task_elapsed(), ViewTime=self.view_elapsed()))

        _text = self.var_in_text(message)  # convert any variable specifiers in the text

        speech_file = f'speech_{gu.string_hash(_text)}.mp3'
        speech_path = Path(self.options.TTSFolder, speech_file)

        if speech_path.is_file():
            log.debug(f'TTS resource already generated and in {str(speech_path)}!')
            try:
                self.play_sound(sound_file=str(speech_path))
            except Exception as e:
                log.error(f'Problem playing speech audio file called {str(speech_path)}: {e}')
        else:
            log.debug(f'TTS resource does not exist in {str(speech_path)}, will try to generate it using web.')
            try:
                tts = gTTS(_text)
            except Exception as e:
                log.error(f'Problem generating tts resource using gTTS web api: {e}')
                return
            try:
                tts.save(str(speech_path))
            except Exception as e:
                log.error(f'Unable to write to speech_path {str(speech_path)} ({e}), '
                          f'will just create a temporary file.')
                speech_path = tempfile.TemporaryFile()
                tts.save(str(speech_path))
        try:
            self.play_sound(sound_file=str(speech_path))
        except Exception as e:
            log.error(f'Problem playing speech audio file called {str(speech_path)}: {e}')

    def HidePockets(self):
        """
        This action hides all active pockets.
        :scope viewobjectglobalpocket
        :mtype action
        """
        for pocket_pic in self.parent().pocket_objects:
            self.parent().pocket_objects[pocket_pic].hide()

    def ShowPockets(self):
        """
        This action unhides all active pockets, assuming they are currently hidden.
        :scope viewobjectglobalpocket
        :mtype action
        """
        for pocket_pic in self.parent().pocket_objects:
            self.parent().pocket_objects[pocket_pic].show()


# fmt: on
