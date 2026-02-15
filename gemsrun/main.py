import itertools
from pathlib import Path
import sys
import threading
import time

from munch import Munch
from PySide6.QtCore import QCoreApplication, QSettings, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox
import typer

import gemsrun
from gemsrun.gui import mainwindow
from gemsrun.gui.parawindow import ParamDialog
from gemsrun.session import sessionsetup as ssetup
from gemsrun.utils import apputils, audiocache

app = typer.Typer(add_completion=False, help="GEMSrun command line interface.")


def _preload_audio_with_spinner(db: Munch):
    """Preload all compressed audio files with a CLI spinner."""

    media_path = db.Global.Options.MediaPath
    audio_files = audiocache.find_playsound_files_in_database(db, media_path)

    # Spinner animation
    spinner = itertools.cycle(["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"])
    done = False
    current_file = [""]
    progress = [0, len(audio_files)]

    def spin():
        while not done:
            sys.stdout.write(
                f"\r{next(spinner)} Loading audio [{progress[0]}/{progress[1]}]: {current_file[0][:50]:<50}"
            )
            sys.stdout.flush()
            time.sleep(0.1)

    spinner_thread = threading.Thread(target=spin, daemon=True)
    spinner_thread.start()

    def update_progress(current: int, total: int, filename: str):
        progress[0] = current
        progress[1] = total
        current_file[0] = filename

    audiocache.preload_audio_files(audio_files, progress_callback=update_progress)

    done = True
    spinner_thread.join(timeout=0.2)
    sys.stdout.write("\r" + " " * 80 + "\r")  # Clear the line
    sys.stdout.flush()


def _handle_clear_cache():
    """Handle the clear-cache command separately."""
    if audiocache.clear_cache():
        print(f"Audio cache cleared successfully: {audiocache.CACHE_FOLDER}")
        sys.exit(0)
    else:
        print("Failed to clear audio cache!")
        sys.exit(1)


@app.command()
def run(
    env_path: str | None = typer.Argument(
        None,
        metavar="FILENAME",
        help="GEMS environment filename (positional or --file).",
    ),
    user_arg: str | None = typer.Argument(
        None, metavar="USERID", help="User ID string, used to create data file name."
    ),
    fname: str | None = typer.Option(None, "--file", "-f", help="Specify your gems environment filename."),
    user: str | None = typer.Option(None, "--user", "-u", help="Specify user ID string."),
    skipdata: bool | None = typer.Option(None, "--skipdata/--no-skipdata", "-s", help="Suppress the output data file."),
    overwrite: bool | None = typer.Option(
        None,
        "--overwrite/--no-overwrite",
        "-o",
        help="Enable overwriting of duplicate output data.",
    ),
    debug: bool | None = typer.Option(
        None,
        "--debug/--no-debug",
        "-d",
        help="Write extra debugging information to terminal.",
    ),
    skipmedia: bool | None = typer.Option(
        None,
        "--skipmedia/--no-skipmedia",
        "-k",
        help="Disable playback of audio and video files.",
    ),
    skipgui: bool = typer.Option(
        False,
        "--skipgui",
        "-g",
        help="Suppress GUI prompt for missing command-line parameters.",
    ),
    fullscreen: bool | None = typer.Option(
        None, "--fullscreen/--no-fullscreen", "-F", help="Launch runner in fullscreen."
    ),
):
    cli_fname = fname or env_path or ""
    cli_user = user or user_arg

    # Round fractional DPR (e.g. 1.198) to nearest integer to avoid rendering
    # artifacts in view transitions on screens with non-integer text scaling.
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.Round)
    gemsrun.APPLICATION = QApplication([])
    gemsrun.default_font = QFont("Arial", 12)

    # IMPORTANT: Set organization/app names BEFORE creating QSettings
    # so that settings are stored in the correct registry location on Windows
    QCoreApplication.setOrganizationName("TravisSeymour")
    QCoreApplication.setOrganizationDomain("travisseymour.com")
    QCoreApplication.setApplicationName("GEMSrun")

    # Now create QSettings - it will use the organization/app names set above
    gemsrun.SETTINGS = QSettings()

    # Set application icon with multiple sizes for different contexts
    app_icon = QIcon()
    for size in [16, 24, 32, 48, 64, 128, 256, 512]:
        try:
            icon_path = apputils.get_resource("images", "appicon", f"icon_{size}.png")
            app_icon.addFile(str(icon_path))
        except FileNotFoundError:
            pass
    gemsrun.APPLICATION.setWindowIcon(app_icon)

    settings = gemsrun.SETTINGS

    # Debug: Check what's actually stored in settings on Windows
    if sys.platform == "win32":
        print(f"[DEBUG] Reading settings:")
        print(f"  fname raw: {settings.value('fname')!r}")
        print(f"  fullscreen raw: {settings.value('fullscreen')!r}")
        print(f"  skipdata raw: {settings.value('skipdata')!r}")

    args = Munch(
        {
            "fname": (cli_fname if cli_fname else settings.value("fname", defaultValue="", type=str)),
            "user": (cli_user if cli_user is not None else settings.value("user", defaultValue="User1", type=str)),
            "skipdata": (
                skipdata if skipdata is not None else settings.value("skipdata", defaultValue=False, type=bool)
            ),
            "fullscreen": (
                fullscreen if fullscreen is not None else settings.value("fullscreen", defaultValue=False, type=bool)
            ),
            "overwrite": (
                overwrite if overwrite is not None else settings.value("overwrite", defaultValue=False, type=bool)
            ),
            "debug": (debug if debug is not None else settings.value("debug", defaultValue=False, type=bool)),
            "skipmedia": (
                skipmedia if skipmedia is not None else settings.value("skipmedia", defaultValue=False, type=bool)
            ),
        }
    )

    if sys.platform == "win32":
        print(f"[DEBUG] After parsing: fullscreen={args.fullscreen!r}, skipdata={args.skipdata!r}")
    session: Munch | None = None

    if skipgui:
        cli_only_args = Munch(
            {
                "fname": cli_fname,
                "user": cli_user,
                "skipdata": skipdata if skipdata is not None else False,
                "overwrite": overwrite if overwrite is not None else False,
                "debug": debug if debug is not None else False,
                "skipmedia": skipmedia if skipmedia is not None else False,
                "fullscreen": fullscreen if fullscreen is not None else False,
            }
        )

        if not isinstance(cli_fname, str) or not Path(cli_fname).is_file():
            _ = QMessageBox.critical(
                None,
                "Invalid Run Parameters",
                f'GEMSrun started with the --skipgui flag, but the "file" parameter of '
                f'"{cli_fname}" is not a valid GEMS environment file.',
                QMessageBox.StandardButton.Ok,
            )
            raise typer.Exit(code=1)
        elif not isinstance(cli_user, str) or not cli_user:
            _ = QMessageBox.critical(
                None,
                "Invalid Run Parameters",
                f'GEMSrun started with the --skipgui flag, but the "user" parameter of '
                f'"{cli_user}" is not a valid string.',
                QMessageBox.StandardButton.Ok,
            )
            raise typer.Exit(code=1)

        settings.setValue("debug", args.debug)
        session = ssetup.setup_session(args=cli_only_args)
    else:
        param_window = ParamDialog(args)
        param_window.exec()

        import sys

        if sys.platform == "win32":
            print(f"[DEBUG] Dialog closed, param_window.ok={param_window.ok}")

        if param_window.ok:
            settings.setValue("fname", args.fname)
            settings.setValue("user", args.user)
            settings.setValue("skipdata", args.skipdata)
            settings.setValue("overwrite", args.overwrite)
            settings.setValue("debug", args.debug)
            settings.setValue("skipmedia", args.skipmedia)
            settings.setValue("fullscreen", args.fullscreen)
            settings.sync()  # Ensure settings are written to disk immediately

            try:
                session = ssetup.setup_session(args=args)
            except Exception as e:
                import traceback

                QMessageBox.critical(
                    None,
                    "Unexpected Error During Setup",
                    f"An unexpected error occurred:\n\n{e}\n\n{traceback.format_exc()}",
                    QMessageBox.StandardButton.Ok,
                )
                raise typer.Exit(code=1) from None

            if not session.ok:
                raise typer.Exit(code=1)
        else:
            raise typer.Exit(code=1)

    if args.fullscreen:
        session.database.Global.Options.DisplayType = "fullscreen"

    # Preload compressed audio at app start if Preloadresources is enabled
    if session.database.Global.Options.Preloadresources:
        _preload_audio_with_spinner(session.database)

    main_win = mainwindow.MainWin(db=session.database)

    if session.database.Global.Options.DisplayType.lower() == "fullscreen":
        main_win.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        main_win.showFullScreen()
    elif session.database.Global.Options.DisplayType.lower() == "maximized":
        main_win.showMaximized()
    else:
        main_win.showNormal()

    exit_code = gemsrun.APPLICATION.exec()
    raise typer.Exit(code=exit_code)


def main():
    # Handle clear-cache command separately to keep 'run' as default
    if len(sys.argv) > 1 and sys.argv[1] == "clear-cache":
        _handle_clear_cache()
    else:
        app(prog_name="GEMSrun")


if __name__ == "__main__":
    main()
