import os
import sys

try:
    from kivy.utils import platform
except Exception:
    # Desktop fallback when Kivy is absent or not yet initialized
    platform = "linux" if sys.platform.startswith("linux") else sys.platform

# Base Directory Setup
HOME = os.path.expanduser("~")

# Modern High-Quality Audio Formats Support
SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac", ".opus"}


def get_cache_folder():
    """
    Dynamically resolves a safe, permission-allowed app directory at runtime.
    Saves cache files inside the app sandbox to bypass Android OS storage locks.
    """
    if platform == "android":
        # 1. Attempt retrieval via running Kivy instance context
        try:
            from kivy.app import App
            app = App.get_running_app()
            if app and app.user_data_dir:
                cache_dir = os.path.join(app.user_data_dir, "cache")
                os.makedirs(cache_dir, exist_ok=True)
                return cache_dir
        except Exception:
            pass

        # 2. Native Pyjnius Android context resolution (works in service processes)
        try:
            from jnius import autoclass
            PythonService = autoclass('org.kivy.android.PythonService')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            
            context = PythonActivity.mActivity or PythonService.mService
            if context:
                files_dir = context.getFilesDir().getAbsolutePath()
                cache_dir = os.path.join(str(files_dir), "cache")
                os.makedirs(cache_dir, exist_ok=True)
                return cache_dir
        except Exception:
            pass

        # 3. Last-resort private path fallback
        fallback_dir = "/data/user/0/org.example.musicsearch/files/cache"
        os.makedirs(fallback_dir, exist_ok=True)
        return fallback_dir
    else:
        # Desktop Development Path
        cache_dir = os.path.join(HOME, ".cache", "music_search")
        os.makedirs(cache_dir, exist_ok=True)
        return cache_dir


# Dynamic Path Allocation for App Caches
YTDLP_CACHE_FOLDER = get_cache_folder()
YTDLP_OUTPUT_TEMPLATE = os.path.join(YTDLP_CACHE_FOLDER, "%(id)s.%(ext)s")

# Base yt-dlp Options
YTDLP_OPTIONS = {
    # Request native raw audio streams that Android's MediaPlayer can decode without FFmpeg
    "format": "bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio[ext=aac]/bestaudio/best",
    "outtmpl": YTDLP_OUTPUT_TEMPLATE,
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "nocheckcertificate": True,
}

# Only add FFmpeg postprocessing when running on Desktop environments where FFmpeg is installed
if platform != "android":
    YTDLP_OPTIONS["postprocessors"] = [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }
    ]


def get_local_music_folders():
    """
    Dynamically generates safe, unique, and queryable music directory paths.
    """
    folders = [
        os.path.join(HOME, "Music"),
        os.getcwd(),
    ]

    if platform == "android":
        # Native Android Storage Path Lookup
        try:
            from android.storage import primary_external_storage_path
            external = primary_external_storage_path()
            if external:
                folders.extend([
                    os.path.join(external, "Music"),
                    os.path.join(external, "Download"),
                    os.path.join(external, "Audiobooks"),
                    os.path.join(external, "Podcasts"),
                ])
        except Exception:
            pass

        # Safe fallback paths prioritizing common user-accessible directories
        folders.extend([
            "/storage/emulated/0/Music",
            "/storage/emulated/0/Download",
            "/sdcard/Music",
            "/sdcard/Download"
        ])

    normalized = []
    for folder in folders:
        if not folder:
            continue
        try:
            path = os.path.normpath(folder)
            if path not in normalized and os.path.isdir(path):
                # Verify read permissions before adding
                os.listdir(path)
                normalized.append(path)
        except (PermissionError, OSError):
            continue

    return normalized


def load_directories():
    """Dynamic property getter to prevent startup load blocking."""
    return get_local_music_folders()