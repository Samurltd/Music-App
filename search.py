import os
import random
import re
import json
import time
import sys

try:
    import requests
except Exception:
    requests = None

try:
    from yt_dlp import YoutubeDL
except Exception:
    YoutubeDL = None

try:
    from jnius import autoclass, PythonJavaClass, java_method
except Exception:
    autoclass = None
    PythonJavaClass = object
    java_method = lambda *args, **kwargs: (lambda fn: fn)

import config  # Importing config directly to reference dynamic attributes

# =====================================================================
# API Key Configuration
# =====================================================================
LASTFM_API_KEY = "your_actual_32_character_lastfm_api_key_here"

# Core Android Native Dependencies via Pyjnius
if autoclass is not None:
    try:
        PythonService = autoclass('org.kivy.android.PythonService')
        Intent = autoclass('android.content.Intent')
        MediaPlayer = autoclass('android.media.MediaPlayer')
        AudioManager = autoclass('android.media.AudioManager')

        # Native Android Notification Layer References for Foreground Audio
        Context = autoclass('android.content.Context')
        NotificationManager = autoclass('android.app.NotificationManager')
        NotificationChannel = autoclass('android.app.NotificationChannel')
        Notification = autoclass('android.app.Notification')

        # Native MediaSession and Metadata Engine Dependencies for Spotify-style UI
        MediaSession = autoclass('android.media.session.MediaSession')
        MediaMetadata = autoclass('android.media.MediaMetadata')
        PlaybackState = autoclass('android.media.session.PlaybackState')
        
        # Version information for Android 14 compatibility
        VERSION = autoclass('android.os.Build$VERSION')
    except Exception:
        PythonService = None
        Intent = None
        MediaPlayer = None
        AudioManager = None
        Context = None
        NotificationManager = None
        NotificationChannel = None
        Notification = None
        MediaSession = None
        MediaMetadata = None
        PlaybackState = None
        VERSION = None
else:
    PythonService = None
    Intent = None
    MediaPlayer = None
    AudioManager = None
    Context = None
    NotificationManager = None
    NotificationChannel = None
    Notification = None
    MediaSession = None
    MediaMetadata = None
    PlaybackState = None
    VERSION = None

# Fast in-memory cache to prevent constant disk scraping
_LOCAL_TRACKS_CACHE = []

# Global Playback Tracking Queues & Engine Instances
media_player = None
media_session = None
_CURRENT_PLAYLIST = []
_CURRENT_TITLES = []
_CURRENT_INDEX = -1
_IS_PLAYING = False
_CURRENT_TRACK_TITLE = "No track playing"

# Keep global references to prevent premature Java Garbage Collection cleanup
_listener_keep_alive = None
_receiver_keep_alive = None


# =====================================================================
# Jnius Interface Proxy Implementations
# =====================================================================

class PreparedListener(PythonJavaClass):
    """
    Explicit native structural interface mapping matching Android's 
    MediaPlayer.OnPreparedListener specifications exactly.
    """
    __javainterfaces__ = ['android/media/MediaPlayer$OnPreparedListener']
    
    def __init__(self, callback_func):
        super(PreparedListener, self).__init__()
        self.callback_func = callback_func
        
    @java_method('(Landroid/media/MediaPlayer;)V')
    def onPrepared(self, mp):
        if self.callback_func:
            self.callback_func(mp)


class ServiceCommandReceiver(PythonJavaClass):
    """
    Implements a live native Android BroadcastReceiver inside the service context
    to capture runtime audio state operations dispatched directly from the UI.
    """
    __javainterfaces__ = ['android/content/BroadcastReceiver']

    def __init__(self):
        super(ServiceCommandReceiver, self).__init__()

    @java_method('(Landroid/content/Context;Landroid/content/Intent;)V')
    def onReceive(self, context, intent):
        try:
            payload = intent.getStringExtra("payload")
            if payload:
                handle_incoming_payload(payload)
        except Exception as e:
            print(f"Error parsing broadcast intent payload pipeline: {e}")


# =====================================================================
# Media Session Management Engine
# =====================================================================

def init_media_session():
    """Initializes a formal Android MediaSession to unlock native system widgets."""
    global media_session
    try:
        if media_session is None and PythonService and PythonService.mService:
            service_instance = PythonService.mService
            media_session = MediaSession(service_instance, "MusicSearchEngineSession")
            media_session.setActive(True)
    except Exception as e:
        print(f"Failed to instantiate hardware MediaSession binding: {e}")


def update_media_session_metadata(title_text):
    """Feeds metadata directly into the OS subsystem to populate system audio widgets."""
    global media_session
    try:
        if media_session is None:
            init_media_session()
            
        if media_session is None:
            return

        MetadataBuilder = autoclass('android.media.MediaMetadata$Builder')
        metadata_builder = MetadataBuilder()
        metadata_builder.putString(MediaMetadata.METADATA_KEY_TITLE, str(title_text))
        metadata_builder.putString(MediaMetadata.METADATA_KEY_ARTIST, "MusicSearch Player")
        
        media_session.setMetadata(metadata_builder.build())
        
        StateBuilder = autoclass('android.media.session.PlaybackState$Builder')
        state_builder = StateBuilder()
        
        current_state = PlaybackState.STATE_PLAYING if _IS_PLAYING else PlaybackState.STATE_PAUSED
        actions = (PlaybackState.ACTION_PLAY | 
                   PlaybackState.ACTION_PAUSE | 
                   PlaybackState.ACTION_SKIP_TO_NEXT | 
                   PlaybackState.ACTION_SKIP_TO_PREVIOUS)
        state_builder.setState(current_state, PlaybackState.PLAYBACK_POSITION_UNKNOWN, 1.0)
        state_builder.setActions(actions)
        
        media_session.setPlaybackState(state_builder.build())
    except Exception as e:
        print(f"System controller synchronization bypassed: {e}")


def start_foreground_notification(title_text):
    """
    Configures and elevates the Python background process to an active Android Foreground Media Service.
    Applies MediaStyle constraints to integrate tightly with system volume panel trays.
    """
    try:
        if not PythonService or not PythonService.mService:
            return

        service_instance = PythonService.mService
        channel_id = "music_search_service_channel"
        
        update_media_session_metadata(title_text)
        
        channel = NotificationChannel(
            channel_id, 
            "Music Playback Service", 
            NotificationManager.IMPORTANCE_LOW
        )
        notification_manager = service_instance.getSystemService(Context.NOTIFICATION_SERVICE)
        notification_manager.createNotificationChannel(channel)
        
        NotificationBuilder = autoclass('android.app.Notification$Builder')
        builder = NotificationBuilder(service_instance, channel_id)
        builder.setContentTitle(str(title_text))
        builder.setContentText("Playing Local Stream Source" if "http" not in str(title_text) else "Streaming Online Source")
        
        app_icon = service_instance.getApplicationInfo().icon
        builder.setSmallIcon(app_icon)
        
        if media_session:
            MediaStyle = autoclass('android.app.Notification$MediaStyle')
            media_style = MediaStyle()
            media_style.setMediaSession(media_session.getSessionToken())
            builder.setStyle(media_style)
        
        builder.setVisibility(Notification.VISIBILITY_PUBLIC)
        built_notification = builder.build()
        
        # Check Android 14 (API 34+) requirement for foregroundType
        if VERSION and VERSION.SDK_INT >= 34:
            # FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK = 2
            service_instance.startForeground(101, built_notification, 2)
        else:
            service_instance.startForeground(101, built_notification)
    except Exception as e:
        print(f"Foreground elevation bypass applied: {e}")


def get_available_local_music_folders():
    """Queries your dynamic config layer for valid, accessible music paths."""
    try:
        folders = config.load_directories()
        valid_folders = []
        for folder in folders:
            if folder and os.path.isdir(folder):
                if folder.strip() in ["/", "/data", "/system", "/vendor"]:
                    continue
                try:
                    os.listdir(folder)
                    valid_folders.append(folder)
                except (PermissionError, Exception):
                    continue
        return valid_folders
    except Exception:
        return []


def clear_local_cache():
    """Forces the system to re-index storage directories on next query."""
    global _LOCAL_TRACKS_CACHE
    _LOCAL_TRACKS_CACHE = []


def _iter_local_tracks():
    """
    Iterates local storage targets cleanly with internal memory caching.
    Defends against Android permission restrictions on system roots.
    """
    global _LOCAL_TRACKS_CACHE
    if _LOCAL_TRACKS_CACHE:
        for track in _LOCAL_TRACKS_CACHE:
            yield track
        return

    temp_cache = []
    available_folders = get_available_local_music_folders()
    
    for folder in available_folders:
        try:
            for root, dirs, files in os.walk(folder, topdown=True):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['data', 'system', 'vendor']]
                for name in files:
                    try:
                        ext = os.path.splitext(name)[1].lower()
                        if ext in config.SUPPORTED_EXTENSIONS:
                            path = os.path.join(root, name)
                            title = os.path.splitext(name)[0]
                            track_data = {
                                "title": title,
                                "normalized": normalize_text(title),
                                "path": path,
                            }
                            temp_cache.append(track_data)
                            yield track_data
                    except Exception:
                        continue
        except (PermissionError, OSError):
            continue
                    
    _LOCAL_TRACKS_CACHE = temp_cache


def get_random_track():
    tracks = list(_iter_local_tracks())
    if not tracks:
        fallback = os.path.join(os.path.dirname(__file__), "assets", "sample_song.wav")
        if os.path.isfile(fallback):
            return {"title": "Sample Song", "path": fallback, "source": "local"}
        return None
    track = random.choice(tracks)
    return {"title": track["title"], "path": track["path"], "source": "local"}


def fetch_artist_image(artist_name, song_title):
    """Fetches album visual art configurations using a valid API key."""
    if not LASTFM_API_KEY or LASTFM_API_KEY in ["your_actual_32_character_lastfm_api_key_here", "0", "None"] or requests is None:
        return None

    try:
        url = f"https://ws.audioscrobbler.com/2.0/?method=album.search&album={song_title}&format=json&limit=1&api_key={LASTFM_API_KEY}"
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            data = response.json()
            if "results" in data and "albummatches" in data["results"]:
                albums = data["results"]["albummatches"].get("album", [])
                if albums:
                    image_data = albums[0].get("image", [])
                    if image_data:
                        for img in reversed(image_data):
                            if img.get("#text") and "placeholder" not in img["#text"].lower():
                                return img["#text"]
    except Exception:
        pass
    return None


def normalize_text(text):
    normalized = text.lower().strip()
    normalized = re.sub(r"[^\w\s]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def search_local(query, max_results=25):
    if not query:
        return []
    normalized_query = normalize_text(query)
    matches = []

    for track in _iter_local_tracks():
        if normalized_query in track["normalized"]:
            score = len(normalized_query) / max(len(track["normalized"]), 1)
            matches.append((score, track))
        else:
            parts = normalized_query.split()
            if all(part in track["normalized"] for part in parts):
                matches.append((0.5, track))

    matches.sort(key=lambda item: (-item[0], item[1]["title"]))
    return [
        {"title": track["title"], "path": track["path"], "source": "local"}
        for _, track in matches[:max_results]
    ]


def _ensure_cache_directory():
    if not os.path.isdir(config.YTDLP_CACHE_FOLDER):
        os.makedirs(config.YTDLP_CACHE_FOLDER, exist_ok=True)


def search_online(query):
    """Downloads targeted audio streams via optimized yt-dlp pipelines."""
    if not query or YoutubeDL is None:
        return []
    _ensure_cache_directory()
    search_query = f"ytsearch1:{query}"
    
    options = dict(config.YTDLP_OPTIONS)
    options.update({
        "format": "bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio/best",
        "extract_flat": False,
        "skip_download": False
    })

    downloaded_path = None
    metadata = None
    
    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(search_query, download=True)
            if not info:
                return []
                
            if "entries" in info and info["entries"]:
                metadata = info["entries"][0]
            else:
                metadata = info

            requested = metadata.get("requested_downloads")
            if requested and isinstance(requested, list):
                downloaded_path = requested[0].get("filepath")

            if not downloaded_path:
                try:
                    downloaded_path = ydl.prepare_filename(metadata)
                except Exception:
                    downloaded_path = None

        if downloaded_path and os.path.exists(downloaded_path):
            title = metadata.get("title") or query
            return [{"title": title, "path": downloaded_path, "source": "online"}]
    except Exception as e:
        print(f"Background stream extraction bottleneck: {e}")

    return []


def fetch_youtube_recommendations(query, max_results=5):
    """Queries YouTube search indices to populate recommended streams."""
    if not query or YoutubeDL is None:
        return []

    search_query = f"ytsearch{max_results}:{query} recommendation"
    ydl_opts = {
        "extract_flat": True,          
        "skip_download": True,         
        "quiet": True,                 
        "no_warnings": True,
    }

    recommendations = []
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=False)
            if info and "entries" in info:
                for entry in info["entries"]:
                    if entry:
                        title = entry.get("title") or "Recommended Track"
                        video_url = f"https://www.youtube.com/watch?v={entry.get('id')}" if entry.get('id') else entry.get('url')
                        if video_url:
                            recommendations.append({"title": title, "path": video_url, "source": "youtube"})
    except Exception:
        pass
    return recommendations


# =====================================================================
# Native Android Media Control and IPC Synchronization
# =====================================================================

def init_media_player():
    """Instantiates and binds standard configurations to Android MediaPlayer."""
    global media_player
    if media_player is None and MediaPlayer is not None:
        media_player = MediaPlayer()
        media_player.setAudioStreamType(AudioManager.STREAM_MUSIC)


def _on_media_prepared_callback(mp):
    """Callback function fired when async internet stream loading completes."""
    global _IS_PLAYING
    try:
        mp.start()
        _IS_PLAYING = True
        update_media_session_metadata(_CURRENT_TRACK_TITLE)
    except Exception as e:
        print(f"Error handling play transition: {e}")


def play_audio_source(file_path):
    """
    Resets the media player pipeline and spins up the chosen file target.
    Utilizes asynchronous loading uniformly to prevent thread race conditions.
    """
    global media_player, _IS_PLAYING, _listener_keep_alive
    try:
        init_media_player()
        if not media_player:
            return

        media_player.reset()
        media_player.setDataSource(file_path)
        
        _listener_keep_alive = PreparedListener(_on_media_prepared_callback)
        media_player.setOnPreparedListener(_listener_keep_alive)
        media_player.prepareAsync()
        print(f"Media engine buffering target initialized asynchronously: {file_path}")
            
    except Exception as e:
        print(f"Background stream engine error during data-source handoff: {e}")
        _IS_PLAYING = False


def broadcast_ui_update(track_title, position_ms, duration_ms):
    """Constructs and dispatches intent payloads to foreground main.py listeners."""
    try:
        if not PythonService or not PythonService.mService:
            return

        service_context = PythonService.mService
        intent = Intent('org.example.musicsearch.UI_UPDATE')
        pos_sec = int(position_ms // 1000) if position_ms else 0
        dur_sec = int(duration_ms // 1000) if duration_ms else 0
        
        intent.putExtra("is_playing", bool(_IS_PLAYING))
        intent.putExtra("position", int(pos_sec))
        intent.putExtra("duration", int(dur_sec))
        intent.putExtra("title", str(track_title))
        
        service_context.sendBroadcast(intent)
    except Exception:
        pass


def handle_incoming_payload(payload_string):
    """Parses control instructions received from the frontend layout context."""
    global _CURRENT_PLAYLIST, _CURRENT_TITLES, _CURRENT_INDEX, _IS_PLAYING, _CURRENT_TRACK_TITLE
    
    try:
        data = json.loads(payload_string)
        command_type = data.get("type")
        
        if command_type == "start":
            _CURRENT_PLAYLIST = data.get("playlist", [])
            _CURRENT_TITLES = data.get("titles", [])
            _CURRENT_INDEX = data.get("index", 0)
            _CURRENT_TRACK_TITLE = _CURRENT_TITLES[_CURRENT_INDEX] if _CURRENT_INDEX < len(_CURRENT_TITLES) else "Track"
            
            start_foreground_notification(_CURRENT_TRACK_TITLE)
            track_path = data.get("track_path")
            play_audio_source(track_path)
            
        elif command_type == "pause":
            if media_player:
                if media_player.isPlaying():
                    media_player.pause()
                    _IS_PLAYING = False
                else:
                    media_player.start()
                    _IS_PLAYING = True
                start_foreground_notification(_CURRENT_TRACK_TITLE)
                    
        elif command_type == "stop":
            if media_player:
                media_player.stop()
                _IS_PLAYING = False
            start_foreground_notification("Engine Stopped")

        elif command_type == "seek":
            target_ms = data.get("position", 0)
            if media_player:
                media_player.seekTo(int(target_ms))
                
        elif command_type == "next":
            if _CURRENT_PLAYLIST and len(_CURRENT_PLAYLIST) > 0:
                _CURRENT_INDEX = (_CURRENT_INDEX + 1) % len(_CURRENT_PLAYLIST)
                _CURRENT_TRACK_TITLE = _CURRENT_TITLES[_CURRENT_INDEX]
                start_foreground_notification(_CURRENT_TRACK_TITLE)
                play_audio_source(_CURRENT_PLAYLIST[_CURRENT_INDEX])
                
        elif command_type == "previous":
            if _CURRENT_PLAYLIST and len(_CURRENT_PLAYLIST) > 0:
                _CURRENT_INDEX = (_CURRENT_INDEX - 1) % len(_CURRENT_PLAYLIST)
                _CURRENT_TRACK_TITLE = _CURRENT_TITLES[_CURRENT_INDEX]
                start_foreground_notification(_CURRENT_TRACK_TITLE)
                play_audio_source(_CURRENT_PLAYLIST[_CURRENT_INDEX])

    except Exception as e:
        print(f"Error executing incoming service action target: {e}")


if __name__ == "__main__":
    argument_env = sys.argv[1] if len(sys.argv) > 1 else ""
    
    init_media_player()
    init_media_session()
    start_foreground_notification("Engine Standing By...")
    
    if argument_env:
        try:
            handle_incoming_payload(argument_env)
        except Exception:
            pass
    
    # Safe registerReceiver implementation supporting Android 14+ export flags
    try:
        if PythonService and PythonService.mService:
            IntentFilter = autoclass('android.content.IntentFilter')
            service_context = PythonService.mService
            
            _receiver_keep_alive = ServiceCommandReceiver()
            filter_channel = IntentFilter('org.example.musicsearch.SERVICE_COMMAND')
            
            if VERSION and VERSION.SDK_INT >= 33:
                # RECEIVER_NOT_EXPORTED = 4
                service_context.registerReceiver(_receiver_keep_alive, filter_channel, 4)
            else:
                service_context.registerReceiver(_receiver_keep_alive, filter_channel)
            print("Real-time audio command bridge registered successfully.")
    except Exception as e:
        print(f"Failed to bind live intent listener: {e}")
    
    while True:
        try:
            from android import get_arguments
            argument_env = get_arguments()
            if argument_env:
                handle_incoming_payload(argument_env)
        except ImportError:
            argument_env = os.environ.get('PYTHON_SERVICE_ARGUMENT', '')
            if argument_env:
                handle_incoming_payload(argument_env)
                os.environ['PYTHON_SERVICE_ARGUMENT'] = ''
        except Exception:
            pass

        try:
            if media_player and _IS_PLAYING:
                if media_player.isPlaying():
                    current_pos = media_player.getCurrentPosition()
                    total_dur = media_player.getDuration()
                    broadcast_ui_update(_CURRENT_TRACK_TITLE, current_pos, total_dur)
                else:
                    broadcast_ui_update(_CURRENT_TRACK_TITLE, 0, 100)
            else:
                broadcast_ui_update(_CURRENT_TRACK_TITLE, 0, 0)
        except Exception as e:
            print(f"Metrics collection safely bypassed during state transition: {e}")
            
        time.sleep(0.4)