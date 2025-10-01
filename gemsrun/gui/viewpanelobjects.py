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

from pathlib import Path
from typing import List, Union

from PySide6.QtCore import (
    QObject,
    QEvent,
    QSize,
    QRect,
    Qt,
    QMimeData,
    Slot,
    QPoint,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QPixmap,
    QPainter,
    QColor,
    QMouseEvent,
    QDrag,
    QDragEnterEvent,
    QDropEvent,
    QImage,
    QCloseEvent,
    QMovie,
    QCursor,
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QLabel


from munch import Munch
from gemsrun.gui.viewpanelutils import pixmap_to_pointer
from gemsrun.utils import gemsutils as gu
from gemsrun import log


class HoverTracker(QObject):
    """
    Adds ability to fire an event when you are hovering over an object
    """

    hover_event = Signal(int)

    def __init__(self, widget):
        super().__init__(widget)
        self._widget = widget
        self.widget.setMouseTracking(True)
        self.widget.installEventFilter(self)

    @property
    def widget(self):
        return self._widget

    def eventFilter(self, obj, event):
        if obj is self.widget and event.type() in (
            QEvent.Type.HoverEnter,
            QEvent.Type.HoverLeave,
        ):
            self.hover_event.emit(event.type())
        return super().eventFilter(obj, event)


class ViewImageObject(QLabel):
    """
    Modified QLabel used to represent a gems view object
    Assumes parent is ViewPanel instance
    """

    def __init__(self, parent, obj_id: int, pixmap: QPixmap, scale: List[float]):
        super(ViewImageObject, self).__init__(parent=parent)
        self.db: Munch = self.parent().db
        self.object: Munch = self.db.Views[str(self.parent().view_id)].Objects[str(obj_id)]
        self.show_name: bool = False  # would ALWAYS show name. For debug?
        self.show_bounds: bool = False  # would ALWAYS show bounds. For debug?
        self.scale = scale

        self.setVisible(self.object.Visible)

        self.setPixmap(pixmap)
        self.pixmax_size = QSize(pixmap.width(), pixmap.height())

        self.hover_tracker = HoverTracker(self)
        self.hover_tracker.hover_event.connect(self.on_hover_change)
        self.hovered = False

        self.setAcceptDrops(True)

        style_sheet = ""
        if self.show_bounds:
            style_sheet += "QLabel{border : 4px solid yellow;} "
        if "Frame" in self.db.Global.Options.ObjectHover:
            style_sheet += "QLabel::hover{border : 4px yellow; border-style : dotted;} "

        if style_sheet:
            self.setStyleSheet(style_sheet)
            log.debug(f"{style_sheet=}")

        if "Cursor" in self.db.Global.Options.ObjectHover:
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def paintEvent(self, event):
        super(ViewImageObject, self).paintEvent(event)
        painter = QPainter(self)

        def show_name():
            name_rect = QRect(
                0,
                0,
                painter.fontMetrics().horizontalAdvance(self.object.Name) + 1,
                painter.fontMetrics().height() + 1,
            )
            painter.setPen(QColor("black"))
            painter.fillRect(name_rect, QColor("yellow"))
            painter.drawText(name_rect, Qt.AlignmentFlag.AlignLeft, self.object.Name)

        def show_frame():
            x, y, w, h = self.rect().getCoords()
            painter.setPen(QColor("yellow"))
            painter.drawRect(QRect(x, y, w - 1, h - 1))

        if not self.hovered:
            if self.show_name:
                show_frame()
            if self.show_bounds:
                show_frame()
        else:
            if "Name" in self.db.Global.Options.ObjectHover:
                show_name()
            if "Frame" in self.db.Global.Options.ObjectHover:
                show_frame()

    def mouseMoveEvent(self, ev: QMouseEvent) -> None:
        if ev.buttons() != Qt.MouseButton.LeftButton or not self.object.Draggable:
            return

        mimeData = QMimeData()
        mimeData.setText(f"{self.object.Name}|{self.parent().view_id}|{self.object.Id}")

        drag = QDrag(self)
        drag.setMimeData(mimeData)
        drag.setDragCursor(
            pixmap_to_pointer(self.pixmap(), 100, 100, keep_aspect_ratio=True),
            Qt.DropAction.MoveAction,
        )
        # drag.setDragCursor(self.pixmap().scaled(QSize(100, 100), Qt.KeepAspectRatio), Qt.MoveAction)
        drag.setHotSpot(ev.pos() - self.rect().topLeft())

        _ = drag.exec(Qt.DropAction.MoveAction)  # required

        ev.accept()

    def dragEnterEvent(self, ev: QDragEnterEvent) -> None:
        if self.isHidden():
            ev.ignore()
        else:
            if self.parent().dragging_object is None:
                self.parent().dragging_object = self
                self.hide()

            ev.accept()

    def dropEvent(self, ev: QDropEvent) -> None:
        source_object_info = ev.mimeData().text()
        source_object_name, source_view_id, source_object_id = source_object_info.split("|")
        if int(source_object_id) == self.object.Id:
            # erroneously picking up us dropping onto ourselves!
            ev.ignore()
        else:
            log.info(
                dict(
                    Kind="Mouse",
                    Type="DropObject",
                    View=self.parent().View.Name,
                    Target=f"{source_object_name}->{self.object.Name}",
                    Result="Success",
                    TimeTime=self.parent().get_task_elapsed(),
                    ViewTime=self.parent().view_elapsed(),
                )
            )

            self.parent().dragging_object.show()
            self.parent().dragging_object = None

            self.parent().handle_object_drop(
                source_id=source_object_id,
                source_view_id=source_view_id,
                target_id=self.object.Id,
            )

            ev.accept()

    def mousePressEvent(self, ev: QMouseEvent) -> None:
        super().mousePressEvent(ev)

        if ev.buttons() == Qt.MouseButton.LeftButton:
            log.info(
                dict(
                    Kind="Mouse",
                    Type="LeftClick",
                    View=self.parent().View.Name,
                    Target=self.object.Name,
                    Result="Success",
                    TimeTime=self.parent().get_task_elapsed(),
                    ViewTime=self.parent().view_elapsed(),
                )
            )

            for action in self.object.Actions.values():
                if action.Enabled and action.Trigger == "MouseClick()":
                    self.parent().do_action(action.Condition, action.Action)

    @Slot(int)
    def on_hover_change(self, evt):
        if self.parent().dragging_object:
            return

        if evt == QEvent.Type.HoverEnter:
            self.hovered = True

            log.info(
                dict(
                    Kind="Mouse",
                    Type="MoveOnto",
                    View=self.parent().View.Name,
                    Target=self.object.Name,
                    Result="Success",
                    TimeTime=self.parent().get_task_elapsed(),
                    ViewTime=self.parent().view_elapsed(),
                )
            )

            # TODO: add action trigger for "MouseHover()" to editor!
            for action in self.object.Actions.values():
                if action.Enabled and action.Trigger == "MouseHover()":
                    self.parent().do_action(action.Condition, action.Action)

        elif evt == QEvent.Type.HoverLeave:
            self.hovered = False

            log.info(
                dict(
                    Kind="Mouse",
                    Type="MoveOff",
                    View=self.parent().View.Name,
                    Target=self.object.Name,
                    Result="Success",
                    TimeTime=self.parent().get_task_elapsed(),
                    ViewTime=self.parent().view_elapsed(),
                )
            )


class ViewPocketObject(QLabel):
    """
    Modified QLabel used to represent a gems pocket object
    Assumes parent is ViewPanel instance
    """

    def __init__(self, parent, pocket_id: int):
        super(ViewPocketObject, self).__init__(parent=parent)
        self.db: Munch = self.parent().db
        self.object_info: Munch = Munch({"name": "", "view_id": -1, "Id": -1, "image": None})
        self.pocket_id: int = pocket_id
        self.pocket_image: QPixmap = QPixmap()
        self.init_pocket_image()
        self.setAcceptDrops(True)

    def init_pocket_image(self):
        if not self.object_info.image:
            bitmap = self.parent().pocket_bitmap
            self.pocket_image = QPixmap().fromImage(bitmap)
            self.object_info.image = bitmap
        else:
            self.pocket_image = QPixmap().fromImage(self.object_info.image)
        self.setPixmap(self.pocket_image)
        self.move(
            QPoint(
                self.pocket_image.width() * self.pocket_id + 5,
                self.parent().height() - self.pocket_image.height() - 5,
            )
        )

    # def paintEvent(self, event):
    #     super(ViewPocketObject, self).paintEvent(event)
    #     painter = QPainter(self)
    #
    #     if self.show_name:
    #         name_rect = QRect(0, 0,
    #                           painter.fontMetrics().width(self.object.Name) + 1,
    #                           painter.fontMetrics().height() + 1)
    #         painter.setPen(QColor('black'))
    #         painter.fillRect(name_rect, QColor('yellow'))
    #         painter.drawText(name_rect, Qt.AlignLeft, self.object.Name)

    """
        self.dragging = False  # True if were currently in a drag
        self.dragging_icon = None
        self.dragging_object = None  # Object we're currently dragging from
        self.drag_object_bitmap = None  # Hold drag object bitmap whilst dragging..avoids re-lookup
    """

    def mouseMoveEvent(self, ev: QMouseEvent) -> None:
        # can't drag from pocket if it's empty!
        if not self.object_info or not self.object_info.name:
            return

        # create mime data to send to ViewImageObject that this pocket object is dropped on
        mimeData = QMimeData()
        mimeData.setText(f"{self.object_info.name}|{self.object_info.view_id}|{self.object_info.Id}")
        drag = QDrag(self)
        drag.setMimeData(mimeData)

        # set cursor to current pixmap which should be the pixmap of the object currently in this pocket
        drag.setDragCursor(
            pixmap_to_pointer(self.pixmap(), 100, 90, keep_aspect_ratio=True),
            Qt.DropAction.MoveAction,
        )
        drag.setHotSpot(ev.pos() - self.rect().topLeft())

        _ = drag.exec(Qt.DropAction.MoveAction)  # required

    def dragEnterEvent(self, ev: QDragEnterEvent) -> None:
        if self.isHidden():
            ev.ignore()
        else:
            if self.parent().dragging_object is None:
                self.parent().dragging_object = self
                self.hide()
            ev.accept()

    def dropEvent(self, ev: QDropEvent) -> None:
        source_object_info = ev.mimeData().text()
        source_object_name, source_view_id, source_object_id = source_object_info.split("|")

        if self.object_info.Id >= 0:
            if int(source_object_id) == self.object_info.Id:
                # erroneously picking up us dropping onto ourselves!
                ev.ignore()
            else:
                # dragged view object onto non-empty pocket, just stop drag
                log.debug(f'"{source_object_name}" was dropped on non-empty Pocket #"{self.pocket_id}"')

                log.info(
                    dict(
                        Kind="Mouse",
                        Type="NonEmptyPocketDrop",
                        View=self.parent().View.Name,
                        Target=f"Pocket{self.pocket_id}",
                        Result="Fail",
                        TimeTime=self.parent().get_task_elapsed(),
                        ViewTime=self.parent().view_elapsed(),
                    )
                )

                self.parent().dragging_object.show()
                self.parent().dragging_object = None

                # self.parent().handle_object_drop(source_id=source_object_id, source_view_id=source_view_id,
                #                                  target_id=self.object.Id)

                ev.accept()

        elif int(source_object_id) in [
            value.object_info.Id for value in self.parent().parent().pocket_objects.values()
        ]:
            log.info(
                dict(
                    Kind="Mouse",
                    Type="PocketDragDrop",
                    View=self.parent().View.Name,
                    **gu.func_params(),
                    Source=source_object_id,
                    Target=self.parent().parent().pocket_objects[self.pocket_id].object_info.name,
                    Result="Invalid|ObjAlreadyInPocket",
                    TimeTime=self.parent().parent().task_elapsed(),
                    ViewTime=self.parent().view_elapsed(),
                )
            )

            self.parent().dragging = False
            if self.parent().dragging_object:
                self.parent().dragging_object.show()
            self.parent().dragging_object = None

            ev.accept()
        else:
            # dragged view object onto empty pocket!
            log.debug(f'"{source_object_name}" was dropped on empty Pocket #"{self.pocket_id}"')

            log.info(
                dict(
                    Kind="Mouse",
                    Type="EmptyPocketDrop",
                    View=self.parent().View.Name,
                    Target=f"Pocket{self.pocket_id}",
                    Result="Success",
                    TimeTime=self.parent().get_task_elapsed(),
                    ViewTime=self.parent().view_elapsed(),
                )
            )

            self.object_info = Munch(
                {
                    "name": source_object_name,
                    "view_id": int(source_view_id),
                    "Id": int(source_object_id),
                    "image": pixmap_to_pointer(
                        self.parent().dragging_object.pixmap().copy(),
                        100,
                        90,
                        keep_aspect_ratio=False,
                    ).toImage(),
                }
            )
            self.init_pocket_image()

            self.parent().dragging_object = None

            # self.parent().handle_object_drop(source_id=source_object_id, source_view_id=source_view_id,
            #                                  target_id=self.object.Id)

            self.parent().handle_pocket_drop(dropped_object_id=source_object_id, pocket_id=self.pocket_id)

            ev.accept()

    def mousePressEvent(self, ev: QMouseEvent) -> None:
        super().mousePressEvent(ev)

        if ev.buttons() == Qt.MouseButton.LeftButton:
            log.debug(f'"Pocket object {self.object_info.name}" left-clicked!')

            # TODO: shouldn't we turn this on...do we want to handle object clicks from the pocket?
            #       NO -- Maybe later
            # for action in self.object.Actions.values():
            #     if action.Enabled and action.Trigger == 'MouseClick()':
            #         self.parent().do_action(action.Condition, action.Action)

            if not self.object_info or not self.object_info.name:
                log.info(
                    dict(
                        Kind="Mouse",
                        Type="PocketOjbectLeftClick",
                        View=self.parent().View.Name,
                        Target=self.object_info.name,
                        Result="Invalid|EmptyPocket",
                        TimeTime=self.parent().get_task_elapsed(),
                        ViewTime=self.parent().view_elapsed(),
                    )
                )
            else:
                log.info(
                    dict(
                        Kind="Mouse",
                        Type="PocketObjectLeftClick",
                        View=self.parent().View.Name,
                        Target=self.object_info.name,
                        Result="Success",
                        TimeTime=self.parent().get_task_elapsed(),
                        ViewTime=self.parent().view_elapsed(),
                    )
                )

        elif ev.buttons() == Qt.MouseButton.RightButton:
            log.debug(f'"Pocket object {self.object_info.name}" right-clicked!')

            if not self.object_info or not self.object_info.name:
                log.info(
                    dict(
                        Kind="Mouse",
                        Type="PocketObjectRightClick",
                        View=self.parent().View.Name,
                        Target=self.object_info.name,
                        Result="Invalid|EmptyPocket",
                        TimeTime=self.parent().get_task_elapsed(),
                        ViewTime=self.parent().view_elapsed(),
                    )
                )
            else:
                log.info(
                    dict(
                        Kind="Mouse",
                        Type="PocketObjectRightClick",
                        View=self.parent().View.Name,
                        Target=self.object_info.name,
                        Result="Success",
                        TimeTime=self.parent().get_task_elapsed(),
                        ViewTime=self.parent().view_elapsed(),
                    )
                )

                self.parent().handle_pocket_right_click(pocket_id=self.pocket_id)


class NavImageObject(QLabel):
    """
    Modified QLabel used to represent a gems navigation area
    Assumes parent is ViewPanel instance
    """

    def __init__(self, parent, nav_type: str, nav_actions: list, nav_image_folder: Path):
        super(NavImageObject, self).__init__(parent=parent)
        self.nav_type: str = nav_type
        self.nav_actions: list = nav_actions

        file_codex = dict(
            zip(
                ("NavTop", "NavBottom", "NavLeft", "NavRight"),
                ("nav_top.png", "nav_bottom.png", "nav_left.png", "nav_right.png"),
            )
        )

        width, height = self.parent().width(), self.parent().height()
        extent = self.parent().nav_extent

        size_codex = dict(
            zip(
                ("NavTop", "NavBottom", "NavLeft", "NavRight"),
                (
                    QSize(width, extent),
                    QSize(width, extent),
                    QSize(extent, height),
                    QSize(extent, height),
                ),
            )
        )

        style_sheet = "QLabel{background-color: rgba(0,0,0,0%)} "  # transparent background

        img_file = Path(nav_image_folder, file_codex[nav_type]).resolve()
        log.warning(f'{img_file=}')
        try:
            image = QImage(str(img_file))
            self.setFixedSize(image.width(), image.height())
            style_sheet += "QLabel::hover {background-image: url(" + str(img_file) + ");}"
        except IndexError:
            self.parent().fail_dialog(
                "Unexpected Nav Type",
                f"Attempting to create navigation area with unexpected type of "
                f'"{self.nav_type}". Should be in (NavTop, NavBottom, NavLeft, and NavRight).',
            )
        except FileNotFoundError:
            log.warning(f"Unable to locate or open nav image file {str(img_file)}.")
            self.setFixedSize(size_codex[self.nav_type])
            style_sheet += "QLabel::hover{border : 4px yellow; border-style : dotted;}"

        self.setStyleSheet(style_sheet)

    def mousePressEvent(self, ev: QMouseEvent) -> None:
        super().mousePressEvent(ev)

        if ev.buttons() == Qt.MouseButton.LeftButton:
            log.info(
                dict(
                    Kind="Mouse",
                    Type=f"{self.nav_type}Pressed",
                    View=self.parent().View.Name,
                    Target=None,
                    Result="Success",
                    TimeTime=self.parent().get_task_elapsed(),
                    ViewTime=self.parent().view_elapsed(),
                )
            )

            for action in self.nav_actions:
                if action.Enabled:
                    self.parent().do_action(action.Condition, action.Action)


class TextBoxObject(QLabel):
    """
    Modified QLabel used to represent a text box object
    Assumes parent is ViewPanel instance
    """

    def __init__(
        self,
        parent,
        message: str,
        left: int = 0,
        top: int = 0,
        duration: float = 0.0,
        fg_color: list = (255, 255, 255, 255),
        bg_color: list = (0, 0, 0, 255),
        font_size: int = 12,
        bold: bool = False,
    ):
        try:
            super(TextBoxObject, self).__init__(parent=parent)
        except RuntimeError:
            # Note: Here because I'm sometimes getting this:
            #       RuntimeError: wrapped C/C++ object of type ViewPanel has been deleted
            super(TextBoxObject, self).__init__()
        style_sheet = "QLabel{ "
        style_sheet += f"color: rgba{tuple(fg_color)}; "
        style_sheet += f"background-color: rgba{tuple(bg_color)}; "
        style_sheet += f"font-size: {font_size}px; "
        style_sheet += f"max-width: {self.parent().width() if hasattr(self.parent(), 'width') else 640}px; "
        style_sheet += f"max-height: {self.parent().height() if hasattr(self.parent(), 'height') else 480}px; "
        style_sheet += "padding: 2px; "
        style_sheet += "position: absolute; "
        if bold:
            style_sheet += "font-style: bold"
        style_sheet += " }"
        self.setStyleSheet(style_sheet)

        self.setWordWrap(True)
        self.setText(message)

        self.move(left, top)

        if duration:
            QTimer.singleShot(
                int(duration * 1000), 
                self, 
                self.hide_me
            )

    def hide_me(self):
        try:
            self.hide()
        except:
            ...


class ExternalImageObject(QLabel):
    """
    Modified QLabel used to display an external image
    Assumes parent is ViewPanel instance
    """

    def __init__(
        self,
        parent,
        image_path: Path,
        left: int = 0,
        top: int = 0,
        duration: float = 0.0,
        click_through: bool = False,
        scale: Union[tuple, list] = (1.0, 1.0),
    ):
        super(ExternalImageObject, self).__init__(parent=parent)
        self.file_name = Path(image_path).name

        style_sheet = "QLabel{ "
        # style_sheet += "background-image: url(" + str(image_path.resolve()) + ");"
        style_sheet += "background-color: rgba(0,0,0,0%); "
        style_sheet += "position: absolute; "
        style_sheet += " }"

        # handle image transparency
        self.setStyleSheet(style_sheet)

        if click_through:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        pixmap = QPixmap(str(image_path.resolve()))

        x_ratio, y_ratio = scale
        pixmap = pixmap.scaled(
            int(pixmap.width() * x_ratio),
            int(pixmap.height() * y_ratio),
            Qt.AspectRatioMode.KeepAspectRatio,
        )

        self.setPixmap(pixmap)
        self.setFixedSize(pixmap.width(), pixmap.height())

        self.move(left, top)

        if duration:
            QTimer.singleShot(
                int(duration * 1000), 
                self, 
                self.hide
            )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        super(ExternalImageObject, self).mousePressEvent(event)
        if event.buttons():
            log.debug(f"external image mouse press event received: {event.buttons()}")

            log.info(
                dict(
                    Kind="Mouse",
                    Type="ExternalImagePressed",
                    View=self.parent().View.Name,
                    Target=self.file_name,
                    Result="Success",
                    TimeTime=self.parent().get_task_elapsed(),
                    ViewTime=self.parent().view_elapsed(),
                )
            )


class VideoObject(QVideoWidget):
    """
    Modified QVideoWidget used to display a video
    Assumes parent is ViewPanel instance
    """

    def __init__(
        self,
        parent,
        video_path: Path,
        pos: QPoint,
        size: QSize,
        start: int = 0,
        volume: float = 1.0,
        loop: bool = False,
    ):
        super(VideoObject, self).__init__(parent=parent)
        self.video_path: Path = video_path
        self.player = None
        self.audio_output = None
        self.fallback_mode = False

        if loop:
            log.warning(
                'In the VideoObject class (created in PlayVideo() action) the "loop" parameter '
                "is not currently implemented"
            )

        style_sheet = "QVideoWidget{ "
        style_sheet += "background-color: rgba(0,0,0,0%); "
        # style_sheet += "position: absolute; "
        style_sheet += " }"
        self.setStyleSheet(style_sheet)

        # Try to create QMediaPlayer with error handling
        try:
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
            
            url = QUrl.fromLocalFile(str(video_path.absolute()))
            
            self.player = QMediaPlayer(self.parent())
            self.player.setSource(url)
            self.player.setVideoOutput(self)
            self.player.setPosition(start)
            
            # Test audio output availability
            self.audio_output = QAudioOutput()
            if self.audio_output.isAvailable():
                self.player.setAudioOutput(self.audio_output)
                self.audio_output.setVolume(volume * 100)
                log.debug("Video audio output initialized successfully")
            else:
                log.warning("Audio output not available for video playback")
                self.fallback_mode = True
                
        except Exception as e:
            log.error(f"Failed to initialize video player: {e}")
            log.info("Video playback will be attempted with limited functionality")
            self.fallback_mode = True

        if size:
            self.setFixedSize(size)
        else:
            self.setFixedSize(self.parent().size())

        self.move(pos)
        self.show()
        self.activateWindow()
        self.raise_()
        
        # Only attempt to play if we have a working player
        if self.player and not self.fallback_mode:
            self.play()
        else:
            log.warning(f"Video {video_path.name} could not be played due to multimedia backend issues")

    def play(self):
        if self.player and not self.fallback_mode:
            try:
                self.player.play()
            except Exception as e:
                log.error(f"Error playing video: {e}")
        else:
            log.warning("Video player not available or in fallback mode")

    def pause(self):
        if self.player and not self.fallback_mode:
            try:
                self.player.pause()
            except Exception as e:
                log.error(f"Error pausing video: {e}")
        else:
            log.warning("Video player not available or in fallback mode")

    def stop(self):
        if self.player and not self.fallback_mode:
            try:
                self.player.stop()
            except Exception as e:
                log.error(f"Error stopping video: {e}")
        else:
            log.warning("Video player not available or in fallback mode")

    def closeEvent(self, event: QCloseEvent) -> None:
        self.stop()
        event.accept()

    def mousePressEvent(self, ev: QMouseEvent) -> None:
        super().mousePressEvent(ev)

        if ev.buttons() == Qt.MouseButton.RightButton:
            log.debug(f'Movie "{self.video_path.name}" closed manually via right-click.')

            log.info(
                dict(
                    Kind="Mouse",
                    Type="StopVideoObject",
                    View=self.parent().View.Name,
                    Target=self.video_path.name,
                    Result="Success",
                    TimeTime=self.parent().get_task_elapsed(),
                    ViewTime=self.parent().view_elapsed(),
                )
            )

            self.stop()
            self.close()


class AnimationObject(QLabel):
    """
    Modified QLabel used to display a gif animation
    Assumes parent is ViewPanel instance
    """

    def __init__(
        self,
        parent,
        video_path: Path,
        pos: QPoint,
        size: QSize,
        start: int = 0,
        volume: float = 1.0,
        loop: bool = False,
    ):
        super(AnimationObject, self).__init__(parent=parent)
        self.video_path: Path = video_path

        style_sheet = "QLabel{ "
        style_sheet += "background-color: rgba(0,0,0,0%); "
        # style_sheet += "position: absolute; "
        style_sheet += " }"
        self.setStyleSheet(style_sheet)

        self.setScaledContents(True)
        self.movie = QMovie(str(video_path.absolute()), parent=self)
        self.setMovie(self.movie)

        if size:
            self.setFixedSize(size)
        else:
            self.setFixedSize(self.parent().size())

        self.move(pos)
        self.show()
        self.play()
        self.activateWindow()
        self.raise_()

    def play(self):
        try:
            self.movie.start()
        except:
            pass

    def pause(self):
        try:
            self.movie.stop()
        except:
            pass

    def stop(self):
        try:
            self.movie.stop()
        except:
            pass

    def closeEvent(self, event: QCloseEvent) -> None:
        self.stop()
        event.accept()

    def mousePressEvent(self, ev: QMouseEvent) -> None:
        super().mousePressEvent(ev)

        if ev.buttons() == Qt.MouseButton.RightButton:
            log.debug(f'Movie "{self.video_path.name}" closed manually via right-click.')

            log.info(
                dict(
                    Kind="Mouse",
                    Type="StopAnimationObject",
                    View=self.parent().View.Name,
                    Target=self.video_path.name,
                    Result="Success",
                    TimeTime=self.parent().get_task_elapsed(),
                    ViewTime=self.parent().view_elapsed(),
                )
            )

            self.stop()
            self.close()
