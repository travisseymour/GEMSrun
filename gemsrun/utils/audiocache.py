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

from collections.abc import Callable
import os
from pathlib import Path
import re
import shutil
import wave

from munch import Munch

from gemsrun import log

# Suppress pygame welcome message before importing
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame.mixer as mixer

# Compressed audio formats that benefit from pre-conversion to WAV
COMPRESSED_FORMATS = {".mp3", ".ogg", ".flac"}

# Cache folder location
CACHE_FOLDER = Path.home() / "Documents" / "GEMS" / "Cache"


def get_cache_folder() -> Path:
    """Get the cache folder path, creating it if necessary."""
    CACHE_FOLDER.mkdir(parents=True, exist_ok=True)
    return CACHE_FOLDER


def clear_cache() -> bool:
    """Clear all files from the cache folder."""
    try:
        if CACHE_FOLDER.exists():
            shutil.rmtree(CACHE_FOLDER)
            log.info(f"Cleared audio cache at {CACHE_FOLDER}")
        return True
    except Exception as e:
        log.error(f"Failed to clear cache: {e}")
        return False


def is_compressed_audio(file_path: str | Path) -> bool:
    """Check if a file is a compressed audio format that should be cached."""
    return Path(file_path).suffix.lower() in COMPRESSED_FORMATS


def get_cached_wav_path(original_path: str | Path) -> Path:
    """Get the path where the cached WAV file would be stored."""
    original = Path(original_path)
    return get_cache_folder() / f"{original.stem}.wav"


def is_cached(original_path: str | Path) -> bool:
    """Check if a WAV version of the file exists in cache."""
    return get_cached_wav_path(original_path).exists()


def convert_to_wav(source_path: str | Path, dest_path: str | Path) -> bool:
    """
    Convert a compressed audio file to WAV format using pygame.

    This loads the audio into pygame.mixer.Sound (which decodes it),
    then extracts the raw PCM data and writes it as a WAV file.
    """
    source_path = Path(source_path)
    dest_path = Path(dest_path)

    # Ensure mixer is initialized
    if not mixer.get_init():
        try:
            mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        except Exception as e:
            log.error(f"Failed to initialize mixer for conversion: {e}")
            return False

    try:
        # Load the sound (pygame decodes compressed formats)
        sound = mixer.Sound(str(source_path))

        # Get raw audio data
        raw_data = sound.get_raw()

        # Get mixer settings to determine WAV parameters
        frequency, format_bits, channels = mixer.get_init()

        # Convert format_bits to sample width in bytes
        # pygame uses negative values for signed formats
        sample_width = abs(format_bits) // 8

        # Write to WAV file
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(dest_path), "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(frequency)
            wav_file.writeframes(raw_data)

        log.debug(f"    CACHE CREATED: {source_path.name} -> {dest_path.name}")
        return True

    except Exception as e:
        log.error(f"    CACHE FAILED: {source_path} -> {e}")
        return False


def ensure_cached(original_path: str | Path) -> Path | None:
    """
    Ensure a compressed audio file has a cached WAV version.

    Returns the path to use for playback:
    - Cached WAV path if file is compressed and cached/converted successfully
    - Original path if file is not compressed
    - None if conversion failed
    """
    original = Path(original_path)

    if not is_compressed_audio(original):
        log.debug(f"    CACHE SKIP: {original.name} (not compressed format)")
        return original

    cached_path = get_cached_wav_path(original)

    if cached_path.exists():
        log.debug(f"    CACHE EXISTS: {original.name} -> {cached_path.name}")
        return cached_path

    log.debug(f"    CACHE CONVERTING: {original.name}...")
    if convert_to_wav(original, cached_path):
        return cached_path

    # Conversion failed, fall back to original
    log.warning(f"Cache conversion failed for {original.name}, using original")
    return original


def get_playback_path(original_path: str | Path) -> Path:
    """
    Get the best path for audio playback.

    Checks cache first for WAV version of compressed files,
    falls back to original if not cached.
    """
    original = Path(original_path)

    if not is_compressed_audio(original):
        return original

    cached_path = get_cached_wav_path(original)
    if cached_path.exists():
        return cached_path

    return original


def find_playsound_files_in_database(db: Munch, media_path: str | Path) -> list[Path]:
    """
    Find all audio files referenced in PlaySound actions in the database.

    Walks through all views and objects looking for PlaySound actions,
    extracts the sound file parameter, and returns a list of full paths
    to compressed audio files that should be cached.
    """
    media_path = Path(media_path)
    sound_files = set()

    # Regex to extract filename from PlaySound action
    # Matches: PlaySound("filename.mp3", ...) or PlaySound('filename.mp3', ...)
    playsound_pattern = re.compile(r'PlaySound\s*\(\s*["\']([^"\']+)["\']')

    def extract_sound_files_from_actions(actions: dict):
        """Extract sound files from a dictionary of actions."""
        for action in actions.values():
            if hasattr(action, "Action") and "PlaySound" in str(action.Action):
                match = playsound_pattern.search(str(action.Action))
                if match:
                    filename = match.group(1)
                    # Resolve full path
                    file_path = media_path / filename
                    if file_path.exists() and is_compressed_audio(file_path):
                        sound_files.add(file_path)

    # Check global actions
    if hasattr(db, "Global") and hasattr(db.Global, "GlobalActions"):
        extract_sound_files_from_actions(db.Global.GlobalActions)

    # Check pocket actions
    if hasattr(db, "Global") and hasattr(db.Global, "PocketActions"):
        extract_sound_files_from_actions(db.Global.PocketActions)

    # Check all views
    if hasattr(db, "Views"):
        for view in db.Views.values():
            # View-level actions
            if hasattr(view, "Actions"):
                extract_sound_files_from_actions(view.Actions)

            # Object-level actions within the view
            if hasattr(view, "Objects"):
                for obj in view.Objects.values():
                    if hasattr(obj, "Actions"):
                        extract_sound_files_from_actions(obj.Actions)

    return sorted(sound_files)


def find_playsound_files_for_view(db: Munch, view_id: int | str, media_path: str | Path) -> list[Path]:
    """
    Find all audio files referenced in PlaySound actions for a specific view.

    Only looks at actions in the specified view and its objects.
    """
    media_path = Path(media_path)
    sound_files = set()

    playsound_pattern = re.compile(r'PlaySound\s*\(\s*["\']([^"\']+)["\']')

    def extract_sound_files_from_actions(actions: dict):
        for action in actions.values():
            if hasattr(action, "Action") and "PlaySound" in str(action.Action):
                match = playsound_pattern.search(str(action.Action))
                if match:
                    filename = match.group(1)
                    file_path = media_path / filename
                    if file_path.exists() and is_compressed_audio(file_path):
                        sound_files.add(file_path)

    view_key = str(view_id)
    if hasattr(db, "Views") and view_key in db.Views:
        view = db.Views[view_key]

        # View-level actions
        if hasattr(view, "Actions"):
            extract_sound_files_from_actions(view.Actions)

        # Object-level actions
        if hasattr(view, "Objects"):
            for obj in view.Objects.values():
                if hasattr(obj, "Actions"):
                    extract_sound_files_from_actions(obj.Actions)

    return sorted(sound_files)


def preload_audio_files(files: list[Path], progress_callback: Callable[[int, int, str], None] | None = None) -> int:
    """
    Preload a list of audio files by converting them to cached WAV files.

    Args:
        files: List of audio file paths to preload
        progress_callback: Optional callback(current, total, filename) for progress updates

    Returns:
        Number of files successfully cached
    """
    if not files:
        return 0

    successful = 0
    total = len(files)

    for i, file_path in enumerate(files):
        if progress_callback:
            progress_callback(i + 1, total, file_path.name)

        result = ensure_cached(file_path)
        if result and result != file_path:
            successful += 1

    return successful
