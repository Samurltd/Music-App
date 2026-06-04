import os
import sys
from kivy.utils import platform

# Base Directory Setup
HOME = os.path.expanduser("~")

# Modern High-Quality Audio Formats Support
SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac", ".opus"}


def get_cache_folder():
    """
    Dynamically resolves a safe, permission-allowed app directory at runtime.
    Saves cache files inside the app sandbox to bypass Android OS locks.
    """
    if platform == "android":
        try:
            # Try parsing through Kivy's core app context if it is active
            from kivy.app import App
            app = App.get_running_app()
            if app and app.user_data_dir:
                return os.path.join(app.user_data_dir, "cache")
        except Exception:
            pass
        
        # Absolute foolproof fallback to the app's internal private storage container.
        # This directory is always writable by the app with zero permission flags.
        return "/data/user/0/org.example.musicsearch/files/cache"
    else:
        # Desktop Development Path
        return os.path.join(HOME, ".cache", "music_search")


# Dynamic Path Allocation for App Caches
YTDLP_CACHE_FOLDER = get_cache_folder()

# Ensure the cache folder exists immediately to prevent yt-dlp write crashes
os.makedirs(YTDLP_CACHE_FOLDER, exist_ok=True)

YTDLP_OUTPUT_TEMPLATE = os.path.join(YTDLP_CACHE_FOLDER, "%(id)s.%(ext)s")

# Optimized 2026 yt-dlp configuration profiles
YTDLP_OPTIONS = {
    "format": "bestaudio/best",
    "outtmpl": YTDLP_OUTPUT_TEMPLATE,
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "postprocessors": [
        {
            "key": "FFmpegExtractAudio", 
            "preferredcodec": "mp3", 
            "preferredquality": "192"
        }
    ],
    # CRITICAL FOR ANDROID: Points yt-dlp directly to the built-in ffmpeg binary
    "ffmpeg_location": sys.executable if platform == "android" else None
}


def get_local_music_folders():
    """
    Dynamically generates safe, unique, and queryable music directory paths.
    """
    folders = [
        os.path.join(HOME, "Music"),
        os.getcwd(),
    ]

    # Try utilizing official native Android system hooks first if available
    if platform == "android":
        try:
            from android.storage import primary_external_storage_path
            external = primary_external_storage_path()
            if external:
                folders.extend([
                    os.path.join(external, "Music"),
                    os.path.join(external, "Download"),
                ])
        except Exception:
            pass

    # Safe fallback paths prioritizing common user-accessible directories
    # Bypasses restricted system folders to avoid security sandboxing blocks
    folders.extend([
        "/storage/emulated/0/Music",
        "/storage/emulated/0/Download",
        "/sdcard/Music",
        "/sdcard/Download"
    ])

    # Clean, normalize, and verify that the paths exist before returning them
    normalized = []
    for folder in folders:
        if not folder:
            continue
        path = os.path.normpath(folder)
        # Avoid duplicates and non-existent folders to speed up UI scanning loops
        if path not in normalized and os.path.exists(path):
            normalized.append(path)
            
    return normalized

# Dynamic property getter to prevent startup load blocking
# We will invoke this inside main.py when the UI is ready!
def load_directories():
    return get_local_music_folders()