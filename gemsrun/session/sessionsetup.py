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

from PySide6.QtWidgets import QMessageBox

from gemsrun import log
from pathlib import Path
import random
import sys
from gemsrun.utils import gemsutils as gu, ttsutils
from datetime import datetime

from munch import Munch
from gemsrun import app_short_name
from gemsrun.session.version import __version__


def setup_data_logging(user: str, debug: bool) -> Path:
    """
    INFO ON LOGGING
    msg
    Type=['sys' or 'user']
    Context=[name of function]
    TaskTime=[time since env started] (for user only)
    ViewTime=[time since view started] (for user only)
    """

    if debug:
        log_format = "{time: MM-DD-YY | HH:mm:ss} | {module} | {line} | {function} | {level} | {message}"
    else:
        log_format = "{message}"

    # setup logfile sink
    data_path = Path.home() / "Documents" / "GEMS" / "Data"  # TODO: Add Option To Move This
    data_path.parent.mkdir(exist_ok=True)
    data_path.mkdir(exist_ok=True)
    dt = datetime.strftime(datetime.now(), "%m%d%y_%H%M%S")
    log_file = Path(data_path, f"{app_short_name}_v{__version__.replace('.', '')}_{user}_{dt}.txt")

    log.remove()

    if debug:
        # In debug mode, keep console output AND add file output
        log.add(
            #Path(data_path, log_file),
            log_file,
            format=log_format,
            colorize=False,
            enqueue=True,
            level="DEBUG",
        )
        # Console output with colors for debug mode
        log.add(
            sys.stderr,
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{module}</cyan>:<cyan>{line}</cyan> | {message}",
            colorize=True,
            enqueue=True,
            level="DEBUG",
        )

    else:
        log.remove()  # remove default logger
        log.add(
            #Path(data_path, log_file),
            log_file,
            format=log_format,
            colorize=False,
            enqueue=True,
            level="INFO",
        )

    return Path(data_path)


def setup_session(args: Munch) -> Munch:
    # {'fname': 'myenvironment.yaml', 'user': 'User1', 'skipdata': True, 'overwrite': True, 'debug': None,
    # 'skipmedia': None, 'skipgui': None}

    fail = Munch({"ok": False})

    # Fail if env file isn't readable
    if not Path(args.fname).is_file():
        QMessageBox.critical(
            None,
            "Error Verifying GEMS Environment",
            f"GEMSrun is unable to read the specified environment file: {args.fname}",
            QMessageBox.StandardButton.Ok,
        )
        return fail

    # Ensure successful data logging
    try:
        data_path = setup_data_logging(user=args.user, debug=args.debug)
    except Exception as e:
        QMessageBox.critical(
            None,
            "Test of Data Storage Failed",
            f"There was a problem with the expected data output folder "
            f"({Path.home() / 'Documents' / 'GEMS' / 'Data'})\n{e}",
            QMessageBox.StandardButton.Ok,
        )
        return fail

    # Create Munch based "database" from env yaml file
    try:
        with open(args.fname, "r") as yaml_file:
            database = Munch.fromYAML(yaml_file)
    except Exception as e:
        QMessageBox.critical(
            None,
            "Error Loading GEMS Environment",
            f"Unable to load GEMS Environment from {args.fname}\n{e}",
            QMessageBox.StandardButton.Ok,
        )
        return fail

    # Verify media folder
    try:
        media_path = verify_media_folder(db_path=Path(args.fname))
    except Exception as e:
        QMessageBox.critical(
            None,
            "Media Folder Verification Problem",
            f"Verification of environment media folder failed:\n{e}",
            QMessageBox.StandardButton.Ok,
        )
        return fail

    # Need a temp folder
    try:
        temp_folder = gu.create_temporary_folder()
    except Exception as e:
        QMessageBox.critical(
            None,
            "GEMS Temporary Folder Creation Problem",
            f"Creation of temporary folder failed:\n{e}",
            QMessageBox.StandardButton.Ok,
        )
        return fail

    # Check for missing media files
    missing_media = check_media(db=database, media_folder=media_path)
    if missing_media:
        msg = (
            f"The media folder ({media_path}) is missing media required for "
            f"the GEMS environment ({args.fname}):\n{missing_media}"
        )
        QMessageBox.critical(None, "Some Media Files Are Missing!", msg, QMessageBox.StandardButton.Ok)
        return fail

    # Determine whether tts is going to work
    # log.warning('TEMPORARILY DISABLED CONNECTIVITY CHECK TO AVOID SPAMMING URLS WHILST DEVELOPMENT, '
    #                'SO NO TTS FOR NOW')
    urls = [
        "https://www.google.com",
        "https://www.microsoft.com",
        "https://www.apple.com",
        "https://www.msn.com",
        "https://www.yahoo.com",
        "https://www.duckduckgo.com",
    ]
    if gu.check_connectivity(random.choice(urls)):
        database.Global.Options.TTSFolder = ttsutils.find_tts_folder(media_folder=media_path, temp_folder=temp_folder)
        if database.Global.Options.Preloadresources:
            try:
                database.Global.Options.TTSEnabled = ttsutils.render_tts_from_google(db=database)
            except Exception as e:
                database.Global.Options.TTSEnabled = False
                msg = (
                    f"Unable to use Google's online Text-To-Speech service to render required phrases used in "
                    f"the environment ({e}).\nThe environment will still run, but TTS will be disabled."
                )
                QMessageBox.warning(None, "Problem With Online TTS Service", msg, QMessageBox.StandardButton.Ok)
        else:
            database.Global.Options.TTSEnabled = True
    else:
        database.Global.Options.TTSEnabled = False
        database.Global.Options.TTSFolder = None

    # Add some stuff to option, all of which will be exited if the db is saved back out!
    database.Global.Options.EnvDims = get_initial_view_size(db=database, media_folder=media_path)
    database.Global.Options.PlayMedia = not args.skipmedia
    database.Global.Options.SaveData = not args.skipdata
    database.Global.Options.User = args.user
    database.Global.Options.Overwrite = args.overwrite
    database.Global.Options.Debug = args.debug
    database.Global.Options.MediaPath = media_path
    database.Global.Options.TempFolder = temp_folder
    if args.debug:
        database.Global.Options.ObjectHover += "+Frame+Name"
    database["Variables"] = Munch()

    # ----------------------------------------------------------------------------------------------
    # - temporarily kept bc some old envs lack a volume option
    try:
        _ = database.Global.Options.Volume
    except:
        database.Global.Options.Volume = 1.0
    # ----------------------------------------------------------------------------------------------

    return Munch({"ok": True, "database": database})


def get_initial_view_size(db: Munch, media_folder: Path) -> tuple:
    try:
        assert str(db.Global.Options.Startview).isdigit()
    except AssertionError:
        log.warning(
            f"Global.Options.Startview either not defined, or its current value "
            f"of {db.Global.Options.Startview} is incorrectly specified."
        )

    start_view = db.Views[str(db.Global.Options.Startview)]
    fg_file = Path(media_folder, start_view.Foreground)
    try:
        sz = gu.get_image_dims(fg_file)
    except Exception as e:
        log.warning(
            f"Problem getting dims of {str(fg_file)}. Defaulting to 1024x768 instead...may not lead to good results!",
            context=gu.func_name(),
        )
        sz = (1024, 768)
    return sz


def verify_media_folder(db_path: Path) -> Path:
    """
    make sure that there is a related _media folder next to the env db file
    """
    db_file_name = db_path.stem
    media_folder = Path(db_path.parent, db_file_name + "_media")
    if not media_folder.is_dir():
        raise FileExistsError(
            f"There does not appear to be a folder called {str(media_folder)} in the same location as {str(db_path)}!"
        )
    if not list(media_folder.glob("*.*")):
        raise EnvironmentError(f"This environment's media folder {str(media_folder)} appears to be empty!")
    return media_folder


def check_media(db: Munch, media_folder: Path) -> tuple:
    """
    returns a list of any media files specified by env db, but that are not in the media folder.
    """

    image_files = [view.Foreground for view in db.Views.values()]
    image_files += [view.Background for view in db.Views.values()]
    image_files += [view.Overlay for view in db.Views.values()]
    image_files += [db.Global.Options.Globaloverlay]
    image_files = [img for img in image_files if img]
    missing = [afile for afile in image_files if not Path(media_folder, afile).is_file()]
    return tuple(set(missing))
