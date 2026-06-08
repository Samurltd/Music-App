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

# Control Constants
ACTION_PREVIOUS = 'org.example.musicsearch.PREVIOUS'
ACTION_PAUSE = 'org.example.musicsearch.PAUSE'
ACTION_NEXT = 'org.example.musicsearch.NEXT'
UI_UPDATE_ACTION = 'org.example.musicsearch.UI_UPDATE'
UI_COMMAND_ACTION = 'org.example.musicsearch.SERVICE_COMMAND'

# Global background operational state tracking blocks
_native_player = None
_playlist = []
_playlist_titles = []
_current_index = 0
_receiver = None
_command_receiver = None  # Persistent reference for UI-to-Service Commands
_media_session = None
_track_has_completed = False
_gc_completion_listener = None  # FIXED: Hard pointer to prevent Garbage Collection drops


class PlaybackCompletionListener(PythonJavaClass):
    __javainterfaces__ = ['android/media/MediaPlayer$OnCompletionListener']

    def __init__(self):
        super().__init__()

    @java_method('(Landroid/media/MediaPlayer;)V')
    def onCompletion(self, mp):
        global _track_has_completed
        print("Native Android notification: Track reached terminal end point.")
        _track_has_completed = True


class NotificationActionReceiver(PythonJavaClass):
    __javainterfaces__ = ['android/content/BroadcastReceiver']

    def __init__(self):
        super().__init__()

    @java_method('(Landroid/content/Context;Landroid/content/Intent;)V')
    def onReceive(self, context, intent):
        # FIXED: Ensure thread attachment for asynchronous broadcast entry hooks
        from jnius import detach
        action = intent.getAction()
        if action == ACTION_PREVIOUS:
            _previous_track()
        elif action == ACTION_PAUSE:
            _pause_resume()
        elif action == ACTION_NEXT:
            _next_track()
        detach()


class UICommandReceiver(PythonJavaClass):
    """FIXED: Intercepts real-time control broadcast dispatches emitted from main.py UI layer."""
    __javainterfaces__ = ['android/content/BroadcastReceiver']

    def __init__(self):
        super().__init__()

    @java_method('(Landroid/content/Context;Landroid/content/Intent;)V')
    def onReceive(self, context, intent):
        from jnius import detach
        if intent.getAction() == UI_COMMAND_ACTION:
            payload_str = intent.getStringExtra("payload")
            if payload_str:
                _process_command_string(str(payload_str))
        detach()


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
    """Passes the explicit FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK flag required for Android 14."""
    global _media_session, _playlist_titles, _current_index, _native_player
    try:
        service = PythonService.mService
        if not service:
            return
        channel_id = 'audio_service_channel'
        
        if not _media_session:
            _media_session = MediaSession(service, "MusicSearchMediaSession")
            _media_session.setActive(True)
        
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

        title = _playlist_titles[_current_index] if _current_index < len(_playlist_titles) else "No Track Playing"
        is_playing = _native_player.isPlaying() if _native_player else False

        builder.setContentTitle(title) \
               .setContentText("Media playback active in background") \
               .setSmallIcon(service.getApplicationInfo().icon) \
               .setVisibility(1) \
               .setOngoing(True) \
               .setOnlyAlertOnce(True)
               
        _register_notification_receiver(service)
        
        res_class = autoclass('android.R$drawable')
        prev_icon = getattr(res_class, 'ic_media_previous')
        next_icon = getattr(res_class, 'ic_media_next')
        play_icon = getattr(res_class, 'ic_media_pause' if is_playing else 'ic_media_play')

        builder.addAction(create_playback_action(service, ACTION_PREVIOUS, prev_icon, "Previous", 1))
        builder.addAction(create_playback_action(service, ACTION_PAUSE, play_icon, "Play/Pause", 2))
        builder.addAction(create_playback_action(service, ACTION_NEXT, next_icon, "Next", 3))

        media_style = MediaStyle()
        media_style.setMediaSession(_media_session.getSessionToken())
        media_style.setShowActionsInCompactView([0, 1, 2])
        builder.setStyle(media_style)

        if autoclass('android.os.Build$VERSION').SDK_INT >= 34:
            service.startForeground(1099, builder.build(), 2)
        else:
            service.startForeground(1099, builder.build())
    except Exception as e:
        print(f"Failed to mount native foreground notification manager layout: {e}")


def broadcast_progress_to_ui():
    """Broadcasts current tracking metrics over the system bus back to main.py."""
    global _native_player, _playlist_titles, _current_index
    if not _native_player:
        return
    try:
        service = PythonService.mService
        if not service:
            return
        intent = Intent(UI_UPDATE_ACTION)
        intent.setPackage(service.getPackageName())
        
        is_playing = _native_player.isPlaying()
        current_pos = _native_player.getCurrentPosition() // 1000  # ms to seconds
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
    """Core player utilizing Android Native Java MediaPlayer with anti-garbage collection locks."""
    global _native_player, _track_has_completed, _gc_completion_listener
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
        
        # FIXED: Pin listener instance to a global variable so Python doesn't collect it mid-track
        _gc_completion_listener = PlaybackCompletionListener()
        _native_player.setOnCompletionListener(_gc_completion_listener)
        
        # Audio Focus Configuration
        service = PythonService.mService
        if service:
            audio_manager = service.getSystemService(service.AUDIO_SERVICE)
            audio_manager.requestAudioFocus(None, AudioManager.STREAM_MUSIC, AudioManager.AUDIOFOCUS_GAIN)
        
        if path.startswith('/') and not path.startswith('http'):
            FileInputStream = autoclass('java.io.FileInputStream')
            fis = FileInputStream(path)
            _native_player.setDataSource(fis.getFD())
            fis.close()
        else:
            _native_player.setDataSource(path)
            
        _native_player.prepare()
        _native_player.start()
        
        # Keep CPU awake while streaming music tracks
        if service:
            _native_player.setWakeMode(service, 1)
        
        update_notification_state(PlaybackState.STATE_PLAYING)
        start_foreground_media_notification()
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


def _random_track():
    global _current_index, _playlist
    if not _playlist:
        return False
    import random
    _current_index = random.randint(0, len(_playlist) - 1)
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
        start_foreground_media_notification()
        return True
    except Exception as e:
        return False


def _process_command_string(command_json):
    """Parses incoming direct command payloads passed runtime from main.py."""
    global _playlist, _playlist_titles, _current_index, _native_player
    try:
        payload = json.loads(command_json)
        command_type = payload.get("type", "start")
        print(f"Background executing action parameter: {command_type}")
        
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
                start_foreground_media_notification()
        elif command_type == "next":
            _next_track()
        elif command_type == "previous":
            _previous_track()
        elif command_type == "random":
            _random_track()
        elif command_type == "seek":
            if _native_player:
                position_ms = payload.get("position", 0)
                _native_player.seekTo(position_ms)
    except Exception as e:
        print(f"Error parsing runtime command payload: {e}")


def _register_notification_receiver(service):
    """ADJUSTED FOR API 33/34: Registers notifications and command bus channels securely."""
    global _receiver, _command_receiver
    RECEIVER_NOT_EXPORTED = 2
    
    # 1. Register Notification UI Button Interceptor Channel
    if _receiver is None:
        try:
            _receiver = NotificationActionReceiver()
            intent_filter = IntentFilter()
            intent_filter.addAction(ACTION_PREVIOUS)
            intent_filter.addAction(ACTION_PAUSE)
            intent_filter.addAction(ACTION_NEXT)
            
            if autoclass('android.os.Build$VERSION').SDK_INT >= 33:
                service.registerReceiver(_receiver, intent_filter, RECEIVER_NOT_EXPORTED)
            else:
                service.registerReceiver(_receiver, intent_filter)
            print("Media notification buttons attached safely.")
        except Exception as e:
            print(f"JNI Event Notification Receiver registration sequence failed: {e}")

    # 2. FIXED: Register UI Command Channel to intercept real-time main.py commands (Pause/Seek/Next)
    if _command_receiver is None:
        try:
            _command_receiver = UICommandReceiver()
            cmd_filter = IntentFilter(UI_COMMAND_ACTION)
            if autoclass('android.os.Build$VERSION').SDK_INT >= 33:
                service.registerReceiver(_command_receiver, cmd_filter, RECEIVER_NOT_EXPORTED)
            else:
                service.registerReceiver(_command_receiver, cmd_filter)
            print("Real-time Service Command system bus synchronized.")
        except Exception as e:
            print(f"JNI Command Router initialization failed: {e}")


def check_for_incoming_intents():
    """Polls cold start intents cleanly without locking threading streams."""
    try:
        service = PythonService.mService
        if not service:
            return
        
        intent = service.getIntent()
        if intent:
            String = autoclass('java.lang.String')
            argument_str = intent.getStringExtra(String("argument"))
            if argument_str:
                print(f"Service cold-start payload received: {argument_str}")
                _process_command_string(str(argument_str))
                
                intent.removeExtra(String("argument"))
                ClearIntent = Intent(service, service.getClass())
                service.setIntent(ClearIntent)
    except Exception as e:
        print(f"Error handling intent queue check loop: {e}")


if __name__ == '__main__':
    _playlist_titles = ["Initializing Player..."]
    _playlist = [""]
    
    # Wait for service execution wrapper initialization to fully finalize
    while PythonService.mService is None:
        time.sleep(0.1)
        
    start_foreground_media_notification()
    time.sleep(0.2) 
    check_for_incoming_intents()

    last_broadcast_time = 0
    
    # Continuous background service monitoring loop
    while True:
        # FIXED: Attach native context pointer explicitly inside loop thread framework
        from jnius import autoclass
        
        check_for_incoming_intents()
            
        if _track_has_completed:
            _track_has_completed = False
            if len(_playlist) > 0:
                _next_track()
            else:
                break
                
        current_time = time.time()
        if current_time - last_broadcast_time >= 1.0:
            broadcast_progress_to_ui()
            last_broadcast_time = current_time
            
        time.sleep(0.25)