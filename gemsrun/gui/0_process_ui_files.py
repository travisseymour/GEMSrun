from pathlib import Path

from plumbum import local
from plumbum.colors import bold, cyan, green, red, yellow

"""
This converts .ui files to .py files for PyQt6, but to keep GIT history accurate,
I only want to process ui files that actually changed.

"""

qt_type = None

try:
    import PySide6

    print(f"Found PySide6 v{PySide6.__version__}")
    qt_type = "pyside6"
except ImportError:
    try:
        import PyQt6

        print(f"Found PySide6 v{PyQt6.__version__}")
        qt_type = "pyqt6"
    except ImportError as err:
        raise ValueError("Expecting To Find Either PySide6 or PyQt6!") from err

ui_files: list[Path] = list(Path().glob("*.ui"))

if not ui_files:
    print("No ui files found...nothing to do." | yellow & bold)

print(f"Checking {len(ui_files)} ui files for potential changes..." | yellow & bold)

found_anything = False

for ui in ui_files:
    py = ui.with_suffix(".py")
    if not py.is_file() or ui.stat().st_mtime > py.stat().st_mtime:
        found_anything = True
        print(f"Converting {ui.name} to {py.name}" | cyan)
        try:
            local["pyuic6" if qt_type == "pyqt6" else "pyside6-uic"]([str(ui.resolve()), "-o", str(py.resolve())])
            print("\tSuccess!" | green)
        except Exception as e:
            print(f"\tERROR: {e}" | red & bold)

if not found_anything:
    print("All files up to date. Nothing done." | yellow & bold)

print("Finished." | yellow & bold)
