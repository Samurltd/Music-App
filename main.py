import json
import os
import threading

from kivy.app import App
from kivy.clock import mainthread, Clock
from kivy.lang import Builder
from kivy.factory import Factory
from kivy.properties import ListProperty, NumericProperty, StringProperty
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.button import Button
from kivy.utils import platform

import player
import search

# 1. Force Kivy to target your modern layout file exclusively
Builder.load_file(os.path.join(os.path.dirname(__file__), "app_modern.kv"))

# Inject the standard os module directly into the Kivy KV context parser
Factory.register('os', module=os)

# Android Native Intent Listener Initialization
if platform == "android":
    from android.broadcast import BroadcastReceiver


class SelectableResultButton(Button):
    """Button for interactive list selections."""
    result_index = NumericProperty(0)


# =========================================================================
# INTERFACE 1: THE MUSIC PLAYER SCREEN (Audio Deck Controls)
# =========================================================================
class PlayerScreen(Screen):
    current_track_title = StringProperty("No track playing")
    status_text = StringProperty("Ready")
    progress_value = NumericProperty(0)
    progress_max = NumericProperty(100)
    progress_text = StringProperty("0:00 / 0:00")
    background_image = StringProperty("")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.progress_update_event = None
        self._is_seeking = False  # Flag preventing track updates while manually scrubbing

    def pause_audio(self):
        if platform == "android":
            App.get_running_app().start_android_audio_service({"type": "pause"})
        else:
            player.player.pause()
            if player.player.is_playing():
                self.status_text = "Playback playing."
            else:
                self.status_text = "Playback paused."

    def stop_audio(self):
        if platform == "android":
            App.get_running_app().start_android_audio_service({"type": "stop"})
        else:
            player.player.stop()
            self._stop_progress_update()
            self.progress_value = 0
            self.progress_text = "0:00 / 0:00"
            self.status_text = "Playback stopped."

    def select_next_result(self):
        if platform == "android":
            App.get_running_app().start_android_audio_service({"type": "next"})
        else:
            search_screen = self.manager.get_screen('search_screen')
            if not search_screen.results:
                return
            search_screen.result_index = (search_screen.result_index + 1) % len(search_screen.results)
            search_screen.selected_index = search_screen.result_index
            search_screen.play_selected()

    def select_previous_result(self):
        if platform == "android":
            App.get_running_app().start_android_audio_service({"type": "previous"})
        else:
            search_screen = self.manager.get_screen('search_screen')
            if not search_screen.results:
                return
            search_screen.result_index = (search_screen.result_index - 1) % len(search_screen.results)
            search_screen.selected_index = search_screen.result_index
            search_screen.play_selected()

    def select_random_result(self):
        if platform == "android":
            App.get_running_app().start_android_audio_service({"type": "random"})
        else:
            search_screen = self.manager.get_screen('search_screen')
            if not search_screen.results:
                return
            import random
            search_screen.result_index = random.randint(0, len(search_screen.results) - 1)
            search_screen.selected_index = search_screen.result_index
            search_screen.play_selected()

    def _start_progress_update(self):
        """Starts tracking timeline increments at fluid 100ms updates (Non-Android Fallback)."""
        if self.progress_update_event:
            self.progress_update_event.cancel()
        self.progress_update_event = Clock.schedule_interval(self._update_progress, 0.1)

    def _stop_progress_update(self):
        """Cancels background clock tracking securely."""
        if self.progress_update_event:
            self.progress_update_event.cancel()
            self.progress_update_event = None

    def _update_progress(self, dt):
        """Tracks active sound progress metrics without stalling the UI thread framework (Non-Android)."""
        if platform == "android":
            return False

        if self._is_seeking:
            return True

        position = player.player.get_position()
        length = player.player.get_length()

        if not player.player.is_playing():
            # Keep clock alive waiting for the track initialization/buffering to settle
            if length <= 0 or position == 0:
                return True
            
            # End of audio track reached, clean slate UI
            if position >= (length - 0.5):
                self.progress_value = 0
                self.progress_text = f"{self._format_time(0)} / {self._format_time(length)}"
                self._stop_progress_update()
                return False

        if length > 0:
            self.progress_value = int((position / length) * self.progress_max)
            self.progress_text = f"{self._format_time(position)} / {self._format_time(length)}"
        else:
            self.progress_value = 0
            self.progress_text = "0:00 / 0:00"
        return True

    def on_progress_slider_touch_down(self):
        """Intercepts track timer modification loops."""
        self._is_seeking = True

    def on_progress_slider_release(self, value):
        """Handles manual audio scrubbing seek actions cleanly using explicit numeric mapping values."""
        if platform == "android":
            if self.progress_max > 0:
                seek_pos_ms = int((value / 100) * (self.progress_max * 1000))
                App.get_running_app().start_android_audio_service({
                    "type": "seek",
                    "position": seek_pos_ms
                })
            self._is_seeking = False
            return

        length = player.player.get_length()
        if length > 0:
            seek_pos = (value / self.progress_max) * length
            player.player.seek(seek_pos)
            self.progress_value = int(value)
        self._is_seeking = False

    @staticmethod
    def _format_time(seconds):
        mins = int(seconds) // 60
        secs = int(seconds) % 60
        return f"{mins}:{secs:02d}"


# =========================================================================
# INTERFACE 2: THE MUSIC SEARCH & BROWSE SCREEN (Online & Local)
# =========================================================================
class SearchScreen(Screen):
    search_query = StringProperty("")
    status_text = StringProperty("Ready")
    rv_data = ListProperty([])
    selected_index = NumericProperty(-1)
    browse_path = StringProperty(os.path.expanduser("~"))
    selected_file = StringProperty("")
    file_filters = ListProperty(["*.mp3", "*.wav", "*.ogg", "*.m4a", "*.flac", "*.aac", "*.opus"])
    results = []
    result_index = NumericProperty(0)

    def on_search_button(self):
        """Dispatches local, online, and YouTube recommendation search operations safely."""
        query = self.search_query.strip()
        if not query:
            self.status_text = "Type a song name or artist before searching."
            return

        self.status_text = "Searching music libraries and recommendations..."
        threading.Thread(target=self._perform_search, args=(query,), daemon=True).start()

    def _perform_search(self, query):
        """Cross-checks local indexing and appends online + YouTube recommendation results."""
        combined = []
        
        # 1. Check Local Storage Folders
        try:
            available_folders = search.get_available_local_music_folders()
            if available_folders:
                local_results = search.search_local(query)
                if local_results:
                    combined.extend(local_results)
        except Exception:
            pass

        # 2. Query Standard Online Engine
        try:
            online_results = search.search_online(query)
            if online_results:
                combined.extend(online_results)
        except Exception:
            pass

        # 3. Query YouTube Recommendations Engine
        try:
            youtube_results = search.fetch_youtube_recommendations(query)
            if youtube_results:
                combined.extend(youtube_results)
        except Exception:
            pass

        if combined:
            self.update_results(combined)
            return

        # Fallback to random track if absolute failure occurs
        self.play_random_fallback_track()

    def play_random_fallback_track(self):
        """Bridges the gap for KV calls looking to spin up an automated asset fallback."""
        try:
            random_track = search.get_random_track()
            if random_track:
                self._play_random_track(random_track, f"Spinning up random fallback asset: {random_track['title']}")
                return
        except Exception:
            pass
        self.update_results_empty()

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
        self.status_text = f"Found {len(results)} tracks & recommendations. Tap to play."

    @mainthread
    def update_results_empty(self):
        self.results = []
        self.rv_data = []
        self.status_text = "No results were found locally, online, or on YouTube."

    def select_result(self, index):
        if index < 0 or index >= len(self.results):
            return
        self.selected_index = index
        self.result_index = index
        self.play_selected()

    def play_selected(self):
        """Loads and processes playback streams, managing background service handover on Android."""
        if self.selected_index < 0 or self.selected_index >= len(self.results):
            self.status_text = "Select a result first, or search again."
            return

        item = self.results[self.selected_index]
        track_path = item["path"]
        
        player_screen = self.manager.get_screen('player_screen')
        player_screen.current_track_title = item['title']
        self._fetch_and_set_artist_image(item['title'])

        if platform == "android":
            payload_data = {
                "type": "start",
                "track_path": track_path,
                "playlist": [res["path"] for res in self.results],
                "titles": [res["title"] for res in self.results],
                "index": self.selected_index,
            }
            App.get_running_app().start_android_audio_service(payload_data)
        else:
            player_screen.status_text = f"Now playing: {item['title']} ({item['source']})"
            def non_android_play_async():
                success = player.player.play(track_path)
                self._apply_desktop_playback_status(success)
                
            threading.Thread(target=non_android_play_async, daemon=True).start()

        # Auto-switch execution view seamlessly to the active player deck interface
        self.manager.current = 'player_screen'

    @mainthread
    def _apply_desktop_playback_status(self, success):
        player_screen = self.manager.get_screen('player_screen')
        if success:
            player_screen._start_progress_update()
        else:
            player_screen.status_text = "Unable to stream or open the selected audio track."

    @mainthread
    def _play_random_track(self, random_track, message):
        self.results = [random_track]
        self.rv_data = [{"text": f"{random_track['title']} ({random_track['source']})", "result_index": 0}]
        self.selected_index = 0
        self.result_index = 0
        self.play_selected()
        self.status_text = message

    def on_browse_internal_memory(self):
        internal_paths = ["/storage/emulated/0", "/sdcard", os.path.expanduser("~")]
        for path in internal_paths:
            if os.path.isdir(path):
                self.browse_path = path
                self.status_text = f"Browsing Storage: {path}"
                return

    def on_file_selected(self, selection):
        if selection:
            self.selected_file = selection[0]
            self.status_text = f"Selected: {os.path.basename(self.selected_file)}"
        else:
            self.selected_file = ""
            self.status_text = "No target file chosen."

    def play_selected_file(self):
        if not self.selected_file or not os.path.isfile(self.selected_file):
            self.status_text = "Select a file from your storage directory first."
            return

        filename = os.path.basename(self.selected_file)
        player_screen = self.manager.get_screen('player_screen')
        player_screen.current_track_title = filename

        if platform == "android":
            payload_data = {
                "type": "start",
                "track_path": self.selected_file,
                "playlist": [self.selected_file],
                "titles": [filename],
                "index": 0,
            }
            App.get_running_app().start_android_audio_service(payload_data)
        else:
            player_screen.status_text = f"Now playing local file: {filename}"
            if player.player.play(self.selected_file):
                player_screen._start_progress_update()
            else:
                player_screen.status_text = "The engine was unable to parse this file format."

        self.manager.current = 'player_screen'

    def _fetch_and_set_artist_image(self, title, artist=""):
        def fetch():
            try:
                image_url = search.fetch_artist_image(artist or title, title)
                if image_url:
                    self._update_background_image(image_url)
            except Exception:
                pass
        threading.Thread(target=fetch, daemon=True).start()

    @mainthread
    def _update_background_image(self, image_url):
        self.manager.get_screen('player_screen').background_image = image_url


# =========================================================================
# INTERFACE 3: THE DEVELOPER SCREEN (Biography & Credentials)
# =========================================================================
class DeveloperScreen(Screen):
    developer_name = StringProperty("Designed by S. Ben")
    developer_role = StringProperty("Data, Mobile Solutions Engineer & Automation Architect")
    developer_bio = StringProperty(
        "Crafting clean cross-platform architectures and responsive mobile environments. "
        "Tap below to review the baseline codebase, tracking mechanics, and full project deployment pipeline."
    )
    github_url = StringProperty("https://github.com/Samurltd")

    def open_github(self):
        """Safely dispatches a platform-aware system browser intent call."""
        import webbrowser
        webbrowser.open(self.github_url)


# =========================================================================
# THE ROOT APPLICATION APP CONTAINER
# =========================================================================
class MusicSearchApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ui_receiver = None

    def build(self):
        safe_dir = self.get_safe_cache_directory()
        os.makedirs(safe_dir, exist_ok=True)
        
        # Instantiate ScreenManager and orchestrate the multi-screen system
        sm = ScreenManager()
        sm.add_widget(PlayerScreen(name='player_screen'))
        sm.add_widget(SearchScreen(name='search_screen'))
        sm.add_widget(DeveloperScreen(name='developer_screen'))
        return sm

    def get_safe_cache_directory(self):
        if platform == "android":
            return os.path.join(self.user_data_dir, "music_cache")
        return os.path.join(os.path.dirname(__file__), "music_cache")

    def start_android_audio_service(self, payload_dict):
        try:
            from jnius import autoclass
            service = autoclass('org.example.musicsearch.ServiceAudioservice')
            activity = autoclass('org.kivy.android.PythonActivity').mActivity
            service.start(activity, json.dumps(payload_dict))
        except Exception as e:
            print(f"Background Audio Service handoff error: {e}")

    def _process_broadcast_intent(self, context, intent):
        """Unpacks the background stream data and safely sends it to the handler."""
        try:
            is_playing = intent.getBooleanExtra("is_playing", False)
            position = intent.getIntExtra("position", 0)
            duration = intent.getIntExtra("duration", 0)
            title = intent.getStringExtra("title") or "Unknown track"
            
            self.handle_background_ui_update(is_playing, position, duration, title)
        except Exception as e:
            print(f"Error reading background intent data: {e}")

    @mainthread
    def handle_background_ui_update(self, is_playing, position, duration, title):
        """Routes background Android service metrics straight onto the main PlayerScreen."""
        player_screen = self.root.get_screen('player_screen')
        
        # Do not overwrite layout fields if the user is currently dragging the slider thumb
        if player_screen._is_seeking:
            return

        # Variables arrive processed down to clean raw seconds from service context update loops
        player_screen.current_track_title = title
        player_screen.progress_max = duration if duration > 0 else 100
        player_screen.progress_value = position
        player_screen.progress_text = f"{player_screen._format_time(position)} / {player_screen._format_time(duration)}"
        player_screen.status_text = f"Now playing: {title}" if is_playing else "Playback paused"

    def on_start(self):
        if platform == "android":
            try:
                from android.permissions import request_permissions, Permission
                
                # ADUSTED: API 34 strict permissions request sequence
                permissions_to_request = [
                    "android.permission.READ_MEDIA_AUDIO",
                    "android.permission.POST_NOTIFICATIONS",
                    "android.permission.FOREGROUND_SERVICE"
                ]

                def permission_callback(permissions, grants):
                    if all(grants):
                        print("All critical audio permissions granted by user.")
                        self._initialize_broadcast_receiver()
                    else:
                        print("Permissions denied. Background audio operations limited.")
                        # Fallback attempt to attach listener anyway
                        self._initialize_broadcast_receiver()

                request_permissions(permissions_to_request, permission_callback)
                
            except Exception as e:
                print(f"Failed during runtime permission sequencing layout: {e}")
                # Fallback implementation if permission engine isn't available
                self._initialize_broadcast_receiver()

    def _initialize_broadcast_receiver(self):
        """Attaches and runs the native receiver listener safely."""
        try:
            if platform == "android" and not self.ui_receiver:
                self.ui_receiver = BroadcastReceiver(
                    self._process_broadcast_intent, 
                    actions=['org.example.musicsearch.UI_UPDATE']
                )
                self.ui_receiver.start()
                print("UI Update Broadcast listener attached successfully via native wrapper.")
        except Exception as e:
            print(f"Error binding native broadcast architecture: {e}")

    def on_pause(self):
        return True

    def on_resume(self):
        pass


if __name__ == "__main__":
    MusicSearchApp().run()