"""
Cross-platform audio utilities for GEMSrun
Provides fallback mechanisms for audio playback when QtMultimedia backends are unavailable
"""

import subprocess
import platform
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtMultimedia import QSoundEffect, QAudioDevice, QMediaDevices

from gemsrun import log


class AudioBackend:
    """Enum-like class for audio backend types"""
    QMEDIAPLAYER = "qmediaplayer"
    QSOUNDEFFECT = "qsoundeffect"
    SYSTEM_COMMAND = "system_command"


class CrossPlatformAudioPlayer(QObject):
    """
    Cross-platform audio player with multiple fallback mechanisms
    """
    
    # Signals for async operations
    playback_finished = Signal()
    playback_error = Signal(str)
    
    def __init__(self, sound_file: str, volume: float = 1.0, loop: bool = False):
        super().__init__()
        self.sound_file = sound_file
        self.volume = max(0.0, min(1.0, volume))  # Clamp between 0 and 1
        self.loop = loop
        self.is_playing_flag = False
        self.duration_ms = 0
        self.current_backend = None
        self.player = None
        self.process = None
        self.timer = None
        
        # Try backends in order of preference
        self.backends = self._detect_available_backends()
        log.debug(f"Available audio backends: {self.backends}")
    
    def _detect_available_backends(self) -> list:
        """Detect which audio backends are available on this system"""
        backends = []
        
        # Test QMediaPlayer availability
        try:
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
            # Try to create instances to test availability
            test_player = QMediaPlayer()
            test_output = QAudioOutput()
            if test_player.hasAudio() and test_output.isAvailable():
                backends.append(AudioBackend.QMEDIAPLAYER)
                log.debug("QMediaPlayer backend available")
        except Exception as e:
            log.debug(f"QMediaPlayer backend not available: {e}")
        
        # Test QSoundEffect availability
        try:
            from PySide6.QtMultimedia import QSoundEffect
            test_effect = QSoundEffect()
            # QSoundEffect doesn't have isAvailable() in newer PySide6 versions
            # Just test if we can create it without errors
            backends.append(AudioBackend.QSOUNDEFFECT)
            log.debug("QSoundEffect backend available")
        except Exception as e:
            log.debug(f"QSoundEffect backend not available: {e}")
        
        # Test system command availability
        if self._test_system_audio_commands():
            backends.append(AudioBackend.SYSTEM_COMMAND)
            log.debug("System audio command backend available")
        
        return backends
    
    def _test_system_audio_commands(self) -> bool:
        """Test if system audio commands are available"""
        commands = self._get_system_audio_commands()
        for cmd in commands:
            try:
                result = subprocess.run([cmd, "--version"], 
                                      capture_output=True, 
                                      timeout=2)
                if result.returncode == 0:
                    return True
            except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
                continue
        return False
    
    def _get_system_audio_commands(self) -> list:
        """Get appropriate system audio commands for the current platform"""
        system = platform.system().lower()
        
        if system == "linux":
            return ["paplay", "aplay", "ffplay", "play"]
        elif system == "darwin":  # macOS
            return ["afplay", "ffplay"]
        elif system == "windows":
            return ["ffplay", "powershell"]
        else:
            return ["ffplay"]
    
    def play(self) -> bool:
        """Start audio playback using the best available backend"""
        if not self.backends:
            error_msg = "No audio backends available"
            log.error(error_msg)
            self.playback_error.emit(error_msg)
            return False
        
        # Use the first available backend
        backend = self.backends[0]
        self.current_backend = backend
        
        try:
            if backend == AudioBackend.QMEDIAPLAYER:
                return self._play_with_qmediaplayer()
            elif backend == AudioBackend.QSOUNDEFFECT:
                return self._play_with_qsoundeffect()
            elif backend == AudioBackend.SYSTEM_COMMAND:
                return self._play_with_system_command()
        except Exception as e:
            log.error(f"Audio playback failed with backend {backend}: {e}")
            # Try next backend if available
            if len(self.backends) > 1:
                log.info(f"Falling back to next available backend")
                self.backends.pop(0)
                return self.play()
            else:
                self.playback_error.emit(str(e))
                return False
        
        return True
    
    def _play_with_qmediaplayer(self) -> bool:
        """Play audio using QMediaPlayer"""
        try:
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
            from PySide6.QtCore import QUrl
            
            self.player = QMediaPlayer()
            audio_output = QAudioOutput()
            audio_output.setVolume(self.volume * 100)
            self.player.setAudioOutput(audio_output)
            
            url = QUrl.fromLocalFile(self.sound_file)
            self.player.setSource(url)
            
            # Connect signals
            self.player.playbackStateChanged.connect(self._on_playback_state_changed)
            self.player.errorOccurred.connect(self._on_error_occurred)
            
            self.player.play()
            self.is_playing_flag = True
            
            # Get duration for non-looping playback
            if not self.loop:
                self.timer = QTimer()
                self.timer.timeout.connect(self._check_duration)
                self.timer.start(100)  # Check every 100ms
            
            log.debug("Playing audio with QMediaPlayer")
            return True
            
        except Exception as e:
            log.error(f"QMediaPlayer playback failed: {e}")
            raise
    
    def _play_with_qsoundeffect(self) -> bool:
        """Play audio using QSoundEffect (better for short sounds)"""
        try:
            from PySide6.QtMultimedia import QSoundEffect
            from PySide6.QtCore import QUrl
            
            self.player = QSoundEffect()
            self.player.setSource(QUrl.fromLocalFile(self.sound_file))
            self.player.setVolume(self.volume)
            
            # Connect signals
            self.player.playingChanged.connect(self._on_playing_changed)
            
            self.player.play()
            self.is_playing_flag = True
            
            log.debug("Playing audio with QSoundEffect")
            return True
            
        except Exception as e:
            log.error(f"QSoundEffect playback failed: {e}")
            raise
    
    def _play_with_system_command(self) -> bool:
        """Play audio using system command"""
        try:
            commands = self._get_system_audio_commands()
            sound_path = Path(self.sound_file)
            
            if not sound_path.exists():
                raise FileNotFoundError(f"Audio file not found: {self.sound_file}")
            
            # Try each command until one works
            for cmd in commands:
                try:
                    if cmd == "paplay":
                        args = ["paplay", str(sound_path)]
                    elif cmd == "aplay":
                        args = ["aplay", str(sound_path)]
                    elif cmd == "afplay":
                        args = ["afplay", str(sound_path)]
                    elif cmd == "ffplay":
                        args = ["ffplay", "-nodisp", "-autoexit", str(sound_path)]
                    elif cmd == "play":
                        args = ["play", str(sound_path)]
                    elif cmd == "powershell":
                        args = ["powershell", "-c", f"(New-Object Media.SoundPlayer '{sound_path}').PlaySync()"]
                    else:
                        continue
                    
                    # Start process
                    self.process = subprocess.Popen(args, 
                                                  stdout=subprocess.DEVNULL, 
                                                  stderr=subprocess.DEVNULL)
                    
                    self.is_playing_flag = True
                    
                    # Monitor process in a separate thread
                    monitor_thread = threading.Thread(target=self._monitor_process)
                    monitor_thread.daemon = True
                    monitor_thread.start()
                    
                    log.debug(f"Playing audio with system command: {cmd}")
                    return True
                    
                except (FileNotFoundError, subprocess.SubprocessError):
                    continue
            
            raise RuntimeError("No system audio commands available")
            
        except Exception as e:
            log.error(f"System command playback failed: {e}")
            raise
    
    def stop(self):
        """Stop audio playback"""
        self.is_playing_flag = False
        
        if self.timer:
            self.timer.stop()
            self.timer = None
        
        if self.player:
            if hasattr(self.player, 'stop'):
                self.player.stop()
            elif hasattr(self.player, 'setLoops'):
                self.player.setLoops(0)
        
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
            except Exception:
                pass
            self.process = None
    
    def is_playing(self) -> bool:
        """Check if audio is currently playing"""
        return self.is_playing_flag
    
    def duration(self) -> int:
        """Get audio duration in milliseconds"""
        return self.duration_ms
    
    def _on_playback_state_changed(self, state):
        """Handle QMediaPlayer playback state changes"""
        if state == QMediaPlayer.PlaybackState.StoppedState:
            self.is_playing_flag = False
            if not self.loop:
                self.playback_finished.emit()
    
    def _on_playing_changed(self, playing):
        """Handle QSoundEffect playing state changes"""
        self.is_playing_flag = playing
        if not playing and not self.loop:
            self.playback_finished.emit()
    
    def _on_error_occurred(self, error, error_string):
        """Handle QMediaPlayer errors"""
        log.error(f"QMediaPlayer error: {error_string}")
        self.playback_error.emit(error_string)
    
    def _check_duration(self):
        """Check if QMediaPlayer has finished playing"""
        if self.player and hasattr(self.player, 'duration'):
            duration = self.player.duration()
            if duration > 0:
                self.duration_ms = duration
                if not self.player.isPlaying():
                    self.is_playing_flag = False
                    self.playback_finished.emit()
                    if self.timer:
                        self.timer.stop()
    
    def _monitor_process(self):
        """Monitor system command process"""
        if self.process:
            self.process.wait()
            self.is_playing_flag = False
            if not self.loop:
                self.playback_finished.emit()


def get_audio_backend_info() -> Dict[str, Any]:
    """Get information about available audio backends"""
    player = CrossPlatformAudioPlayer("dummy.wav")
    return {
        "available_backends": player.backends,
        "system": platform.system(),
        "system_commands": player._get_system_audio_commands()
    }
