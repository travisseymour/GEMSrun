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

import atexit
import os
from pathlib import Path
import threading
from typing import Any

# Suppress pygame welcome message before importing
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from pygame import mixer as pygame_mixer  # For music module access
import pygame.mixer as mixer
from PySide6.QtCore import QObject, QTimer, Signal

from gemsrun import log

# Track current background music file for logging
_current_background_music: str | None = None

"""
Cross-platform audio utilities for GEMSrun using pygame.mixer
Provides simple, reliable audio playback across Windows, macOS, and Linux
"""

# Initialize pygame mixer once at module load
# frequency=44100, size=-16, channels=2, buffer=512 are good defaults
# buffer=512 provides low latency without crackling
try:
    mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    MIXER_AVAILABLE = True
    log.info("pygame.mixer initialized successfully")
except Exception as e:
    MIXER_AVAILABLE = False
    log.error(f"Failed to initialize pygame.mixer: {e}")


def _cleanup_mixer():
    """Cleanup function to be called at exit"""
    if MIXER_AVAILABLE:
        try:
            mixer.quit()
            log.debug("pygame.mixer cleaned up")
        except Exception as e:
            log.debug(f"Error cleaning up pygame.mixer: {e}")


# Register cleanup function to run at exit
atexit.register(_cleanup_mixer)


class CrossPlatformAudioPlayer(QObject):
    """
    Cross-platform audio player using pygame.mixer
    Supports MP3, WAV, OGG formats
    Multiple instances can play simultaneously
    """

    # Signals for async operations
    playback_finished = Signal()
    playback_error = Signal(str)
    _load_complete = Signal(bool)  # Internal signal: True=success, False=failure

    def __init__(self, sound_file: str, volume: float = 1.0, loop: bool = False):
        super().__init__()
        self.sound_file = sound_file
        self.volume = max(0.0, min(1.0, volume))  # Clamp between 0 and 1
        self.loop = loop
        self.sound = None
        self.channel = None
        self.monitor_timer = None
        self._was_playing = False
        self._load_attempted = False
        self._is_loading = False
        self._pending_play = False
        self._load_lock = threading.Lock()

        # Connect internal signal for thread-safe playback trigger
        self._load_complete.connect(self._on_load_complete)

        # Verify file exists, but don't load yet (will load in background on play())
        sound_path = Path(sound_file)
        if not sound_path.exists():
            error_msg = f"Audio file not found: {sound_file}"
            log.error(error_msg)
            # Don't emit signal here - QObject might not be fully initialized

    def _load_sound_sync(self) -> bool:
        """Synchronously load the sound file (called from background thread or direct)"""
        try:
            sound_path = Path(self.sound_file)
            if not sound_path.exists():
                raise FileNotFoundError(f"Audio file not found: {self.sound_file}")

            log.debug(f"Loading audio file: {self.sound_file}")
            sound = mixer.Sound(str(sound_path))
            sound.set_volume(self.volume)

            with self._load_lock:
                self.sound = sound

            log.debug(f"Loaded audio file: {self.sound_file}")
            return True

        except Exception as e:
            error_msg = f"Failed to load audio file {self.sound_file}: {e}"
            log.error(error_msg)
            return False

    def _load_and_play_background(self):
        """Background thread function to load and play audio"""
        with self._load_lock:
            if self._load_attempted:
                return
            self._load_attempted = True
            self._is_loading = True

        success = self._load_sound_sync()

        with self._load_lock:
            self._is_loading = False

        # Emit signal to trigger playback on main thread (thread-safe)
        self._load_complete.emit(success)

    def _on_load_complete(self, success: bool):
        """Handle load completion (runs on main thread via signal)"""
        if success and self._pending_play:
            log.debug("Load complete, playing audio now")
            self._do_play()
        elif not success:
            error_msg = f"Failed to load audio file {self.sound_file}"
            log.error(error_msg)
            self.playback_error.emit(error_msg)

    def _do_play(self) -> bool:
        """Internal method to actually play the sound (assumes sound is loaded)"""
        if self.sound is None:
            return False

        try:
            # Play the sound, loop=-1 for infinite loop, 0 for once
            loops = -1 if self.loop else 0
            self.channel = self.sound.play(loops=loops)

            if self.channel is None:
                raise RuntimeError("No available audio channels")

            self._was_playing = True
            self._pending_play = False
            log.info(
                f"Playing audio: {self.sound_file}, volume={self.volume}, loop={self.loop}"
            )

            # Start monitoring playback state for non-looping sounds
            if not self.loop:
                self.monitor_timer = QTimer()
                self.monitor_timer.timeout.connect(self._check_playback_status)
                self.monitor_timer.start(100)  # Check every 100ms

            return True

        except Exception as e:
            error_msg = f"Failed to play audio: {e}"
            log.error(error_msg)
            self.playback_error.emit(error_msg)
            return False

    def play(self) -> bool:
        """Start audio playback (non-blocking)"""
        if not MIXER_AVAILABLE:
            error_msg = "pygame.mixer not available"
            log.error(error_msg)
            self.playback_error.emit(error_msg)
            return False

        with self._load_lock:
            # If already loaded, play immediately
            if self.sound is not None:
                return self._do_play()

            # If currently loading, just mark as pending
            if self._is_loading:
                self._pending_play = True
                log.debug("Audio is loading, will play when ready")
                return True

            # If already attempted and failed, don't try again
            if self._load_attempted:
                error_msg = "Audio file failed to load previously"
                log.error(error_msg)
                self.playback_error.emit(error_msg)
                return False

            # Start background loading
            self._pending_play = True
            log.debug(f"Starting background load for: {self.sound_file}")
            thread = threading.Thread(
                target=self._load_and_play_background, daemon=True
            )
            thread.start()
            return True

    def stop(self):
        """Stop audio playback"""
        if self.monitor_timer:
            self.monitor_timer.stop()
            self.monitor_timer = None

        if self.channel:
            try:
                self.channel.stop()
                log.debug(f"Stopped audio: {self.sound_file}")
            except Exception as e:
                log.debug(f"Error stopping audio: {e}")
            finally:
                self.channel = None
                self._was_playing = False

    def pause(self):
        """Pause audio playback"""
        if self.channel:
            try:
                self.channel.pause()
                log.debug(f"Paused audio: {self.sound_file}")
            except Exception as e:
                log.debug(f"Error pausing audio: {e}")

    def resume(self):
        """Resume paused audio playback"""
        if self.channel:
            try:
                self.channel.unpause()
                log.debug(f"Resumed audio: {self.sound_file}")
            except Exception as e:
                log.debug(f"Error resuming audio: {e}")

    def is_playing(self) -> bool:
        """Check if audio is currently playing"""
        if self.channel:
            return self.channel.get_busy()
        return False

    def duration(self) -> int:
        """Get audio duration in milliseconds"""
        if self.sound:
            # pygame Sound.get_length() returns seconds as float
            return int(self.sound.get_length() * 1000)
        return 0

    def set_volume(self, volume: float):
        """Set playback volume (0.0 to 1.0)"""
        self.volume = max(0.0, min(1.0, volume))
        if self.sound:
            self.sound.set_volume(self.volume)
            log.debug(f"Set volume to {self.volume} for {self.sound_file}")

    def _check_playback_status(self):
        """Monitor playback status and emit finished signal when done"""
        if not self.is_playing() and self._was_playing:
            self._was_playing = False
            if self.monitor_timer:
                self.monitor_timer.stop()
                self.monitor_timer = None
            log.debug(f"Playback finished: {self.sound_file}")
            self.playback_finished.emit()


def get_audio_backend_info() -> dict[str, Any]:
    """Get information about the audio backend"""
    return {
        "backend": "pygame.mixer",
        "available": MIXER_AVAILABLE,
        "available_backends": ["pygame.mixer"] if MIXER_AVAILABLE else [],
        "mixer_initialized": mixer.get_init() is not None if MIXER_AVAILABLE else False,
        "num_channels": mixer.get_num_channels() if MIXER_AVAILABLE else 0,
    }


# ============================================================================
# Background Music Functions (using pygame.mixer.music)
# ============================================================================
# pygame.mixer.music is separate from mixer.Sound channels:
# - Only one music stream can play at a time
# - Designed for streaming longer audio files
# - Not affected by mixer.Sound operations (StopAllSounds, etc.)
# - Automatically cleaned up when mixer.quit() is called
# ============================================================================


def play_background_music(
    sound_file: str, volume: float = 1.0, loop: bool = False
) -> bool:
    """
    Play background music using pygame.mixer.music.

    Only one background music stream can play at a time. If music is already
    playing, it will be stopped and the new music will start.

    Args:
        sound_file: Path to the audio file
        volume: Volume level (0.0 to 1.0)
        loop: If True, loop the music indefinitely

    Returns:
        True if playback started successfully, False otherwise
    """
    global _current_background_music

    if not MIXER_AVAILABLE:
        log.error("pygame.mixer not available for background music")
        return False

    try:
        # Stop any currently playing background music
        if pygame_mixer.music.get_busy():
            pygame_mixer.music.stop()
            log.debug(f"Stopped previous background music: {_current_background_music}")

        # Load and play the new music
        pygame_mixer.music.load(sound_file)
        pygame_mixer.music.set_volume(max(0.0, min(1.0, volume)))

        # -1 for infinite loop, 0 for play once
        loops = -1 if loop else 0
        pygame_mixer.music.play(loops=loops)

        _current_background_music = sound_file
        log.info(
            f"Playing background music: {sound_file}, volume={volume}, loop={loop}"
        )
        return True

    except Exception as e:
        log.error(f"Failed to play background music {sound_file}: {e}")
        return False


def stop_background_music() -> bool:
    """
    Stop the currently playing background music.

    Returns:
        True if music was stopped, False if no music was playing or error occurred
    """
    global _current_background_music

    if not MIXER_AVAILABLE:
        log.error("pygame.mixer not available")
        return False

    try:
        if pygame_mixer.music.get_busy():
            pygame_mixer.music.stop()
            log.info(f"Stopped background music: {_current_background_music}")
            _current_background_music = None
            return True
        else:
            log.debug("No background music was playing")
            return False

    except Exception as e:
        log.error(f"Failed to stop background music: {e}")
        return False


def is_background_music_playing() -> bool:
    """Check if background music is currently playing."""
    if not MIXER_AVAILABLE:
        return False
    try:
        return pygame_mixer.music.get_busy()
    except Exception:
        return False


def set_background_music_volume(volume: float) -> None:
    """Set the volume for background music (0.0 to 1.0)."""
    if MIXER_AVAILABLE:
        try:
            pygame_mixer.music.set_volume(max(0.0, min(1.0, volume)))
        except Exception as e:
            log.error(f"Failed to set background music volume: {e}")
