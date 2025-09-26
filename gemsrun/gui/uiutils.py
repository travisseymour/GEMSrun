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

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage, QTransform
from PySide6.QtCore import Qt
from pathlib import Path

from gemsrun import log


def create_nav_pics(
    nav_panel_image: QImage,
    temp_folder: Path,
    view_width: int,
    view_height: int,
    nav_extent: int,
) -> str:
    """
    Assumes nav_panel is an already loaded QImage for **nav_bottom**!
    return: empty string if aOK, otherwise an error string.
    """

    # using LBYL to avoid wasting time doing transforms that fail (they take a long time to fail for some reason)
    if not temp_folder.is_dir():
        return f"temp_folder {temp_folder} is not an existing or writable path."
    if not isinstance(nav_panel_image, QImage):
        return f"nav_panel_image is type {type(nav_panel_image)}, but should be QImage."

    width, height = view_width, view_height

    try:
        log.debug(f"{temp_folder=}")
        # NavTop
        image = nav_panel_image.transformed(QTransform().rotate(180))
        image = image.scaled(
            QSize(width, nav_extent),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        image.save(str(Path(temp_folder, "nav_top.png").resolve()))
        # image.save(str(Path(Path().home(), "Desktop", "TEMP", "nav_top.png")))

        # NavBottom
        image = nav_panel_image.scaled(
            QSize(width, nav_extent),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        image.save(str(Path(temp_folder, "nav_bottom.png").resolve()))
        # image.save(str(Path(Path().home(), "Desktop", "TEMP", "nav_bottom.png")))

        # NavLeft
        image = nav_panel_image.transformed(QTransform().rotate(90))
        image = image.scaled(
            QSize(nav_extent, height),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        image.save(str(Path(temp_folder, "nav_left.png").resolve()))
        # image.save(str(Path(Path().home(), "Desktop", "TEMP", "nav_left.png")))

        # NavRight
        image = nav_panel_image.transformed(QTransform().rotate(-90))
        image = image.scaled(
            QSize(nav_extent, height),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        image.save(str(Path(temp_folder, "nav_right.png").resolve()))
        # image.save(str(Path(Path().home(), "Desktop", "TEMP", "nav_right.png")))

    except Exception as e:
        return f"problem creating scaled navigation panels: {e}"

    return ""
