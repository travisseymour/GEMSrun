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

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap, QPainter, QPainterPath, QPen, QColor


def pixmap_to_pointer(pixmap: QPixmap, width: 50, height: int = 50, keep_aspect_ratio: bool = True) -> QPixmap:
    """
    Takes a pixmap and creates a dragging icon with a little pointer in the upper left.
    returns a picture you can use to indicate something is being dragged.
    Works on linux, not tested on windows, does not seem to work on macos.
    """
    new_pixmap = QPixmap(pixmap).scaled(
        QSize(width, height),
        (Qt.AspectRatioMode.KeepAspectRatio if keep_aspect_ratio else Qt.AspectRatioMode.IgnoreAspectRatio),
    )

    point_size = int(new_pixmap.width() * 0.15)
    painter = QPainter()
    path = QPainterPath()
    painter.begin(new_pixmap)
    # painter.setRenderHint(QPainterPath.Antialiasing)
    painter.setPen(QPen(QColor("yellow"), 2))
    painter.setBrush(QColor("yellow"))
    path.moveTo(0, 0)
    path.lineTo(point_size, 0)
    path.lineTo(0, point_size)
    path.lineTo(0, 0)
    painter.drawPath(path)
    painter.end()

    return new_pixmap
