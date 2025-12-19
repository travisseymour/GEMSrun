from pathlib import Path

from munch import Munch
from PySide6.QtCore import QCoreApplication, QSettings, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox
import typer

import gemsrun
from gemsrun.gui import mainwindow
from gemsrun.gui.parawindow import ParamDialog
from gemsrun.session import sessionsetup as ssetup

# Avoid forcing QT multimedia backend. Let Qt auto-detect best available plugins.
# If users need to override, they can set QT_MEDIA_BACKEND in their environment before launch.

app = typer.Typer(add_completion=False, help="GEMSrun command line interface.")

@app.command()
def run(
    env_path: str | None = typer.Argument(
        None, metavar="FILENAME", help="GEMS environment filename (positional or --file)."
    ),
    user_arg: str | None = typer.Argument(
        None, metavar="USERID", help="User ID string, used to create data file name."
    ),
    fname: str | None = typer.Option(None, "--file", "-f", help="Specify your gems environment filename."),
    user: str | None = typer.Option(None, "--user", "-u", help="Specify user ID string."),
    skipdata: bool | None = typer.Option(
        None, "--skipdata/--no-skipdata", "-s", help="Suppress the output data file."
    ),
    overwrite: bool | None = typer.Option(
        None, "--overwrite/--no-overwrite", "-o", help="Enable overwriting of duplicate output data."
    ),
    debug: bool | None = typer.Option(
        None, "--debug/--no-debug", "-d", help="Write extra debugging information to terminal."
    ),
    skipmedia: bool | None = typer.Option(
        None, "--skipmedia/--no-skipmedia", "-k", help="Disable playback of audio and video files."
    ),
    skipgui: bool = typer.Option(
        False, "--skipgui", "-g", help="Suppress GUI prompt for missing command-line parameters."
    ),
    fullscreen: bool | None = typer.Option(
        None, "--fullscreen/--no-fullscreen", "-F", help="Launch runner in fullscreen."
    ),
):
    cli_fname = fname or env_path or ""
    cli_user = user or user_arg

    gemsrun.APPLICATION = QApplication([])
    gemsrun.default_font = QFont("Arial", 12)
    gemsrun.SETTINGS = QSettings()

    QCoreApplication.setOrganizationName("TravisSeymour")
    QCoreApplication.setOrganizationDomain("travisseymour.com")
    QCoreApplication.setApplicationName("GEMSrun")

    settings = gemsrun.SETTINGS
    args = Munch(
        {
            "fname": cli_fname if cli_fname else settings.value("fname", defaultValue="", type=str),
            "user": (
                cli_user if cli_user is not None else settings.value("user", defaultValue="User1", type=str)
            ),
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

        if param_window.ok:
            settings.setValue("fname", args.fname)
            settings.setValue("user", args.user)
            settings.setValue("skipdata", args.skipdata)
            settings.setValue("overwrite", args.overwrite)
            settings.setValue("debug", args.debug)
            settings.setValue("skipmedia", args.skipmedia)
            settings.setValue("fullscreen", args.fullscreen)

            session = ssetup.setup_session(args=args)

            if not session.ok:
                raise typer.Exit(code=1)
        else:
            raise typer.Exit(code=1)

    if args.fullscreen:
        session.database.Global.Options.DisplayType = "fullscreen"

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
    app(prog_name="GEMSrun")


if __name__ == "__main__":
    main()
