import optparse
from pathlib import Path
import sys
from typing import Optional

from munch import Munch
from PySide6.QtCore import QCoreApplication, QSettings, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

import gemsrun
from gemsrun import app_short_name
from gemsrun.gui import mainwindow
from gemsrun.gui.parawindow import ParamDialog
from gemsrun.session import sessionsetup as ssetup

# Avoid forcing QT multimedia backend. Let Qt auto-detect best available plugins.
# If users need to override, they can set QT_MEDIA_BACKEND in their environment before launch.


def get_parser() -> optparse.OptionParser:
    # Define commandline arguments
    parser = optparse.OptionParser(
        version=f"%prog {app_short_name}",
        usage="%prog [options]\n  e.g.:\n  %prog -f myenvironment.yaml -u User1 -s\n   or\n"
        "%prog --file=myenvironment.yaml --user=User1 --skipdata --overwrite\n   or\n"
        "%prog myenvironment.yaml User1\n",
    )

    parser.add_option(
        "-f",
        "--file",
        action="store",
        dest="fname",
        type="string",
        help="Specify your gems environment filename",
        metavar="FILENAME",
    )

    parser.add_option(
        "-u",
        "--user",
        action="store",
        dest="user",
        type="string",
        # default="User1",
        help="Specify user ID string, used to create data file name",
        metavar="USERID",
    )

    parser.add_option(
        "-s",
        "--skipdata",
        action="store_true",
        dest="skipdata",
        help="Enables suppression of the output data file.",
    )

    parser.add_option(
        "-o",
        "--overwrite",
        action="store_true",
        dest="overwrite",
        help="Enables overwriting of duplicate output data",
    )

    parser.add_option(
        "-d",
        "--debug",
        action="store_true",
        dest="debug",
        help="Enables writing of output data to terminal",
    )

    parser.add_option(
        "-k",
        "--skipmedia",
        action="store_true",
        dest="skipmedia",
        help="Disables playback of audio and video files",
    )

    parser.add_option(
        "-g",
        "--skipgui",
        action="store_true",
        dest="skipgui",
        help="Suppresses GUI prompt for missing commandline parameters",
    )

    parser.add_option(
        "-F",
        "--fullscreen",
        action="store_true",
        dest="fullscreen",
        help="Launches runner in fullscreen (ignoring value in environment file)",
    )

    return parser


def main():
    cmd_line, _ = get_parser().parse_args(sys.argv[1:])

    gemsrun.APPLICATION = QApplication([])
    gemsrun.default_font = QFont("Arial", 12)
    gemsrun.SETTINGS = QSettings()

    # Set some global vars
    QCoreApplication.setOrganizationName("TravisSeymour")
    QCoreApplication.setOrganizationDomain("travisseymour.com")
    QCoreApplication.setApplicationName("GEMSrun")

    # gemsrun.CONFIG_PATH = Path(appdirs.user_config_dir(), 'GEMS')
    # gemsrun.CONFIG_PATH.mkdir(exist_ok=True)
    # gemsrun.LOG_PATH = Path(gemsrun.CONFIG_PATH, 'gems_run_log.txt')
    # gemsrun.LOG_PATH.write_text('')
    # gemsrun.log.add(str(gemsedit.LOG_PATH))

    # try:
    #     gemsrun.log.info(f'\n---------------{datetime.datetime.now().ctime()}---------------')
    #     gemsrun.log.info(f'GEMSrun app logging enabled at {gemsrun.LOG_PATH}')
    # except Exception as e:
    #     gemsrun.log.warning(f'GEMSrun app logging to {gemsrun.LOG_PATH} failed: "{e}"')

    settings = gemsrun.SETTINGS
    args = Munch(
        {
            "fname": (
                cmd_line.fname if cmd_line.fname is not None else settings.value("fname", defaultValue="", type=str)
            ),
            "user": (
                cmd_line.user if cmd_line.user is not None else settings.value("user", defaultValue="User1", type=str)
            ),
            "skipdata": (
                cmd_line.skipdata
                if cmd_line.skipdata is not None
                else settings.value("skipdata", defaultValue=False, type=bool)
            ),
            "fullscreen": (
                cmd_line.fullscreen
                if cmd_line.fullscreen is not None
                else settings.value("fullscreen", defaultValue=False, type=bool)
            ),
            "overwrite": (
                cmd_line.overwrite
                if cmd_line.overwrite is not None
                else settings.value("overwrite", defaultValue=False, type=bool)
            ),
            "debug": (
                cmd_line.debug if cmd_line.debug is not None else settings.value("debug", defaultValue=False, type=bool)
            ),
            "skipmedia": (
                cmd_line.skipmedia
                if cmd_line.skipmedia is not None
                else settings.value("skipmedia", defaultValue=False, type=bool)
            ),
        }
    )

    session: Optional[Munch] = None

    if cmd_line.skipgui:
        if not isinstance(cmd_line.fname, str) or not Path(cmd_line.fname).is_file():
            _ = QMessageBox.critical(
                None,
                "Invalid Run Parameters",
                f'GEMSrun started with the --skipgui flag, but the "file" parameter of '
                f'"{cmd_line.fname}" is not a valid GEMS environment file.',
                QMessageBox.StandardButton.Ok,
            )
            sys.exit()
        elif not isinstance(cmd_line.user, str) or not cmd_line.user:
            _ = QMessageBox.critical(
                None,
                "Invalid Run Parameters",
                f'GEMSrun started with the --skipgui flag, but the "user" parameter of '
                f'"{cmd_line.user}" is not a valid string.',
                QMessageBox.StandardButton.Ok,
            )
            sys.exit()

        session = ssetup.setup_session(args=cmd_line)
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
                sys.exit()
        else:
            sys.exit()

    if settings.value("fullscreen") or cmd_line.fullscreen is not None:
        session.database.Global.Options.DisplayType = "fullscreen"

    main_win = mainwindow.MainWin(db=session.database)

    if session.database.Global.Options.DisplayType.lower() == "fullscreen":
        main_win.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        main_win.showFullScreen()
    elif session.database.Global.Options.DisplayType.lower() == "maximized":
        main_win.showMaximized()
    else:
        main_win.showNormal()

    gemsrun.APPLICATION.exec()

    sys.exit()


if __name__ == "__main__":
    main()
