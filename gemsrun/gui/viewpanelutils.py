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

from functools import lru_cache
from pathlib import Path
import re

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

    overlay = get_custom_cursors().get("closed_hand_overlay")
    if overlay and not overlay.isNull():
        hotspot_offset = QPoint(overlay.width() // 2, overlay.height() // 2)
        dest = hotspot - hotspot_offset
        painter.drawPixmap(dest, overlay)
    else:
        # last-resort fallback: draw a small yellow circle at the hotspot
        painter.setPen(QPen(QColor("yellow"), 2))
        painter.setBrush(QColor("yellow"))
        painter.drawEllipse(hotspot, 6, 6)

    painter.end()
    return drag_pixmap


def _cursor_from_file(rel_path: str, default_shape: Qt.CursorShape) -> QCursor:
    try:
        path = Path(get_resource("images", rel_path))
        if not path.is_file():
            return QCursor(default_shape)
        match = re.search(r"_([0-9]+)_([0-9]+)\.", path.name)
        hx, hy = (int(match.group(1)), int(match.group(2))) if match else (0, 0)
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return QCursor(default_shape)
        return QCursor(pixmap, hx, hy)
    except Exception:
        return QCursor(default_shape)


@lru_cache
def get_custom_cursors() -> dict:
    """
    Load custom cursors and overlay assets from resources/images/cursors.
    Expected files:
      arrow_2_3.png
      open_hand_17_15.png
      pointing_hand_13_9.png
      closed_hand_cropped.png (used as overlay, not a cursor)
    """
    cursors = {
        "arrow": _cursor_from_file("cursors/arrow_2_3.png", Qt.CursorShape.ArrowCursor),
        "open_hand": _cursor_from_file("cursors/open_hand_17_15.png", Qt.CursorShape.OpenHandCursor),
        "pointing_hand": _cursor_from_file("cursors/pointing_hand_13_9.png", Qt.CursorShape.PointingHandCursor),
    }
    try:
        overlay_path = Path(get_resource("images", "cursors/closed_hand_cropped.png"))
        overlay = QPixmap(str(overlay_path)) if overlay_path.is_file() else QPixmap()
    except Exception:
        overlay = QPixmap()
    cursors["closed_hand_overlay"] = overlay
    return cursors
