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

import json
from typing import TypeAlias

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QPainterPath, QPolygon

Point: TypeAlias = list[int]  # [x, y]
Polygon: TypeAlias = list[Point]  # [[x1,y1], [x2,y2], ...]


def json_to_points(json_str: str | None) -> Polygon:
    """
    Deserialize polygon points from a JSON string.

    Args:
        json_str: JSON string containing list of [x, y] pairs

    Returns:
        List of points, or empty list if invalid/empty
    """
    if not json_str:
        return []
    try:
        result = json.loads(json_str)
        if isinstance(result, list):
            return result
        return []
    except (json.JSONDecodeError, TypeError):
        return []


def points_to_bounding_rect(points: Polygon) -> tuple[int, int, int, int]:
    """
    Get the axis-aligned bounding rectangle for a polygon.

    Args:
        points: List of [x, y] coordinate pairs

    Returns:
        Tuple of (left, top, width, height), or (0, 0, 0, 0) if empty
    """
    if not points:
        return (0, 0, 0, 0)
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    left, top = min(xs), min(ys)
    right, bottom = max(xs), max(ys)
    return (left, top, right - left, bottom - top)


def points_to_qpolygon(points: Polygon) -> QPolygon:
    """
    Convert polygon points to a QPolygon for Qt operations.

    Args:
        points: List of [x, y] coordinate pairs

    Returns:
        QPolygon object
    """
    return QPolygon([QPoint(p[0], p[1]) for p in points])


def points_to_qrect(points: Polygon) -> QRect:
    """
    Get the bounding QRect for a polygon.

    Args:
        points: List of [x, y] coordinate pairs

    Returns:
        QRect bounding box
    """
    left, top, width, height = points_to_bounding_rect(points)
    return QRect(left, top, width, height)


def scale_points(points: Polygon, scale_x: float, scale_y: float, offset_x: int = 0, offset_y: int = 0) -> Polygon:
    """
    Scale and offset polygon points.

    Args:
        points: List of [x, y] coordinate pairs
        scale_x: Horizontal scale factor
        scale_y: Vertical scale factor
        offset_x: Horizontal offset to add after scaling
        offset_y: Vertical offset to add after scaling

    Returns:
        New list of scaled/offset points
    """
    return [[int(p[0] * scale_x) + offset_x, int(p[1] * scale_y) + offset_y] for p in points]


def point_in_polygon(point: Point | QPoint, points: Polygon) -> bool:
    """
    Check if a point is inside a polygon using Qt's containsPoint.

    Args:
        point: [x, y] point or QPoint to test
        points: Polygon vertices

    Returns:
        True if point is inside polygon
    """
    if not points:
        return False

    if isinstance(point, QPoint):
        qpoint = point
    else:
        qpoint = QPoint(point[0], point[1])

    polygon = points_to_qpolygon(points)
    return polygon.containsPoint(qpoint, 0)  # 0 = OddEvenFill


def create_polygon_painter_path(points: Polygon) -> QPainterPath:
    """
    Create a QPainterPath for polygon clipping.

    Args:
        points: List of [x, y] coordinate pairs

    Returns:
        QPainterPath for use with painter.setClipPath()
    """
    path = QPainterPath()
    if not points:
        return path

    path.moveTo(points[0][0], points[0][1])
    for p in points[1:]:
        path.lineTo(p[0], p[1])
    path.closeSubpath()
    return path


def has_old_style_bounds(obj) -> bool:
    """
    Check if an object uses old-style rectangular bounds (Left/Top/Width/Height)
    instead of new polygon Points.

    Args:
        obj: Object with potential Left/Top/Width/Height or Points attributes

    Returns:
        True if object has old-style bounds without Points
    """
    has_old_columns = hasattr(obj, "Left") and hasattr(obj, "Width")
    has_new_column = hasattr(obj, "Points") and obj.Points
    return has_old_columns and not has_new_column
