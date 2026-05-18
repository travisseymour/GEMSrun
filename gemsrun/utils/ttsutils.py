from concurrent.futures import ThreadPoolExecutor, as_completed
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

    try:
        temp_folder.mkdir(parents=True, exist_ok=True)
        # Test if we can write to the temp folder (no network call needed)
        test_path = Path(temp_folder, "tts_test.tmp")
        test_path.write_text("test")
        test_path.unlink(missing_ok=True)
        tts_folder = temp_folder
    except Exception:
        tts_folder = Path(tempfile.gettempdir(), "gemsruntemp")
        tts_folder.mkdir(parents=True, exist_ok=True)

    return tts_folder.resolve()


def _download_tts_mp3(speech: str, speech_hash: str, temp_folder: Path) -> Path | None:
    """Download a single TTS phrase as mp3. Returns the mp3 path on success."""
    temp_mp3 = temp_folder / f"speech_{speech_hash}.mp3"
    try:
        tts = gTTS(speech)
        tts.save(str(temp_mp3))
        return temp_mp3
    except Exception as e:
        log.warning(f"Unable to download TTS for '{speech[:30]}...': {e}")
        return None


def render_tts_from_google(db: Munch) -> bool:
    """
    Pre-render TTS resources and cache them as WAV files.
    Downloads mp3 to temp folder in parallel, then converts to wav sequentially
    (pygame.mixer is not thread-safe).
    """
    try:
        say_pattern = re.compile(r"\"([^\"]+)\"")

        # Temp folder for mp3 downloads
        temp_folder = Path(tempfile.gettempdir(), "gemsruntemp")
        temp_folder.mkdir(parents=True, exist_ok=True)

        # Get all actions from global, pocket, views, and objects
        actions = list(chain(db.Global.GlobalActions.values(), db.Global.PocketActions.values()))
        for view in db.Views.values():
            actions.extend(list(view.Actions.values()))
            for _object in view.Objects.values():
                actions.extend(list(_object.Actions.values()))

        # Collect unique phrases that need downloading (deduplicate by hash)
        seen_hashes: set[str] = set()
        phrases_to_download: list[tuple[str, str]] = []
        for action in actions:
            # Skip actions with variable specifiers (can't pre-render)
            if action.Enabled and "SayText" in action.Action and "[" not in action.Action and "$" not in action.Action:
                if match := say_pattern.search(string=action.Action):
                    speech = match.group().strip().replace('"', "")
                    speech_hash = gu.string_hash(speech)

                    if speech_hash in seen_hashes:
                        continue
                    seen_hashes.add(speech_hash)

                    # Skip if already cached as WAV
                    if audiocache.is_tts_cached(speech_hash):
                        log.debug(f"TTS already cached: speech_{speech_hash}.wav")
                        continue

                    phrases_to_download.append((speech, speech_hash))

        if not phrases_to_download:
            return True

        print(f"downloading {len(phrases_to_download)} TTS phrase(s)...")

        # Phase 1: Download mp3s in parallel (network I/O, thread-safe)
        downloaded: list[tuple[Path, str]] = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(_download_tts_mp3, speech, speech_hash, temp_folder): (
                    speech,
                    speech_hash,
                )
                for speech, speech_hash in phrases_to_download
            }
            for future in as_completed(futures):
                speech, speech_hash = futures[future]
                mp3_path = future.result()
                if mp3_path is not None:
                    downloaded.append((mp3_path, speech_hash))

        # Phase 2: Convert to WAV sequentially (pygame.mixer is not thread-safe)
        for mp3_path, speech_hash in downloaded:
            cached_wav = audiocache.cache_tts_from_mp3(mp3_path, speech_hash)
            if cached_wav:
                log.debug(f"Pre-rendered TTS: speech_{speech_hash} -> {cached_wav.name}")
            # Clean up temp mp3
            mp3_path.unlink(missing_ok=True)

        print(f"TTS pre-rendering complete ({len(downloaded)}/{len(phrases_to_download)}).")
        return True
    except Exception as e:
        log.debug(f"Got exception trying to pre-render tts: {e}")
        return False
