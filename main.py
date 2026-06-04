import os
import threading

from kivy.app import App
from kivy.clock import mainthread, Clock
from kivy.lang import Builder
from kivy.properties import ListProperty, NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.utils import platform

import player
import search


class SelectableResultButton(Button):
    """Button for interactive list selections."""
    result_index = NumericProperty(0)


class MusicSearchLayout(BoxLayout):
    search_query = StringProperty("")
    status_text = StringProperty("Ready")
    rv_data = ListProperty([])
    selected_index = NumericProperty(-1)
    browse_path = StringProperty(os.path.expanduser("~"))
    selected_file = StringProperty("")
    file_filters = ListProperty(["*.mp3", "*.wav", "*.ogg", "*.m4a", "*.flac", "*.aac", "*.opus"])
    current_track_title = StringProperty("No track playing")
    progress_value = NumericProperty(0)
    progress_max = NumericProperty(100)
    progress_text = StringProperty("0:00 / 0:00")
    background_image = StringProperty("")
    results = []
    progress_update_event = None
    result_index = NumericProperty(0)

    def on_search_button(self):
        """Dispatches local, online, and YouTube recommendation search operations safely."""
        query = self.search_query.strip()
        if not query:
            self.set_status("Type a song name or artist before searching.")
            return

        self.set_status("Searching music libraries and recommendations...")
        threading.Thread(target=self._perform_search, args=(query,), daemon=True).start()

    def _perform_search(self, query):
        """Cross-checks local indexing and appends online + YouTube recommendation results."""
        combined = []
        
        # 1. Check Local Storage Folders
        available_folders = search.get_available_local_music_folders()
        if available_folders:
            local_results = search.search_local(query)
            if local_results:
                combined.extend(local_results)

        # 2. Query Standard Online Engine
        try:
            online_results = search.search_online(query)
            if online_results:
                combined.extend(online_results)
        except Exception:
            pass

        # 3. Query YouTube Recommendations Engine
        try:
            self.set_status("Fetching YouTube recommendations...")
            youtube_results = search.fetch_youtube_recommendations(query)
            if youtube_results:
                combined.extend(youtube_results)
        except Exception:
            pass

        # Update UI if any combined results exist
        if combined:
            self.update_results(combined)
            self.set_status(f"Found {len(combined)} tracks & recommendations. Tap to play.")
            return

        # Fallback to random track if absolute failure occurs
        random_track = search.get_random_track()
        if random_track:
            self._play_random_track(
                random_track,
                f"No direct results found. Spinning up random asset: {random_track['title']}"
            )
            return

        self.update_results([])
        self.set_status("No results were found locally, online, or on YouTube.")
        self._set_background_image(self._get_default_image())

    @mainthread
    def update_results(self, results):
        """Populates UI list models smoothly back on the main loop thread."""
        self.results = results
        self.result_index = 0
        self.rv_data = [
            {"text": f"[{item['source'].upper()}] {item['title']}", "result_index": idx}
            for idx, item in enumerate(results)
        ]
        self.selected_index = -1

    @mainthread
    def set_status(self, text):
        self.status_text = text

    def select_result(self, index):
        if index < 0 or index >= len(self.results):
            return
        self.selected_index = index
        self.play_selected()

    def play_selected(self):
        """Loads and processes playback streams, managing background service handover on Android."""
        if self.selected_index < 0 or self.selected_index >= len(self.results):
            self.set_status("Select a result first, or search again.")
            return

        item = self.results[self.selected_index]
        track_path = item["path"]
        
        # Start the background audio engine container service on Android before triggering playback
        if platform == "android":
            self.start_android_audio_service(track_path)

        success = player.player.play(track_path)
        if success:
            self.current_track_title = item['title']
            self.set_status(f"Now playing: {item['title']} ({item['source']})")
            self._start_progress_update()
            self._fetch_and_set_artist_image(item['title'])
        else:
            self.set_status("Unable to stream or open the selected audio track.")

    def start_android_audio_service(self, track_url):
        """Starts the persistent background execution service on Android to bypass OS sleep limits."""
        try:
            from jnius import autoclass
            service = autoclass('org.example.musicsearch.ServiceAudioservice')
            activity = autoclass('org.kivy.android.PythonActivity').mActivity
            # Pass the track URL to the background context loop execution lifecycle
            service.start(activity, track_url)
        except Exception as e:
            print(f"Background Audio Service handoff error: {e}")

    def pause_audio(self):
        player.player.pause()
        self.set_status("Playback paused.")

    def stop_audio(self):
        player.player.stop()
        self._stop_progress_update()
        self.set_status("Playback stopped.")

    @mainthread
    def _play_random_track(self, random_track, message):
        self.results = [random_track]
        self.rv_data = [
            {"text": f"{random_track['title']} ({random_track['source']})", "result_index": 0}
        ]
        self.selected_index = 0
        self.play_selected()
        self.set_status(message)

    def play_random_song(self):
        random_track = search.get_random_track()
        if not random_track:
            self.set_status("No tracks available to play randomly.")
            return
        self._play_random_track(random_track, f"Playing random track: {random_track['title']}")

    def on_browse_music(self):
        available_folders = search.get_available_local_music_folders()
        if available_folders:
            self.browse_path = available_folders[0]
            self.set_status(f"Browsing: {self.browse_path}")
        else:
            self.browse_path = os.path.expanduser("~")
            self.set_status("No local folders mapped. Opening Home directory.")

    def on_file_selected(self, selection):
        if selection:
            self.selected_file = selection[0]
            self.set_status(f"Selected: {os.path.basename(self.selected_file)}")
        else:
            self.selected_file = ""
            self.set_status("No target file chosen.")

    def play_selected_file(self):
        if not self.selected_file or not os.path.isfile(self.selected_file):
            self.set_status("Select a file from your storage directory first.")
            return

        if platform == "android":
            self.start_android_audio_service(self.selected_file)

        success = player.player.play(self.selected_file)
        if success:
            self.current_track_title = os.path.basename(self.selected_file)
            self.set_status(f"Now playing local file: {os.path.basename(self.selected_file)}")
            self._start_progress_update()
        else:
            self.set_status("The engine was unable to parse this specific file format.")

    def _start_progress_update(self):
        """Starts tracking timeline increments at fluid 100ms updates."""
        if self.progress_update_event:
            self.progress_update_event.cancel()
        self.progress_update_event = Clock.schedule_interval(self._update_progress, 0.1)

    def _stop_progress_update(self):
        """Cancels background clock tracking securely."""
        if self.progress_update_event:
            self.progress_update_event.cancel()
            self.progress_update_event = None

    def _update_progress(self, dt):
        """Tracks active sound progress metrics without stalling the UI thread framework."""
        if not player.player.is_playing():
            position = player.player.get_position()
            length = player.player.get_length()
            if position == 0 or position >= length:
                self.progress_value = 0
                self.progress_text = f"{self._format_time(0)} / {self._format_time(length)}"
                self._stop_progress_update()
            return False

        position = player.player.get_position()
        length = player.player.get_length()

        if length > 0:
            self.progress_value = int((position / length) * self.progress_max)
            self.progress_text = f"{self._format_time(position)} / {self._format_time(length)}"
        else:
            self.progress_value = 0
            self.progress_text = "0:00 / 0:00"

        return True

    @staticmethod
    def _format_time(seconds):
        mins = int(seconds) // 60
        secs = int(seconds) % 60
        return f"{mins}:{secs:02d}"

    def on_progress_slider_release(self, value):
        """Handles manual audio scrubbing seek actions cleanly using explicit numeric mapping values."""
        length = player.player.get_length()
        if length > 0:
            seek_pos = (value / self.progress_max) * length
            player.player.seek(seek_pos)
            self.progress_value = int(value)

    def select_next_result(self):
        if not self.results:
            return
        self.result_index = (self.result_index + 1) % len(self.results)
        self.selected_index = self.result_index
        self._update_current_result_display()

    def select_previous_result(self):
        if not self.results:
            return
        self.result_index = (self.result_index - 1) % len(self.results)
        self.selected_index = self.result_index
        self._update_current_result_display()

    def _update_current_result_display(self):
        if 0 <= self.result_index < len(self.results):
            item = self.results[self.result_index]
            self.set_status(f"[{self.result_index + 1}/{len(self.results)}] {item['title']} [{item['source'].upper()}]")

    def play_current_result(self):
        if self.result_index < 0 or self.result_index >= len(self.results):
            self.select_result(0)
            return
        self.selected_index = self.result_index
        self.play_selected()

    def on_browse_internal_memory(self):
        internal_paths = ["/storage/emulated/0", "/sdcard", os.path.expanduser("~")]
        for path in internal_paths:
            if os.path.isdir(path):
                self.browse_path = path
                self.set_status(f"Browsing Storage: {path}")
                return

    def _set_background_image(self, image_url):
        if image_url:
            self.background_image = image_url
        else:
            self.background_image = self._get_default_image()

    def _get_default_image(self):
        """Finds our customized dancing lion image file location."""
        placeholder = os.path.join(os.path.dirname(__file__), "assets", "images", "dancing_lion.png")
        if os.path.exists(placeholder):
            return placeholder
        return ""

    def _fetch_and_set_artist_image(self, title, artist=""):
        """Asynchronously updates background artwork without freezing operations."""
        def fetch():
            try:
                image_url = search.fetch_artist_image(artist or title, title)
                if image_url:
                    self.background_image = image_url
            except Exception:
                pass
        threading.Thread(target=fetch, daemon=True).start()


class MusicSearchApp(App):
    def build(self):
        # Ensure targeted cache directories are created inside safe isolated storage path
        safe_dir = self.get_safe_cache_directory()
        os.makedirs(safe_dir, exist_ok=True)
        
        # Dynamically load modern layout file definition
        kv_path = os.path.join(os.path.dirname(__file__), "app_modern.kv")
        if not os.path.exists(kv_path):
            kv_path = os.path.join(os.path.dirname(__file__), "app.kv")
        Builder.load_file(kv_path)
        return MusicSearchLayout()

    def get_safe_cache_directory(self):
        """Returns the internal app data folder on Android to sidestep OS permission locks."""
        if platform == "android":
            return os.path.join(self.user_data_dir, "music_cache")
        return os.path.join(os.path.dirname(__file__), "music_cache")

    def on_start(self):
        """Asks for targeted modern Android multimedia file read permissions."""
        if platform == "android":
            try:
                from android.permissions import request_permissions, Permission
                permissions = []
                
                if hasattr(Permission, "READ_MEDIA_AUDIO"):
                    permissions.append(Permission.READ_MEDIA_AUDIO)
                if hasattr(Permission, "READ_EXTERNAL_STORAGE"):
                    permissions.append(Permission.READ_EXTERNAL_STORAGE)
                    
                if permissions:
                    request_permissions(permissions)
            except Exception:
                pass

    def on_pause(self):
        # Returning True explicitly forces Android to retain our state while minimized,
        # leaving our separate Service process to shoulder active audio rendering.
        return True

    def on_resume(self):
        pass


if __name__ == "__main__":
    MusicSearchApp().run()