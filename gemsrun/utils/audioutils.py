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

from pathlib import Path
from typing import Any

import rpaudio
from PySide6.QtCore import QObject, QTimer, Signal

from gemsrun import log

"""
Cross-platform audio utilities for GEMSrun using rpaudio
Provides simple, reliable audio playback across Windows, macOS, and Linux
"""


class CrossPlatformAudioPlayer(QObject):
    """
    Cross-platform audio player using rpaudio (Rust-based audio library)
    Supports MP3, WAV, OGG, FLAC, Vorbis formats
    Multiple instances can play simultaneously
    """

    # Signals for async operations
    playback_finished = Signal()
    playback_error = Signal(str)

    def __init__(self, sound_file: str, volume: float = 1.0, loop: bool = False):
        super().__init__()
        self.sound_file = sound_file
        self.volume = max(0.0, min(1.0, volume))  # Clamp between 0 and 1
        self.loop = loop
        self.sink = None
        self._is_paused = False
        self._should_loop = loop
        self._playback_monitor_timer = None

        # Verify file exists
        sound_path = Path(sound_file)
        if not sound_path.exists():
            error_msg = f"Audio file not found: {sound_file}"
            log.error(error_msg)
            return

        try:
            # Initialize AudioSink with callback for playback finished
            self.sink = rpaudio.AudioSink(callback=self._on_playback_finished)
            self.sink.load_audio(str(sound_path))
            self.sink.set_volume(self.volume)
            log.debug(f"Loaded audio file: {self.sound_file}")
        except Exception as e:
            error_msg = f"Failed to load audio file {self.sound_file}: {e}"
            log.error(error_msg)
            self.playback_error.emit(error_msg)
            self.sink = None

    def _on_playback_finished(self):
        """Callback invoked when audio finishes playing (from rpaudio)"""
        log.debug(f"Playback finished callback for: {self.sound_file}")

        # If looping is enabled, restart playback
        if self._should_loop and self.sink and not self._is_paused:
            try:
                log.debug(f"Looping audio: {self.sound_file}")
                self.sink.play()
                return
            except Exception as e:
                log.error(f"Error looping audio: {e}")

        # Not looping, emit finished signal
        self.playback_finished.emit()

    def play(self) -> bool:
        """Start audio playback"""
        if self.sink is None:
            error_msg = "Audio sink not initialized"
            log.error(error_msg)
            self.playback_error.emit(error_msg)
            return False

        try:
            self.sink.play()
            self._is_paused = False
            log.info(f"Playing audio: {self.sound_file}, volume={self.volume}, loop={self.loop}")
            return True
        except Exception as e:
            error_msg = f"Failed to play audio: {e}"
            log.error(error_msg)
            self.playback_error.emit(error_msg)
            return False

    def stop(self):
        """Stop audio playback"""
        if self.sink:
            try:
                self.sink.stop()
                self._is_paused = False
                self._should_loop = False  # Disable looping when explicitly stopped
                log.debug(f"Stopped audio: {self.sound_file}")
            except Exception as e:
                log.debug(f"Error stopping audio: {e}")

    def pause(self):
        """Pause audio playback"""
        if self.sink:
            try:
                self.sink.pause()
                self._is_paused = True
                log.debug(f"Paused audio: {self.sound_file}")
            except Exception as e:
                log.debug(f"Error pausing audio: {e}")

    def resume(self):
        """Resume paused audio playback"""
        if self.sink and self._is_paused:
            try:
                self.sink.play()
                self._is_paused = False
                log.debug(f"Resumed audio: {self.sound_file}")
            except Exception as e:
                log.debug(f"Error resuming audio: {e}")

    def is_playing(self) -> bool:
        """Check if audio is currently playing"""
        if self.sink:
            try:
                return self.sink.is_playing and not self._is_paused
            except Exception:
                return False
        return False

    def duration(self) -> int:
        """Get audio duration in milliseconds"""
        if self.sink:
            try:
                # Get metadata and extract duration
                metadata = self.sink.metadata_dict
                if 'duration' in metadata:
                    # Convert seconds to milliseconds
                    return int(float(metadata['duration']) * 1000)
            except Exception as e:
                log.debug(f"Error getting duration: {e}")
        return 0

    def set_volume(self, volume: float):
        """Set playback volume (0.0 to 1.0)"""
        self.volume = max(0.0, min(1.0, volume))
        if self.sink:
            try:
                self.sink.set_volume(self.volume)
                log.debug(f"Set volume to {self.volume} for {self.sound_file}")
            except Exception as e:
                log.debug(f"Error setting volume: {e}")


def get_audio_backend_info() -> dict[str, Any]:
    """Get information about the audio backend"""
    try:
        # Test if rpaudio is working by creating a temporary sink
        test_sink = rpaudio.AudioSink()
        available = True
    except Exception:
        available = False

    return {
        "backend": "rpaudio",
        "available": available,
        "available_backends": ["rpaudio"] if available else [],
        "supported_formats": ["MP3", "WAV", "OGG", "FLAC", "Vorbis"],
    }
