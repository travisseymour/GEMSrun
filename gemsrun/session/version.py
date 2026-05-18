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
import io
import os
import tomllib
import urllib.request


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


GITHUB_PYPROJECT_URL = "https://raw.githubusercontent.com/travisseymour/GEMSrun/main/pyproject.toml"


def version_less_than(version_str: str, target: str) -> bool:
    """Compare version strings like '2026.1.10.7'. Returns True if version_str < target."""
    if not version_str or not target:
        return False
    try:
        v1 = [int(x) for x in str(version_str).split(".")]
        v2 = [int(x) for x in str(target).split(".")]
        max_len = max(len(v1), len(v2))
        v1.extend([0] * (max_len - len(v1)))
        v2.extend([0] * (max_len - len(v2)))
        return v1 < v2
    except (ValueError, AttributeError):
        return False


def check_latest_github_version() -> str | None:
    """Fetch the latest version from the GitHub repo. Returns version string or None on failure."""
    try:
        req = urllib.request.Request(GITHUB_PYPROJECT_URL)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read()
        pyproject_data = tomllib.load(io.BytesIO(data))
        return pyproject_data.get("project", {}).get("version", None)
    except Exception:
        return None


try:
    # Try to get version from installed package
    __version__ = version("gemsrun")
except Exception:
    # Fallback: Read version from pyproject.toml during development
    __version__ = get_version_from_pyproject()

print(f"Running GEMSRun version {__version__}")
