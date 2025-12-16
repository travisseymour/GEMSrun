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

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QColor, QCursor, QPainter, QPainterPath, QPen, QPixmap

from gemsrun.utils.apputils import get_resource


def pixmap_to_pointer(pixmap: QPixmap, width: int = 50, height: int = 50, keep_aspect_ratio: bool = True) -> QPixmap:
    """
    Takes a pixmap and creates a dragging icon with a little pointer in the upper left.
    returns a picture you can use to indicate something is being dragged.
    Works on linux, not tested on windows, does not seem to work on macos.
    """
    return QPixmap(pixmap).scaled(
        QSize(width, height),
        (Qt.AspectRatioMode.KeepAspectRatio if keep_aspect_ratio else Qt.AspectRatioMode.IgnoreAspectRatio),
    )


def drag_pixmap_with_hand(pixmap: QPixmap, hotspot: QPoint) -> QPixmap:
    """
    Build a drag pixmap and overlay a closed-hand cursor graphic, aligning the cursor hotspot
    with the provided hotspot. Falls back to a packaged icon (resources/images/close_hand_icon.png)
    and finally a small marker if no icon is available.
    """
    drag_pixmap = QPixmap(pixmap)

    painter = QPainter(drag_pixmap)
    hand_cursor = QCursor(Qt.CursorShape.ClosedHandCursor)
    hand_pixmap = hand_cursor.pixmap()

    if hand_pixmap.isNull():
        # try packaged fallback icon if system cursor pixmap is unavailable
        try:
            icon_path = Path(get_resource("images", "close_hand_icon.png"))
            if icon_path.is_file():
                hand_pixmap = QPixmap(str(icon_path))
                # center the icon on the hotspot
                hotspot_offset = QPoint(hand_pixmap.width() // 2, hand_pixmap.height() // 2)
                dest = hotspot - hotspot_offset
                painter.drawPixmap(dest, hand_pixmap)
        except Exception:
            ...

    if hand_pixmap.isNull():
        # last-resort fallback: draw a small yellow circle at the hotspot
        painter.setPen(QPen(QColor("yellow"), 2))
        painter.setBrush(QColor("yellow"))
        painter.drawEllipse(hotspot, 6, 6)
    else:
        hand_hotspot = hand_cursor.hotSpot() if not hand_cursor.pixmap().isNull() else QPoint(
            hand_pixmap.width() // 2, hand_pixmap.height() // 2
        )
        dest = hotspot - hand_hotspot
        painter.drawPixmap(dest, hand_pixmap)

    painter.end()
    return drag_pixmap
