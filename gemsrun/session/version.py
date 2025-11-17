"""
GEMSrun
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

from importlib.metadata import version
import os
import tomllib


def get_version_from_pyproject():
    pyproject_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "pyproject.toml",
    )
    pyproject_path = os.path.abspath(pyproject_path)

    with open(pyproject_path, "rb") as f:
        pyproject_data = tomllib.load(f)
        return pyproject_data.get("project", {}).get("version", "Unknown")


try:
    # Try to get version from installed package
    __version__ = version("gemsrun")
except Exception:
    # Fallback: Read version from pyproject.toml during development
    __version__ = get_version_from_pyproject()

print(f"Running GEMSRun version {__version__}")
