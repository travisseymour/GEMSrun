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

import contextlib
from pathlib import Path
from typing import TYPE_CHECKING

from munch import Munch
from PySide6.QtCore import (
    QEvent,
    QMimeData,
    QObject,
    QPoint,
    QRect,
    QSize,
    Qt,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QCursor,
    QDrag,
    QDragEnterEvent,
    QDropEvent,
    QImage,
    QMouseEvent,
    QMovie,
    QPainter,
    QPainterPath,
    QPixmap,
    QPolygon,
    QRegion,
)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QLabel

from gemsrun import log
from gemsrun.gui.viewpanelutils import (
    drag_pixmap_with_hand,
    get_custom_cursors,
    pixmap_to_pointer,
)
from gemsrun.utils import gemsutils as gu

if TYPE_CHECKING:  # Avoid circular import at runtime
    from .viewpanel import ViewPanel


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

    def __init__(
        self,
        parent: ViewPanel,
        obj_id: int,
        pixmap: QPixmap,
        scale: list[float],
        polygon_points: list | None = None,
    ):
        super().__init__(parent=parent)
        self.db: Munch = self.parent().db
        self.object: Munch = self.db.Views[str(self.parent().view_id)].Objects[str(obj_id)]
        # Enable debug visualization based on Debug option
        debug_mode = getattr(self.db.Global.Options, "Debug", False)
        self.show_name: bool = bool(debug_mode)
        self.show_bounds: bool = bool(debug_mode)
        self.scale = scale
        self.polygon_points = polygon_points or []
        self._mask_needs_update = bool(self.polygon_points)  # Flag for deferred mask setup

        # Check if this is an invisible object with click actions (hotspot)
        has_click_action = any(
            action.Enabled and action.Trigger == "MouseClick()" for action in self.object.Actions.values()
        )

        # Always store the original pixmap for later restoration (e.g., pocket right-click)
        self._original_pixmap = pixmap

        if self.object.Visible:
            # Visible object - show normally
            self.setVisible(True)
            self.setPixmap(pixmap)
        elif has_click_action:
            # Invisible hotspot - keep widget visible but fully transparent
            self.setVisible(True)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setStyleSheet("background: transparent;")
            # Use a transparent pixmap
            transparent_pixmap = QPixmap(pixmap.size())
            transparent_pixmap.fill(QColor(0, 0, 0, 0))
            self.setPixmap(transparent_pixmap)
        else:
            # Invisible with no click action - hide completely
            self.setVisible(False)
            self.setPixmap(pixmap)
        self.pixmax_size = QSize(pixmap.width(), pixmap.height())

        # Note: Polygon mask is set in setGeometry() after geometry is established

        self.hover_tracker = HoverTracker(self)
        self.hover_tracker.hover_event.connect(self.on_hover_change)
        self.hovered = False

        self.setAcceptDrops(True)

        # Cursor behavior is opt-in via Global.Options.ObjectHover containing "Cursor"
        self.cursors_enabled = "Cursor" in self.db.Global.Options.ObjectHover
        if self.cursors_enabled:
            cursors = get_custom_cursors()
            self.arrow_cursor = cursors.get("arrow")
            self.open_hand_cursor = cursors.get("open_hand")
            self.pointing_cursor = cursors.get("pointing_hand")
            self._apply_hover_cursor()
        else:
            self.arrow_cursor = None
            self.open_hand_cursor = None
            self.pointing_cursor = None

        style_sheet = ""
        if self.show_bounds:
            style_sheet += "QLabel{border : 4px solid yellow;} "
        if "Frame" in self.db.Global.Options.ObjectHover:
            style_sheet += "QLabel::hover{border : 4px yellow; border-style : dotted;} "

        if style_sheet:
            self.setStyleSheet(style_sheet)

    def setGeometry(self, *args):
        """Override setGeometry to set polygon mask after geometry is established."""
        super().setGeometry(*args)
        # Now that geometry is set, apply the polygon mask if needed
        if self._mask_needs_update:
            self._set_polygon_mask()
            self._mask_needs_update = False

    def restore_visible(self):
        """Restore this object to its normal visible state.

        Used when an object is returned from a pocket. The widget may have been
        created with a transparent pixmap (invisible hotspot path) or hidden
        entirely, so we must restore the original pixmap and clear any
        transparency attributes before showing.
        """
        self.setPixmap(self._original_pixmap)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setVisible(True)
        self.update()

    def _set_polygon_mask(self):
        """Set a mask on the widget so only polygon area receives mouse events."""
        if not self.polygon_points:
            return

        # Get widget geometry to calculate local polygon coordinates
        geom = self.geometry()

        # Convert global polygon points to local widget coordinates
        local_points = [QPoint(p[0] - geom.x(), p[1] - geom.y()) for p in self.polygon_points]

        # Create polygon and region for masking
        polygon = QPolygon(local_points)
        region = QRegion(polygon)

        # Set the mask - only this region will receive mouse events
        self.setMask(region)

    def paintEvent(self, event):
        super().paintEvent(event)
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
            # Draw the actual polygon outline instead of a rectangle
            if self.polygon_points:
                geom = self.geometry()
                local_points = [QPoint(p[0] - geom.x(), p[1] - geom.y()) for p in self.polygon_points]
                polygon = QPolygon(local_points)
                painter.setPen(QColor("yellow"))
                painter.drawPolygon(polygon)
            else:
                # Fallback to rectangle if no polygon points
                r = self.rect()
                painter.setPen(QColor("yellow"))
                painter.drawRect(QRect(r.left(), r.top(), r.width() - 1, r.height() - 1))

        # In debug mode (show_name/show_bounds True), always draw
        # Otherwise, only draw on hover if ObjectHover options specify
        if self.show_name or (self.hovered and "Name" in self.db.Global.Options.ObjectHover):
            show_name()
        if self.show_bounds or (self.hovered and "Frame" in self.db.Global.Options.ObjectHover):
            show_frame()

    def _create_polygon_clipped_pixmap(self, source: QPixmap) -> QPixmap:
        """Create a polygon-clipped version of the source pixmap with transparency outside the polygon."""
        if not self.polygon_points or source.isNull():
            return source

        # Create result pixmap with transparency
        result = QPixmap(source.size())
        result.fill(QColor(0, 0, 0, 0))

        # Convert global polygon points to local widget coordinates
        geom = self.geometry()
        local_points = [[p[0] - geom.x(), p[1] - geom.y()] for p in self.polygon_points]

        # Create painter path for clipping
        path = QPainterPath()
        if local_points:
            path.moveTo(local_points[0][0], local_points[0][1])
            for p in local_points[1:]:
                path.lineTo(p[0], p[1])
            path.closeSubpath()

        # Draw source pixmap clipped to polygon
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, source)
        painter.end()

        return result

    def mouseMoveEvent(self, ev: QMouseEvent) -> None:
        if ev.buttons() != Qt.MouseButton.LeftButton or not self.object.Draggable:
            return

        mime_data = QMimeData()
        mime_data.setText(f"{self.object.Name}|{self.parent().view_id}|{self.object.Id}")

        drag = QDrag(self)
        drag.setMimeData(mime_data)
        hotspot = ev.pos() - self.rect().topLeft()

        # Get base pixmap and apply polygon clipping for non-rectangular objects
        base_pixmap = self.pixmap()
        if self.polygon_points:
            base_pixmap = self._create_polygon_clipped_pixmap(base_pixmap)

        # scale drag image to ~95% of pocket size for easier drops
        pocket = getattr(self.parent(), "pocket_bitmap", None)
        if pocket and not base_pixmap.isNull():
            target_w = int(pocket.width() * 0.95)
            target_h = int(pocket.height() * 0.95)
            ratio = min(target_w / base_pixmap.width(), target_h / base_pixmap.height())
            ratio = ratio if ratio > 0 else 1.0
            base_pixmap = base_pixmap.scaled(
                int(base_pixmap.width() * ratio),
                int(base_pixmap.height() * ratio),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            hotspot = QPoint(int(hotspot.x() * ratio), int(hotspot.y() * ratio))

        drag.setDragCursor(
            drag_pixmap_with_hand(base_pixmap, hotspot),
            Qt.DropAction.MoveAction,
        )
        drag.setHotSpot(hotspot)
        self.parent().drag_object_bitmap = base_pixmap.copy()
        if self.cursors_enabled and self.open_hand_cursor:
            self.setCursor(self.open_hand_cursor)

        _ = drag.exec(Qt.DropAction.MoveAction)  # required
        self._apply_cursor_after_drag()

        ev.accept()

    def dragEnterEvent(self, ev: QDragEnterEvent) -> None:
        if self.isHidden():
            ev.ignore()
        else:
            # Only hide ourselves if WE are the object being dragged.
            # When dragging from a pocket, dragging_object is never set by the
            # source, so without this check every target object would hide itself.
            if self.parent().dragging_object is None:
                try:
                    _, _, source_object_id = ev.mimeData().text().split("|")
                    if int(source_object_id) == self.object.Id:
                        self.parent().dragging_object = self
                        self.hide()
                except (ValueError, AttributeError):
                    pass

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

            if self.parent().dragging_object:
                self.parent().dragging_object.show()
            self.parent().dragging_object = None
            self.parent().drag_object_bitmap = None  # Clear the stored bitmap

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

            # Sort by RowOrder for predictable execution order
            for action in sorted(self.object.Actions.values(), key=lambda a: a.RowOrder):
                if action.Enabled and action.Trigger == "MouseClick()":
                    self.parent().do_action(action.Condition, action.Action)

    @Slot(int)
    def on_hover_change(self, evt):
        if self.parent().dragging_object:
            return

        if evt == QEvent.Type.HoverEnter:
            self.hovered = True

            self._apply_hover_cursor()
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
            # Sort by RowOrder for predictable execution order
            for action in sorted(self.object.Actions.values(), key=lambda a: a.RowOrder):
                if action.Enabled and action.Trigger == "MouseHover()":
                    self.parent().do_action(action.Condition, action.Action)

        elif evt == QEvent.Type.HoverLeave:
            self.hovered = False

            self._apply_hover_cursor()
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

    def _apply_hover_cursor(self):
        # Priority: clickable -> pointing hand; draggable -> open hand; otherwise arrow
        if not self.cursors_enabled:
            return
        is_clickable = any(
            action.Enabled and action.Trigger == "MouseClick()" for action in self.object.Actions.values()
        )
        if is_clickable and self.pointing_cursor:
            self.setCursor(self.pointing_cursor)
        elif self.object.Draggable and self.open_hand_cursor:
            self.setCursor(self.open_hand_cursor)
        elif self.arrow_cursor:
            self.setCursor(self.arrow_cursor)
        else:
            self.unsetCursor()

    def _apply_cursor_after_drag(self):
        # If we're still hovering over this object, apply hover cursor rules; else clear to default
        pos_local = self.mapFromGlobal(QCursor.pos())
        if self.rect().contains(pos_local):
            self._apply_hover_cursor()
        else:
            if self.cursors_enabled and self.arrow_cursor:
                self.setCursor(self.arrow_cursor)
            else:
                self.unsetCursor()


class ViewPocketObject(QLabel):
    """
    Modified QLabel used to represent a gems pocket object
    Assumes parent is ViewPanel instance
    """

    def __init__(self, parent: ViewPanel, pocket_id: int):
        super().__init__(parent=parent)
        self.db: Munch = self.parent().db
        self.object_info: Munch = Munch({"name": "", "view_id": -1, "Id": -1, "image": None})
        self.pocket_id: int = pocket_id
        self.pocket_image: QPixmap = QPixmap()
        self.pocket_adjust_timer: QTimer = QTimer(self)
        cursors = get_custom_cursors()
        self.open_hand_cursor = cursors.get("open_hand")
        self.arrow_cursor = cursors.get("arrow")
        self.init_pocket_image()
        self.setAcceptDrops(True)
        self._apply_cursor()

    def init_pocket_image(self):
        # Get the empty pocket background - make a copy to avoid modifying cached version
        pocket_bg = self.parent().pocket_bitmap
        if pocket_bg is None:
            return

        if not self.object_info.image or self.object_info.name == "":
            # Empty pocket - just show the pocket background
            self.pocket_image = QPixmap.fromImage(pocket_bg.copy())
            self.object_info.image = pocket_bg.copy()  # Store a copy, not reference to cached image
        else:
            # Pocket has an object - composite object image on top of pocket background
            # This ensures transparent areas of polygon objects show the pocket background
            # Use copy() to ensure we have our own pixmap to draw on
            self.pocket_image = QPixmap.fromImage(pocket_bg.copy())
            object_pixmap = QPixmap.fromImage(self.object_info.image)

            # Center the object image on the pocket background
            painter = QPainter(self.pocket_image)
            x_offset = (self.pocket_image.width() - object_pixmap.width()) // 2
            y_offset = (self.pocket_image.height() - object_pixmap.height()) // 2
            painter.drawPixmap(x_offset, y_offset, object_pixmap)
            painter.end()

        self.setPixmap(self.pocket_image)
        self.show()

        # make sure pockets stay at the bottom of the view
        self.position_pockets()
        self.pocket_adjust_timer.start()
        self._apply_cursor()

    def position_pockets(self):
        self.move(
            QPoint(
                self.pocket_image.width() * self.pocket_id + 5,
                self.parent().height() - self.pocket_image.height() - 5,
            )
        )

    def _create_polygon_clipped_pixmap(self, source: QPixmap, polygon_points: list, geometry: QRect) -> QPixmap:
        """Create a polygon-clipped version of the source pixmap with transparency outside the polygon."""
        if not polygon_points or source.isNull():
            return source

        # Create result pixmap with transparency
        result = QPixmap(source.size())
        result.fill(QColor(0, 0, 0, 0))

        # Convert global polygon points to local widget coordinates
        local_points = [[p[0] - geometry.x(), p[1] - geometry.y()] for p in polygon_points]

        # Create painter path for clipping
        path = QPainterPath()
        if local_points:
            path.moveTo(local_points[0][0], local_points[0][1])
            for p in local_points[1:]:
                path.lineTo(p[0], p[1])
            path.closeSubpath()

        # Draw source pixmap clipped to polygon
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, source)
        painter.end()

        return result

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
        mime_data = QMimeData()
        mime_data.setText(f"{self.object_info.name}|{self.object_info.view_id}|{self.object_info.Id}")
        drag = QDrag(self)
        drag.setMimeData(mime_data)

        # set cursor to current pixmap which should be the pixmap of the object currently in this pocket
        hotspot = ev.pos() - self.rect().topLeft()
        base_pixmap = self.pixmap()
        pocket = getattr(self.parent(), "pocket_bitmap", None)
        if pocket and not base_pixmap.isNull():
            target_w = int(pocket.width() * 0.95)
            target_h = int(pocket.height() * 0.95)
            ratio = min(target_w / base_pixmap.width(), target_h / base_pixmap.height())
            ratio = ratio if ratio > 0 else 1.0
            base_pixmap = base_pixmap.scaled(
                int(base_pixmap.width() * ratio),
                int(base_pixmap.height() * ratio),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            hotspot = QPoint(int(hotspot.x() * ratio), int(hotspot.y() * ratio))

        drag.setDragCursor(
            drag_pixmap_with_hand(base_pixmap, hotspot),
            Qt.DropAction.MoveAction,
        )
        drag.setHotSpot(hotspot)
        # cursor remains the default/arrow; drag icon handles the closed hand overlay
        self.parent().drag_object_bitmap = base_pixmap.copy()

        _ = drag.exec(Qt.DropAction.MoveAction)  # required
        self._apply_cursor()

    def _apply_cursor(self):
        is_empty = not self.object_info or not self.object_info.name
        if is_empty and self.arrow_cursor:
            self.setCursor(self.arrow_cursor)
        elif not is_empty and self.open_hand_cursor:
            self.setCursor(self.open_hand_cursor)
        elif self.arrow_cursor:
            self.setCursor(self.arrow_cursor)

    def dragEnterEvent(self, ev: QDragEnterEvent) -> None:
        if self.isHidden():
            ev.ignore()
        else:
            # Note: Unlike ViewImageObject, the pocket should NOT set itself as
            # the dragging_object. The pocket is a drop target, not a drag source.
            # The actual source object's dragEnterEvent sets dragging_object.
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

                if self.parent().dragging_object:
                    self.parent().dragging_object.show()
                self.parent().dragging_object = None
                self.parent().drag_object_bitmap = None  # Clear the stored bitmap

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
            self.parent().drag_object_bitmap = None  # Clear the stored bitmap

            ev.accept()
        else:
            # dragged view object onto empty pocket!
            log.debug(f'"{source_object_name}" was dropped on empty Pocket #"{self.pocket_id}"')

            current_view = self.parent().db.Views.get(str(self.parent().view_id))
            source_object = None
            if current_view:
                source_object = current_view.Objects.get(str(source_object_id))

            if source_object is None or not getattr(source_object, "Takeable", False):
                log.info(
                    dict(
                        Kind="Mouse",
                        Type="PocketDropNotTakeable",
                        View=self.parent().View.Name,
                        Target=source_object_name,
                        Result="Invalid|NotTakeable",
                        TimeTime=self.parent().get_task_elapsed(),
                        ViewTime=self.parent().view_elapsed(),
                    )
                )

                if self.parent().dragging_object:
                    self.parent().dragging_object.show()
                self.parent().dragging_object = None
                ev.ignore()
                return

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

            # Get the object image by looking up the source object directly.
            # We use the source_object_id from mime data to find the actual ViewImageObject
            # and get its pixmap. This is more reliable than relying on drag_object_bitmap
            # which may have parent/view issues.
            base_pixmap = None
            source_obj_id = int(source_object_id)

            # Try to get the pixmap from the source object in object_pics
            if source_obj_id in self.parent().object_pics:
                source_obj = self.parent().object_pics[source_obj_id]
                base_pixmap = source_obj.pixmap()
                if base_pixmap and not base_pixmap.isNull():
                    # Apply polygon clipping if the source has polygon points
                    polygon_points = getattr(source_obj, "polygon_points", [])
                    if polygon_points:
                        base_pixmap = source_obj._create_polygon_clipped_pixmap(base_pixmap)
                    base_pixmap = base_pixmap.copy()  # Ensure we have our own copy

            # Fallback to drag_object_bitmap if source object not found
            if base_pixmap is None or base_pixmap.isNull():
                base_pixmap = self.parent().drag_object_bitmap
                if base_pixmap is not None:
                    base_pixmap = base_pixmap.copy()  # Ensure we have our own copy

            # Final fallback to dragging_object
            if base_pixmap is None or base_pixmap.isNull():
                dragging_obj = self.parent().dragging_object
                if dragging_obj is not None:
                    base_pixmap = dragging_obj.pixmap().copy()

            if base_pixmap is not None and not base_pixmap.isNull():
                object_image = pixmap_to_pointer(base_pixmap, 100, 90, keep_aspect_ratio=False).toImage()
            else:
                # Last resort: create empty image
                object_image = QImage()

            self.object_info = Munch(
                {
                    "name": source_object_name,
                    "view_id": int(source_view_id),
                    "Id": int(source_object_id),
                    "image": object_image,
                }
            )
            self.init_pocket_image()

            self.parent().dragging_object = None
            self.parent().drag_object_bitmap = None  # Clear the stored bitmap

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

    def __init__(
        self,
        parent: ViewPanel,
        nav_type: str,
        nav_actions: list,
        nav_image_folder: Path,
    ):
        super().__init__(parent=parent)
        self.nav_type: str = nav_type
        self.nav_actions: list = nav_actions

        file_codex = dict(
            zip(
                ("NavTop", "NavBottom", "NavLeft", "NavRight"),
                ("nav_top.png", "nav_bottom.png", "nav_left.png", "nav_right.png"),
                strict=False,
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
                strict=False,
            )
        )

        style_sheet = "QLabel{background-color: rgba(0,0,0,0%)} "  # transparent background

        img_file = Path(nav_image_folder, file_codex[nav_type]).resolve()
        # log.warning(f"{img_file=}; {Path(img_file).is_file()=}")
        try:
            image = QImage(str(img_file))
            self.setFixedSize(image.width(), image.height())
            # Use forward slashes for Qt stylesheet URLs to avoid backslash escape issues on Windows
            img_file_url = img_file.as_posix()
            style_sheet += "QLabel::hover {background-image: url(" + img_file_url + ");}"
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
        except Exception as e:
            log.warning(f"Error Creating NavImageObject: {e}")

        # ensure the stylesheet background is actually painted on Windows
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMouseTracking(True)  # makes :hover more responsive on some styles
        style_sheet += "QLabel { background-repeat: no-repeat; } "

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
        parent: ViewPanel,
        message: str,
        left: int = 0,
        top: int = 0,
        duration: float = 0.0,
        fg_color: list | tuple = (255, 255, 255, 255),
        bg_color: list | tuple = (0, 0, 0, 255),
        font_size: int = 12,
        bold: bool = False,
    ):
        try:
            super().__init__(parent=parent)
        except RuntimeError:
            # Note: Here because I'm sometimes getting this:
            #       RuntimeError: wrapped C/C++ object of type ViewPanel has been deleted
            super().__init__()
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
            QTimer.singleShot(int(duration * 1000), self, self.hide_me)

    def hide_me(self):
        try:
            self.hide()
        except Exception:
            ...


class ExternalImageObject(QLabel):
    """
    Modified QLabel used to display an external image
    Assumes parent is ViewPanel instance
    """

    def __init__(
        self,
        parent: ViewPanel,
        image_path: Path,
        left: int = 0,
        top: int = 0,
        duration: float = 0.0,
        click_through: bool = False,
        scale: tuple | list = (1.0, 1.0),
    ):
        super().__init__(parent=parent)
        self.file_name = Path(image_path).name

        style_sheet = "QLabel{ " + "background-color: rgba(0,0,0,0%); "
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
            QTimer.singleShot(int(duration * 1000), self, self.hide)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
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
        parent: ViewPanel,
        video_path: Path,
        pos: QPoint,
        size: QSize,
        start: int = 0,
        volume: float = 1.0,
        loop: bool = False,
        on_finish: callable = None,
        polygon_points: list | None = None,
    ):
        super().__init__(parent=parent)
        self.video_path: Path = video_path
        self.player = None
        self.audio_output = None
        self.fallback_mode = False
        self.on_finish = on_finish
        self.polygon_points = polygon_points or []

        if loop:
            log.warning(
                'In the VideoObject class (created in PlayVideo() action) the "loop" parameter '
                "is not currently implemented"
            )

        style_sheet = "QVideoWidget{ background-color: rgba(0,0,0,0%); }"
        self.setStyleSheet(style_sheet)

        # Try to create QMediaPlayer with error handling
        try:
            url = QUrl.fromLocalFile(str(video_path.absolute()))

            self.player = QMediaPlayer(self.parent())
            self.player.setSource(url)
            self.player.setVideoOutput(self)
            self.player.setPosition(start)
            self.player.mediaStatusChanged.connect(self._on_media_status_changed)
            self.player.errorOccurred.connect(self._on_error)

            # Attach audio output if possible; PySide6 QAudioOutput lacks isAvailable on some platforms
            try:
                self.audio_output = QAudioOutput()
                self.player.setAudioOutput(self.audio_output)
                self.audio_output.setVolume(volume * 100)
                log.debug("Video audio output initialized successfully")
            except Exception as e:
                log.warning(f"Audio output not available for video playback: {e}")
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

        # Apply polygon mask if we have polygon points
        if self.polygon_points:
            self._set_polygon_mask()

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

    def _on_media_status_changed(self, status):
        log.debug(f"Video status changed: {status}")
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.on_finish:
                self.on_finish()
            self.close()
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            log.warning(f"Invalid media encountered for {self.video_path}")

    def _on_error(self, error, error_string=None):
        log.error(f"Video playback error ({error}): {error_string or ''}")

    def closeEvent(self, event: QCloseEvent) -> None:
        self.stop()
        event.accept()

    def _set_polygon_mask(self):
        """Set a mask on the video widget so only the polygon area is visible."""
        if not self.polygon_points:
            return

        # Get widget geometry to calculate local polygon coordinates
        geom = self.geometry()

        # Convert global polygon points to local widget coordinates
        local_points = [QPoint(p[0] - geom.x(), p[1] - geom.y()) for p in self.polygon_points]

        # Create polygon and set as mask
        polygon = QPolygon(local_points)
        region = QRegion(polygon)
        self.setMask(region)

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
            if self.on_finish:
                self.on_finish()
            self.close()


class AnimationObject(QLabel):
    """
    Modified QLabel used to display a gif animation
    Assumes parent is ViewPanel instance
    """

    def __init__(
        self,
        parent: ViewPanel,
        video_path: Path,
        pos: QPoint,
        size: QSize,
        start: int = 0,
        volume: float = 1.0,
        loop: bool = False,
        on_finish: callable = None,
        polygon_points: list | None = None,
    ):
        super().__init__(parent=parent)
        self.video_path: Path = video_path
        self.on_finish = on_finish
        self.polygon_points = polygon_points or []

        style_sheet = "QLabel{ background-color: rgba(0,0,0,0%); }"
        self.setStyleSheet(style_sheet)

        self.setScaledContents(True)
        self.movie = QMovie(str(video_path.absolute()), parent=self)
        self.setMovie(self.movie)

        # For non-looping animations, connect finished signal
        if not loop:
            self.movie.finished.connect(self._on_movie_finished)

        if isinstance(size, QSize):
            self.setFixedSize(size)
        else:
            self.setFixedSize(self.parent().size())

        self.move(pos)
        self.show()
        self.play()
        self.activateWindow()
        self.raise_()

        # Apply polygon mask if we have polygon points
        if self.polygon_points:
            self._set_polygon_mask()

    def _on_movie_finished(self):
        """Called when the animation finishes playing."""
        if self.on_finish:
            self.on_finish()
        self.close()

    def play(self):
        with contextlib.suppress(Exception):
            self.movie.start()

    def pause(self):
        with contextlib.suppress(Exception):
            self.movie.stop()

    def stop(self):
        with contextlib.suppress(Exception):
            self.movie.stop()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.stop()
        event.accept()

    def _set_polygon_mask(self):
        """Set a mask on the animation widget so only the polygon area is visible."""
        if not self.polygon_points:
            return

        # Get widget geometry to calculate local polygon coordinates
        geom = self.geometry()

        # Convert global polygon points to local widget coordinates
        local_points = [QPoint(p[0] - geom.x(), p[1] - geom.y()) for p in self.polygon_points]

        # Create polygon and set as mask
        polygon = QPolygon(local_points)
        region = QRegion(polygon)
        self.setMask(region)

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
            if self.on_finish:
                self.on_finish()
            self.close()
