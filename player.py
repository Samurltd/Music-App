import os
import sys
import shutil
import subprocess
import threading
import time

# Detect platform
IS_ANDROID = 'ANDROID_ARGUMENT' in os.environ or 'PYTHON_SERVICE_ARGUMENT' in os.environ

if IS_ANDROID:
    try:
        from jnius import autoclass
        MediaPlayer = autoclass('android.media.MediaPlayer')
        AudioManager = autoclass('android.media.AudioManager')
    except Exception:
        MediaPlayer = None
else:
    MediaPlayer = None

try:
    from kivy.core.audio import SoundLoader
except Exception:
    SoundLoader = None


class AudioPlayer:
    def __init__(self):
        self.sound = None
        self.android_player = None
        self.current_track = None
        self.paused = False
        self.pause_position = 0.0
        self._native_process = None

    def _cleanup(self):
        """Safely stops, releases system audio streams, and resets state variables."""
        if self.android_player:
            try:
                self.android_player.stop()
                self.android_player.reset()
                self.android_player.release()
            except Exception:
                pass
            self.android_player = None

        if self.sound:
            try:
                self.sound.stop()
                self.sound.unload()
            except Exception:
                pass
            self.sound = None

        if self._native_process:
            try:
                self._native_process.terminate()
            except Exception:
                pass
            self._native_process = None

        self.current_track = None
        self.paused = False
        self.pause_position = 0.0

    def play(self, path):
        """Loads and initiates audio streams on Android and Desktop."""
        if not path:
            return False

        if not path.startswith(('http://', 'https://')) and not os.path.isfile(path):
            return False

        if path == self.current_track and self.paused:
            self.resume()
            return True

        self._cleanup()

        # 1. Android Native MediaPlayer Backend
        if IS_ANDROID and MediaPlayer is not None:
            try:
                mp = MediaPlayer()
                mp.setAudioStreamType(AudioManager.STREAM_MUSIC)
                mp.setDataSource(path)
                mp.prepare()
                mp.start()

                self.android_player = mp
                self.current_track = path
                self.paused = False
                return True
            except Exception as e:
                self._cleanup()

        # 2. Desktop Kivy SoundLoader Backend
        if SoundLoader is not None:
            try:
                sound = SoundLoader.load(path)
                if sound:
                    self.sound = sound
                    self.current_track = path
                    self.sound.play()
                    self.paused = False
                    return True
            except Exception:
                pass

        # 3. Desktop CLI Fallback (ffplay, vlc, aplay)
        fallback = self._launch_native_audio(path)
        if fallback:
            self.current_track = path
            self.paused = False
            return True

        return False

    def _launch_native_audio(self, path):
        """Desktop CLI player launcher."""
        if IS_ANDROID or path.startswith(('http://', 'https://')):
            return False

        player_candidates = ['ffplay', 'mpg123', 'aplay', 'vlc']
        exe = None
        for candidate in player_candidates:
            resolved = shutil.which(candidate)
            if resolved:
                exe = resolved
                break

        if not exe:
            return False

        try:
            if exe.endswith('vlc'):
                cmd = [exe, '--intf', 'dummy', path]
            elif exe.endswith('aplay'):
                cmd = [exe, '-q', path]
            elif exe.endswith('ffplay'):
                cmd = [exe, '-nodisp', '-autoexit', '-hide_banner', '-loglevel', 'error', path]
            else:
                cmd = [exe, path]

            self._native_process = subprocess.Popen(
                cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return True
        except Exception:
            return False

    def pause(self):
        """Pauses audio playback cleanly across backends."""
        if self.android_player and self.android_player.isPlaying():
            self.pause_position = self.android_player.getCurrentPosition() / 1000.0
            self.android_player.pause()
            self.paused = True
            return

        if self.sound and self.sound.state == "play":
            self.pause_position = self.sound.get_pos()
            self.sound.stop()
            self.paused = True
            return

        if self._native_process and self._native_process.poll() is None:
            self._native_process.terminate()
            self.paused = True

    def resume(self):
        """Resumes playback from the exact pause point."""
        if not self.paused or not self.current_track:
            return

        if self.android_player:
            self.android_player.start()
            self.paused = False
            return

        if self.sound:
            self.sound.play()
            try:
                self.sound.seek(self.pause_position)
            except Exception:
                pass
            self.paused = False
            return

        # Fallback for CLI or total restart
        self.play(self.current_track)

    def stop(self):
        """Terminates active audio playback."""
        self._cleanup()

    def is_playing(self):
        """Returns True if audio is actively playing."""
        if self.android_player:
            try:
                return self.android_player.isPlaying()
            except Exception:
                return False

        if self.sound:
            return self.sound.state == "play"

        if self._native_process:
            return self._native_process.poll() is None

        return False

    def is_paused(self):
        return self.paused

    def get_current_path(self):
        return self.current_track

    def get_position(self):
        """Returns current playback position in seconds."""
        if self.android_player:
            try:
                return self.android_player.getCurrentPosition() / 1000.0
            except Exception:
                return 0.0

        if self.sound:
            if self.paused:
                return self.pause_position
            return self.sound.get_pos()

        return 0.0

    def get_length(self):
        """Returns total duration in seconds."""
        if self.android_player:
            try:
                return self.android_player.getDuration() / 1000.0
            except Exception:
                return 0.0

        if self.sound and self.sound.length > 0:
            return self.sound.length

        return 0.0

    def get_track_title(self):
        if self.current_track:
            return os.path.basename(self.current_track)
        return "No track playing"

    def seek(self, position):
        """Seeks to target time in seconds."""
        if self.android_player:
            try:
                ms = int(position * 1000)
                self.android_player.seekTo(ms)
                return True
            except Exception:
                return False

        if self.sound:
            try:
                if self.paused:
                    self.pause_position = float(position)
                else:
                    self.sound.seek(float(position))
                return True
            except Exception:
                return False

        return False


# Singleton export instance
player = AudioPlayer()