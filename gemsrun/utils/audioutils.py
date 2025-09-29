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
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices
            # Try to create instances to test availability
            test_player = QMediaPlayer()
            test_output = QAudioOutput()
            
            # Check if we have audio devices available
            audio_devices = QMediaDevices.audioOutputs()
            log.debug(f"Audio devices available: {len(audio_devices)}")
            
            # We cannot rely on hasAudio() here because no source is set yet; just ensure construction works
            if test_output is not None and test_player is not None and len(audio_devices) > 0:
                backends.append(AudioBackend.QMEDIAPLAYER)
                log.debug("QMediaPlayer backend available")
            else:
                log.debug(f"QMediaPlayer backend not available - output:{test_output is not None}, player:{test_player is not None}, devices:{len(audio_devices)}")
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
        
        # On macOS, prioritize system commands if Qt multimedia is having issues
        if platform.system() == "Darwin" and backends:
            log.debug(f"macOS detected, backends before reorder: {backends}")
            if AudioBackend.SYSTEM_COMMAND in backends:
                # Move system command to front for macOS
                backends = [AudioBackend.SYSTEM_COMMAND] + [b for b in backends if b != AudioBackend.SYSTEM_COMMAND]
            log.debug(f"macOS detected, backends after reorder: {backends}")
        
        # On Windows, prioritize system commands over Qt multimedia
        elif platform.system() == "Windows" and backends:
            log.debug(f"Windows detected, backends before reorder: {backends}")
            if AudioBackend.SYSTEM_COMMAND in backends:
                # Move system command to front for Windows
                backends = [AudioBackend.SYSTEM_COMMAND] + [b for b in backends if b != AudioBackend.SYSTEM_COMMAND]
            log.debug(f"Windows detected, backends after reorder: {backends}")
        
        return backends
    
    def _test_system_audio_commands(self) -> bool:
        """Test if system audio commands are available"""
        commands = self._get_system_audio_commands()
        for cmd in commands:
            try:
                # afplay doesn't have a --version flag, test differently
                if cmd == "afplay":
                    result = subprocess.run([cmd], 
                                          capture_output=True, 
                                          timeout=2)
                    # afplay will error without a file argument, but that means it exists
                    log.debug(f"Found afplay command on macOS")
                    return True
                elif cmd == "powershell":
                    # Check if powershell is available
                    result = subprocess.run([cmd, "-Command", "Get-Host"], 
                                          capture_output=True, 
                                          timeout=2)
                    if result.returncode == 0:
                        log.debug(f"Found powershell command on Windows")
                        return True
                else:
                    result = subprocess.run([cmd, "--version"], 
                                          capture_output=True, 
                                          timeout=2)
                    if result.returncode == 0:
                        log.debug(f"Found {cmd} command")
                        return True
            except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError) as e:
                log.debug(f"Command {cmd} not available: {e}")
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
        
        # Choose backend based on file type and availability
        suffix = Path(self.sound_file).suffix.lower()
        is_wav = suffix in [".wav", ".wave"]
        is_short_effect_candidate = is_wav  # QSoundEffect is reliable for WAV only

        preferred_order = []
        if is_short_effect_candidate and AudioBackend.QSOUNDEFFECT in self.backends:
            preferred_order.append(AudioBackend.QSOUNDEFFECT)
        if AudioBackend.QMEDIAPLAYER in self.backends:
            preferred_order.append(AudioBackend.QMEDIAPLAYER)
        if AudioBackend.SYSTEM_COMMAND in self.backends:
            preferred_order.append(AudioBackend.SYSTEM_COMMAND)

        # Fallback to detected order if nothing matched
        if not preferred_order:
            preferred_order = self.backends[:]

        backend = preferred_order[0]
        self.current_backend = backend
        
        log.info(f"Selected audio backend: {backend} for file {self.sound_file}")
        
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
            remaining = [b for b in preferred_order if b != backend]
            if remaining:
                log.info(f"Falling back to next available backend")
                # Temporarily set backends to remaining for this attempt
                original = self.backends
                self.backends = remaining
                try:
                    return self.play()
                finally:
                    self.backends = original
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
            
            # Check if audio output is available (method varies by PySide6 version)
            try:
                if hasattr(audio_output, 'isAvailable') and not audio_output.isAvailable():
                    log.warning("QAudioOutput not available")
                    raise RuntimeError("QAudioOutput not available")
            except AttributeError:
                # Old PySide6 versions don't have isAvailable, check available devices instead
                from PySide6.QtMultimedia import QMediaDevices
                audio_devices = QMediaDevices.audioOutputs()
                if len(audio_devices) == 0:
                    log.warning("No audio output devices available")
                    raise RuntimeError("No audio output devices available")
            
            # QAudioOutput volume range is 0.0 - 1.0 in Qt6
            audio_output.setVolume(float(self.volume))
            self.player.setAudioOutput(audio_output)
            
            url = QUrl.fromLocalFile(self.sound_file)
            self.player.setSource(url)
            
            # Connect signals
            self.player.playbackStateChanged.connect(self._on_playback_state_changed)
            self.player.errorOccurred.connect(self._on_error_occurred)
            
            log.info(f"QMediaPlayer: Playing {self.sound_file}, volume={self.volume}")
            if hasattr(audio_output, 'isAvailable'):
                log.debug(f"Audio output available: {audio_output.isAvailable()}")
            log.debug(f"Audio output volume: {audio_output.volume()}")
            log.debug(f"Media player has audio: {self.player.hasAudio()}")
            
            self.player.play()
            self.is_playing_flag = True
            
            # Check playback state after a short delay
            QTimer.singleShot(100, self._log_playback_status)
            
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
            # QSoundEffect volume range is 0.0 - 1.0
            self.player.setVolume(float(self.volume))
            
            # Connect signals
            # Some PySide6 builds emit playingChanged() without args; accept optional param
            self.player.playingChanged.connect(lambda *args: self._on_playing_changed(args[0] if args else self.player.isPlaying()))
            
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
            
            # Prefer commands based on file type
            suffix = sound_path.suffix.lower()
            is_wav = suffix in [".wav", ".wave"]

            # Reorder for better success probability
            def order_cmds(cmds: list) -> list:
                if is_wav:
                    return cmds
                # mp3/other: prefer ffplay/afplay over paplay/aplay
                priority = ["ffplay", "afplay", "play", "paplay", "aplay", "powershell"]
                return [c for c in priority if c in cmds]

            commands = order_cmds(commands)

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
                        # System.Media.SoundPlayer only supports WAV; skip if not WAV
                        if not is_wav:
                            log.debug("Skipping PowerShell (only supports WAV), will try ffplay for MP3/other")
                            continue
                        # Use -ExecutionPolicy Bypass to avoid policy restrictions
                        args = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", f"(New-Object Media.SoundPlayer '{sound_path}').PlaySync()"]
                    else:
                        continue
                    
                    # Start process (avoid" flashing console on Windows)
                    popen_kwargs: Dict[str, Any] = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if platform.system().lower() == "windows":
                        try:
                            # CREATE_NO_WINDOW to prevent console window flashing
                            popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                            log.debug(f"Windows: Using CREATE_NO_WINDOW for {cmd}")
                        except Exception as e:
                            log.debug(f"Windows: Could not set CREATE_NO_WINDOW: {e}")
                    
                    log.info(f"Starting audio command: {' '.join(args)}")
                    self.process = subprocess.Popen(args, **popen_kwargs)
                    
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
        from PySide6.QtMultimedia import QMediaPlayer
        if state == QMediaPlayer.PlaybackState.StoppedState:
            self.is_playing_flag = False
            if not self.loop:
                self.playback_finished.emit()
    
    def _on_playing_changed(self, playing=None):
        """Handle QSoundEffect playing state changes"""
        is_playing = bool(playing) if playing is not None else bool(getattr(self.player, "isPlaying", lambda: False)())
        self.is_playing_flag = is_playing
        if not is_playing and not self.loop:
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
    
    def _log_playback_status(self):
        """Log current playback status for debugging"""
        if self.player and hasattr(self.player, 'playbackState'):
            from PySide6.QtMultimedia import QMediaPlayer
            state = self.player.playbackState()
            state_names = {
                QMediaPlayer.PlaybackState.StoppedState: "Stopped",
                QMediaPlayer.PlaybackState.PlayingState: "Playing", 
                QMediaPlayer.PlaybackState.PausedState: "Paused"
            }
            log.debug(f"QMediaPlayer state: {state_names.get(state, 'Unknown')}")
        if hasattr(self, 'current_backend'):
            log.debug(f"Current backend: {self.current_backend}")

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
