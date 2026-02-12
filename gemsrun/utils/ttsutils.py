import contextlib
from itertools import chain
from pathlib import Path
import re
import tempfile

from gtts import gTTS
from munch import Munch

from gemsrun import log
from gemsrun.utils import audiocache, gemsutils as gu


def find_tts_folder(media_folder: Path, temp_folder: Path) -> Path:
    """
    Returns folder for temporary TTS mp3 file downloads.
    TTS audio is now cached as WAV in Documents/GEMS/Cache.
    This folder is just used as a temp staging area for mp3 downloads.

    Args:
        media_folder: Legacy parameter, no longer used (kept for API compatibility)
        temp_folder: Preferred temp folder location
    """
    _ = media_folder  # Unused, kept for API compatibility

    tts = None
    with contextlib.suppress(Exception):
        tts = gTTS("Hello.")

    try:
        assert tts is not None
        # Test if we can write to the temp folder
        test_path = Path(temp_folder, "tts_test.mp3")
        tts.save(str(test_path))
        tts_folder = temp_folder
        # Clean up test file
        test_path.unlink(missing_ok=True)
    except Exception:
        tts_folder = Path(tempfile.gettempdir(), "gemsruntemp")
        tts_folder.mkdir(parents=True, exist_ok=True)

    return tts_folder.resolve()


def render_tts_from_google(db: Munch) -> bool:
    """
    Pre-render TTS resources and cache them as WAV files.
    Downloads mp3 to temp folder, converts to wav in cache.
    """
    try:
        say_pattern = re.compile(r"\"([^\"]+)\"")

        # Temp folder for mp3 downloads
        temp_folder = Path(tempfile.gettempdir(), "gemsruntemp")
        temp_folder.mkdir(parents=True, exist_ok=True)

        # Get all actions from global, pocket, views, and objects
        actions = list(
            chain(db.Global.GlobalActions.values(), db.Global.PocketActions.values())
        )
        for view in db.Views.values():
            actions.extend(list(view.Actions.values()))
        for view in db.Views.values():
            objects = view.Objects.values()
            for _object in objects:
                actions.extend(list(_object.Actions.values()))

        for action in actions:
            # Skip actions with variable specifiers (can't pre-render)
            if (
                action.Enabled
                and "SayText" in action.Action
                and "[" not in action.Action
                and "$" not in action.Action
            ):
                if match := say_pattern.search(string=action.Action):
                    speech = match.group().strip().replace('"', "")
                    speech_hash = gu.string_hash(speech)

                    # Skip if already cached as WAV
                    if audiocache.is_tts_cached(speech_hash):
                        log.debug(f"TTS already cached: speech_{speech_hash}.wav")
                        continue

                    # Download mp3 to temp folder
                    temp_mp3 = temp_folder / f"speech_{speech_hash}.mp3"
                    try:
                        tts = gTTS(speech)
                        tts.save(str(temp_mp3))
                    except Exception as e:
                        log.warning(
                            f"Unable to download TTS for action {action.Action}: {e}"
                        )
                        continue

                    # Convert to WAV and cache
                    cached_wav = audiocache.cache_tts_from_mp3(temp_mp3, speech_hash)
                    if cached_wav:
                        log.debug(
                            f"Pre-rendered TTS: {speech[:30]}... -> {cached_wav.name}"
                        )

        return True
    except Exception as e:
        log.debug(f"Got exception trying to pre-render tts: {e}")
        return False
