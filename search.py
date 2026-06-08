import os
import random
import re
import requests
import json
import time
import sys
from yt_dlp import YoutubeDL
from jnius import autoclass, PythonJavaClass, java_method

import config  # Importing config directly to reference dynamic attributes

# =====================================================================
# API Key Configuration
# =====================================================================
# Replace this string with your actual 32-character Last.fm API developer key.
# Get a free key immediately from: https://www.lastfm.com/api/account/create
LASTFM_API_KEY = "your_actual_32_character_lastfm_api_key_here"

# Core Android Native Dependencies via Pyjnius
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
        if media_session is None:
            service_instance = PythonService.mService
            # Instantiate session with a unique hardware tag identification string
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
            
        # Build strict media container blocks containing Track metadata descriptions
        MetadataBuilder = autoclass('android.media.MediaMetadata$Builder')
        metadata_builder = MetadataBuilder()
        metadata_builder.putString(MediaMetadata.METADATA_KEY_TITLE, str(title_text))
        metadata_builder.putString(MediaMetadata.METADATA_KEY_ARTIST, "MusicSearch Player")
        
        media_session.setMetadata(metadata_builder.build())
        
        # Define current playback state dynamics (Speed, Play/Pause configurations)
        StateBuilder = autoclass('android.media.session.PlaybackState$Builder')
        state_builder = StateBuilder()
        
        current_state = PlaybackState.STATE_PLAYING if _IS_PLAYING else PlaybackState.STATE_PAUSED
        # Map required action flags to notify subsystem that play control commands are active
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
        service_instance = PythonService.mService
        channel_id = "music_search_service_channel"
        
        # Ensure MediaSession state reflects current track values
        update_media_session_metadata(title_text)
        
        # Build a persistent Notification Channel (Required for Android 8.0+)
        channel = NotificationChannel(
            channel_id, 
            "Music Playback Service", 
            NotificationManager.IMPORTANCE_LOW
        )
        notification_manager = service_instance.getSystemService(Context.NOTIFICATION_SERVICE)
        notification_manager.createNotificationChannel(channel)
        
        # Configure the interface builder container properties
        NotificationBuilder = autoclass('android.app.Notification$Builder')
        builder = NotificationBuilder(service_instance, channel_id)
        builder.setContentTitle(str(title_text))
        builder.setContentText("Playing Local Stream Source" if "http" not in str(title_text) else "Streaming Online Source")
        
        # Pull the default system package asset icon wrapper mapping reference
        app_icon = service_instance.getApplicationInfo().icon
        builder.setSmallIcon(app_icon)
        
        # CRITICAL HANDSHAKE: Style notification explicitly as MediaStyle bound to our Session Token
        MediaStyle = autoclass('android.app.Notification$MediaStyle')
        media_style = MediaStyle()
        media_style.setMediaSession(media_session.getSessionToken())
        builder.setStyle(media_style)
        
        # Make the notification responsive in real-time across lockscreens
        builder.setVisibility(Notification.VISIBILITY_PUBLIC)
        
        built_notification = builder.build()
        
        # Elevate to foreground process mode using ID 101
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
                # PROTECT: Prevent OS-level restricted roots from crashing file system evaluations
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
                # PROTECT: Clean directory targets to prevent os.walk tracking descending into restricted areas
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
        return None
    track = random.choice(tracks)
    return {"title": track["title"], "path": track["path"], "source": "local"}


def fetch_artist_image(artist_name, song_title):
    """Fetches album visual art configurations using a valid API key."""
    if not LASTFM_API_KEY or LASTFM_API_KEY in ["your_actual_32_character_lastfm_api_key_here", "0", "None"]:
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
    if not query:
        return []
    _ensure_cache_directory()
    search_query = f"ytsearch1:{query}"
    
    options = dict(config.YTDLP_OPTIONS)
    options.update({
        "format": "bestaudio/best",    # CRITICAL: Force resolution of raw audio formats
        "extract_flat": False,         # CRITICAL: Disable flat extraction so true stream metadata maps
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
    if not query:
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
# Native Android Media Control and IPC Synchronization Additions
# =====================================================================

def init_media_player():
    """Instantiates and binds standard configurations to Android MediaPlayer."""
    global media_player
    if media_player is None:
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
        media_player.reset()
        
        # Safe binding to local disk cache files or live HTTP endpoints
        media_player.setDataSource(file_path)
        
        # FIX: Force ALL files to execute via prepareAsync() instead of blocking prepare(). 
        # This satisfies the internal hardware decoder timing loops and wakes up audio tracks cleanly.
        _listener_keep_alive = PreparedListener(_on_media_prepared_callback)
        media_player.setOnPreparedListener(_listener_keep_alive)
        
        # Initiate non-blocking background hardware asset compilation
        media_player.prepareAsync()
        print(f"Media engine buffering target initialized asynchronously: {file_path}")
            
    except Exception as e:
        print(f"Background stream engine error during data-source handoff: {e}")
        _IS_PLAYING = False


def broadcast_ui_update(track_title, position_ms, duration_ms):
    """Constructs and dispatches intent payloads to foreground main.py listeners."""
    try:
        service_context = PythonService.mService
        if service_context is None:
            return
            
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
                # Redraw notification state to reflect playback change (Play vs Pause icon style)
                start_foreground_notification(_CURRENT_TRACK_TITLE)
                    
        elif command_type == "stop":
            if media_player:
                media_player.stop()
                _IS_PLAYING = False
            start_foreground_notification("Engine Stopped")
                
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
    # CRITICAL: Capture environment parameters passed on application setup loop cleanly
    argument_env = sys.argv[1] if len(sys.argv) > 1 else ""
    
    init_media_player()
    init_media_session()
    start_foreground_notification("Engine Standing By...")
    
    if argument_env:
        try:
            handle_incoming_payload(argument_env)
        except Exception:
            pass
    
    # FIX: Instantiate and bind live real-time dynamic Android Intent Broadcast Channels
    try:
        IntentFilter = autoclass('android.content.IntentFilter')
        service_context = PythonService.mService
        
        _receiver_keep_alive = ServiceCommandReceiver()
        filter_channel = IntentFilter('org.example.musicsearch.SERVICE_COMMAND')
        
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

        # SAFE TRACKING: Guard against IllegalStateException during async buffering
        try:
            if media_player and _IS_PLAYING:
                # Verify if the hardware decoder has finished preparing and is rendering frames
                if media_player.isPlaying():
                    current_pos = media_player.getCurrentPosition()
                    total_dur = media_player.getDuration()
                    broadcast_ui_update(_CURRENT_TRACK_TITLE, current_pos, total_dur)
                else:
                    # If _IS_PLAYING is marked True but the player is still rendering buffer steps,
                    # return safe placeholder metrics to prevent native crashes.
                    broadcast_ui_update(_CURRENT_TRACK_TITLE, 0, 100)
            else:
                broadcast_ui_update(_CURRENT_TRACK_TITLE, 0, 0)
        except Exception as e:
            print(f"Metrics collection safely bypassed during state transition: {e}")
            
        time.sleep(0.4)