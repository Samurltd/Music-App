import os
import sys
from kivy.core.audio import SoundLoader

class AudioPlayer:
    def __init__(self):
        self.sound = None
        self.current_track = None
        self.paused = False
        # Track timestamp when paused to circumvent Kivy's Android position-drop bug
        self.pause_position = 0.0 

    def _cleanup(self):
        """Safely stops, releases system audio streams, and resets state variables."""
        if self.sound:
            try:
                self.sound.stop()
                self.sound.unload()
            except Exception:
                pass
            self.sound = None
            self.current_track = None
            self.paused = False
            self.pause_position = 0.0

    def play(self, path):
        """
        Loads and initiates audio track streams.
        Supports absolute local files and network audio endpoints cleanly.
        """
        if not path:
            return False
            
        # Verify local file existences; bypass verification for web network URLs
        if not path.startswith(('http://', 'https://')) and not os.path.isfile(path):
            return False

        # If the same track is paused, treat this play command as a resume action
        if path == self.current_track and self.paused:
            self.resume()
            return True

        self._cleanup()

        try:
            sound = SoundLoader.load(path)
            if not sound:
                return False
                
            self.sound = sound
            self.current_track = path
            self.sound.play()
            self.paused = False
            self.pause_position = 0.0
            return True
        except Exception:
            return False

    def pause(self):
        """Saves current position safely before resting the audio pipeline."""
        if self.sound and self.sound.state == "play":
            # Store timestamp directly before execution drops it
            self.pause_position = self.sound.get_pos()
            self.sound.stop()
            self.paused = True

    def resume(self):
        """Restores audio pipeline stream directly to the exact point of pause."""
        if self.sound and self.paused:
            self.sound.play()
            # Force timeline to catch back up to the stored position marker
            try:
                self.sound.seek(self.pause_position)
            except Exception:
                pass
            self.paused = False

    def stop(self):
        """Terminates active audio channels cleanly."""
        if self.sound:
            self.stop_audio_pipeline()

    def stop_audio_pipeline(self):
        """Helper to break locks cleanly without race conditions inside main loops."""
        self._cleanup()

    def is_playing(self):
        """True if actively sending output signals to system speakers."""
        return self.sound is not None and self.sound.state == "play"

    def is_paused(self):
        return self.paused

    def get_current_path(self):
        return self.current_track

    def get_position(self):
        """Returns the current runtime position marker in absolute seconds."""
        if self.sound:
            if self.paused:
                return self.pause_position
            return self.sound.get_pos()
        return 0.0

    def get_length(self):
        """Returns total duration of file container in seconds."""
        if self.sound and self.sound.length > 0:
            return self.sound.length
        return 0.0

    def seek(self, position):
        """
        Scrubs timeline position securely.
        Handles runtime dynamic adjustments while playing or paused.
        """
        if not self.sound:
            return False
            
        try:
            length = self.get_length()
            if length > 0 and position > length:
                position = length
            if position < 0:
                position = 0.0

            if self.paused:
                # If paused, update our state tracking variable so resume hits the new marker
                self.pause_position = float(position)
                return True
            else:
                self.sound.seek(float(position))
                return True
        except Exception:
            return False

# Singleton application export instance
player = AudioPlayer()