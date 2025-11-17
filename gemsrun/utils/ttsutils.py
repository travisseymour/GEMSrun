import contextlib
from itertools import chain
from pathlib import Path
import re

from gtts import gTTS
from munch import Munch

from gemsrun import log
from gemsrun.utils import gemsutils as gu


def find_tts_folder(media_folder: Path, temp_folder: Path) -> Path:
    """
    returns folder for tts file saves. tries to put them in the
    same folder as env media, if that fails (or if tts fails)
    then just returns the temp folder
    """
    tts = None

    with contextlib.suppress(Exception):
        tts = gTTS("Hello.")
    try:
        assert tts is not None
        tts.save(str(Path(media_folder, "Hello.mp3")))
        tts_folder = media_folder
    except Exception:
        tts_folder = Path(temp_folder)

    return tts_folder.resolve()


def render_tts_from_google(db: Munch) -> bool:
    try:
        # "Please wait, creating missing TTS resources..."
        # "Busy Retrieving TTS Data From Google..."

        say_pattern = re.compile(r"\"([^\"]+)\"")
        # figure out where to store this stuff

        tts_folder = db.Global.Options.TTSFolder

        # meta-note: this is pretty efficient, luckily, this is the only time we'll need ALL the actions at once!
        # get global and pocket actions
        actions = list(chain(db.Global.GlobalActions.values(), db.Global.PocketActions.values()))
        # get all view-level actions
        for view in db.Views.values():
            actions.extend(list(view.Actions.values()))
        # get all object level actions
        for view in db.Views.values():
            objects = view.Objects.values()
            for _object in objects:
                actions.extend(list(_object.Actions.values()))

        for action in actions:
            if action.Enabled and "SayText" in action.Action and "[" not in action.Action:
                if match := say_pattern.search(string=action.Action):
                    speech = match.group().strip().replace('"', "")
                    speech_hash = gu.string_hash(speech)
                    speech_filename = f"speech_{speech_hash}.mp3"
                    if not Path(tts_folder, speech_filename).is_file():
                        try:
                            tts = gTTS(speech)
                            tts.save(str(Path(tts_folder, speech_filename)))
                        except Exception as e:
                            tts_ok = False
                            log.warning(f"Unable to pre-render tts media for action {action.Action}, {e}")

        return True
    except Exception as e:
        log.debug(f"Got exception trying to pre-render tts: {e}")
        return False
