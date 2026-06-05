import json
import os
import time
from os import environ

# Force Kivy internals to skip Window creation inside this background process
environ['KIVY_NO_ARGS'] = '1'

from jnius import autoclass, PythonJavaClass, java_method

# Reference native Android Core, Notification, and MediaSession Classes via JNI
PythonService = autoclass('org.kivy.android.PythonService')
NotificationBuilder = autoclass('android.app.Notification$Builder')
NotificationManager = autoclass('android.app.NotificationManager')
Intent = autoclass('android.content.Intent')
PendingIntent = autoclass('android.app.PendingIntent')
IntentFilter = autoclass('android.content.IntentFilter')

# Media control specific native classes
MediaPlayer = autoclass('android.media.MediaPlayer')
AudioManager = autoclass('android.media.AudioManager')
MediaSession = autoclass('android.media.session.MediaSession')
MediaStyle = autoclass('android.app.Notification$MediaStyle')
PlaybackState = autoclass('android.media.session.PlaybackState')

ACTION_PREVIOUS = 'org.example.musicsearch.PREVIOUS'
ACTION_PAUSE = 'org.example.musicsearch.PAUSE'
ACTION_NEXT = 'org.example.musicsearch.NEXT'

# Broadcast constant for signaling data updates back to main UI
UI_UPDATE_ACTION = 'org.example.musicsearch.UI_UPDATE'

# Global background operational state tracking blocks
_native_player = None
_playlist = []
_playlist_titles = []
_current_index = 0
_receiver = None
_media_session = None
_track_has_completed = False


class PlaybackCompletionListener(PythonJavaClass):
    __javainterfaces__ = ['android/media/MediaPlayer$OnCompletionListener']

    def __init__(self):
        super().__init__()

    @java_method('(Landroid/media/MediaPlayer;)V')
    def onCompletion(self, mp):
        global _track_has_completed
        print("Native Android notification: Track reached terminal end point.")
        _track_has_completed = True


def create_playback_action(context, action_str, icon_id, title, request_code):
    """Helper to create actionable intent buttons for the notification bar."""
    intent = Intent(action_str)
    intent.setPackage(context.getPackageName())
    flags = PendingIntent.FLAG_UPDATE_CURRENT | getattr(PendingIntent, 'FLAG_IMMUTABLE', 67108864)
    pending_intent = PendingIntent.getBroadcast(context, request_code, intent, flags)
    
    NotificationActionBuilder = autoclass('android.app.Notification$Action$Builder')
    action_builder = NotificationActionBuilder(icon_id, title, pending_intent)
    return action_builder.build()


def update_notification_state(state):
    """Updates the native Android lockscreen/shade widget state UI dynamically."""
    global _media_session
    if not _media_session:
        return
    try:
        state_builder = PlaybackState.Builder()
        state_builder.setState(state, PlaybackState.PLAYBACK_POSITION_UNKNOWN, 1.0)
        _media_session.setPlaybackState(state_builder.build())
    except Exception as e:
        print(f"Failed to update OS playback state indicator: {e}")


def start_foreground_media_notification():
    """FIX: Binds service to a persistent foreground notification to bypass Android Doze limits."""
    global _media_session
    try:
        service = PythonService.mService
        channel_id = 'audio_service_channel'
        
        # Configure the native System MediaSession token
        _media_session = MediaSession(service, "MusicSearchMediaSession")
        _media_session.setActive(True)
        
        # Handle modern Android Oreo+ notification channels safely
        if autoclass('android.os.Build$VERSION').SDK_INT >= 26:
            NotificationChannel = autoclass('android.content.NotificationChannel')
            char_sequence = autoclass('java.lang.CharSequence')
            channel_name = char_sequence.cast(autoclass('java.lang.String')("Audio Background Engine"))
            importance = NotificationManager.IMPORTANCE_LOW
            channel = NotificationChannel(channel_id, channel_name, importance)
            manager = service.getSystemService(service.NOTIFICATION_SERVICE)
            manager.createNotificationChannel(channel)
            builder = NotificationBuilder(service, channel_id)
        else:
            builder = NotificationBuilder(service)

        # Build structural layout notifications panel components
        builder.setContentTitle("Music Search") \
               .setContentText("Media playback active in background") \
               .setSmallIcon(service.getApplicationInfo().icon)
               
        # Register interface notification broadcast hooks
        _register_notification_receiver(service)
        
        # Apply specialized system lockscreen media styling constraints
        media_style = MediaStyle()
        media_style.setMediaSession(_media_session.getSessionToken())
        builder.setStyle(media_style)

        # Pin context securely into operating system parameters
        service.startForeground(1099, builder.build())
        print("Foreground Media Notification subsystem established successfully.")
    except Exception as e:
        print(f"Failed to mount native foreground notification manager layout: {e}")


def broadcast_progress_to_ui():
    """Broadcasts current tracking metrics over the system bus back to main.py."""
    global _native_player, _playlist_titles, _current_index
    if not _native_player:
        return
    try:
        service = PythonService.mService
        intent = Intent(UI_UPDATE_ACTION)
        intent.setPackage(service.getPackageName())
        
        # Pull live metrics directly out of the Java engine safely
        is_playing = _native_player.isPlaying()
        current_pos = _native_player.getCurrentPosition() // 1000  # convert ms to seconds
        duration = _native_player.getDuration() // 1000
        
        title = _playlist_titles[_current_index] if _current_index < len(_playlist_titles) else "Unknown Track"
        
        intent.putExtra("is_playing", bool(is_playing))
        intent.putExtra("position", int(current_pos))
        intent.putExtra("duration", int(duration))
        intent.putExtra("title", str(title))
        
        service.sendBroadcast(intent)
    except Exception as e:
        pass


def _play_track(path):
    """Core fallback player utilizing Android Native Java MediaPlayer instead of SoundLoader."""
    global _native_player, _track_has_completed
    _track_has_completed = False

    if _native_player:
        try:
            _native_player.stop()
            _native_player.reset()
            _native_player.release()
        except Exception:
            pass
        _native_player = None

    if not path:
        return False

    try:
        print(f"Native MediaPlayer initializing engine path payload: {path}")
        _native_player = MediaPlayer()
        _native_player.setAudioStreamType(AudioManager.STREAM_MUSIC)
        
        completion_listener = PlaybackCompletionListener()
        _native_player.setOnCompletionListener(completion_listener)
        
        if path.startswith('/') and not path.startswith('http'):
            FileInputStream = autoclass('java.io.FileInputStream')
            fis = FileInputStream(path)
            _native_player.setDataSource(fis.getFD())
            fis.close()
        else:
            _native_player.setDataSource(path)
            
        _native_player.prepare()
        _native_player.start()
        
        update_notification_state(PlaybackState.STATE_PLAYING)
        return True
    except Exception as e:
        print(f"Native Java MediaPlayer playback initiation crashed: {e}")
        return False


def _play_current_index():
    global _current_index
    if not _playlist or _current_index < 0 or _current_index >= len(_playlist):
        return False
    return _play_track(_playlist[_current_index])


def _previous_track():
    global _current_index
    if not _playlist:
        return False
    _current_index = (_current_index - 1) % len(_playlist)
    return _play_current_index()


def _next_track():
    global _current_index
    if not _playlist:
        return False
    _current_index = (_current_index + 1) % len(_playlist)
    return _play_current_index()


def _pause_resume():
    global _native_player
    if not _native_player:
        return False
    try:
        if _native_player.isPlaying():
            _native_player.pause()
            update_notification_state(PlaybackState.STATE_PAUSED)
        else:
            _native_player.start()
            update_notification_state(PlaybackState.STATE_PLAYING)
        return True
    except Exception as e:
        return False


def _process_command_string(command_json):
    """Parses incoming direct command payloads passed runtime from main.py."""
    global _playlist, _playlist_titles, _current_index, _native_player
    try:
        payload = json.loads(command_json)
        command_type = payload.get("type", "start")
        
        if command_type == "start":
            _playlist = payload.get('playlist', []) or []
            _playlist_titles = payload.get('titles', []) or []
            _current_index = int(payload.get('index', 0) or 0)
            track_path = payload.get('track_path') or payload.get('audio_path')
            
            if _playlist and 0 <= _current_index < len(_playlist):
                _play_current_index()
            elif track_path:
                _play_track(track_path)
                
        elif command_type == "pause":
            _pause_resume()
        elif command_type == "stop":
            if _native_player:
                _native_player.stop()
                update_notification_state(PlaybackState.STATE_STOPPED)
        elif command_type == "next":
            _next_track()
        elif command_type == "previous":
            _previous_track()
    except Exception as e:
        print(f"Error parsing runtime command payload: {e}")


class NotificationActionReceiver(PythonJavaClass):
    __javainterfaces__ = ['android/content/BroadcastReceiver']

    def __init__(self):
        super().__init__()

    @java_method('(Landroid/content/Context;Landroid/content/Intent;)V')
    def onReceive(self, context, intent):
        action = intent.getAction()
        if action == ACTION_PREVIOUS:
            _previous_track()
        elif action == ACTION_PAUSE:
            _pause_resume()
        elif action == ACTION_NEXT:
            _next_track()


def _register_notification_receiver(service):
    global _receiver
    if _receiver is not None:
        return
    try:
        _receiver = NotificationActionReceiver()
        intent_filter = IntentFilter()
        intent_filter.addAction(ACTION_PREVIOUS)
        intent_filter.addAction(ACTION_PAUSE)
        intent_filter.addAction(ACTION_NEXT)
        service.registerReceiver(_receiver, intent_filter)
    except Exception as e:
        print(f"JNI Event Broadcast Receiver registration sequence failed: {e}")


if __name__ == '__main__':
    start_foreground_media_notification()
    
    # Process initial launch argument execution handoff payload
    initial_arg = environ.get('PYTHON_SERVICE_ARGUMENT', '')
    if initial_arg:
        _process_command_string(initial_arg)

    last_broadcast_time = 0
    
    # Continuous background loop
    while True:
        # Check for newly arrived operational intents dropped down at runtime from main.py
        fresh_arg = environ.get('PYTHON_SERVICE_ARGUMENT', '')
        if fresh_arg and fresh_arg != initial_arg:
            _process_command_string(fresh_arg)
            initial_arg = fresh_arg  # Reset state pointer token tracking
            environ['PYTHON_SERVICE_ARGUMENT'] = '' # Wipe argument slot clean for next command
            
        if _track_has_completed:
            _track_has_completed = False
            if len(_playlist) > 0:
                _next_track()
            else:
                break
                
        # Send live progress updates to UI every 1 second
        current_time = time.time()
        if current_time - last_broadcast_time >= 1.0:
            broadcast_progress_to_ui()
            last_broadcast_time = current_time
            
        time.sleep(0.2)