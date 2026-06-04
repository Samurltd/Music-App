"""
Mobile Music Search App Package.
Initializes core configuration, search utilities, and audio playback engines.
"""

import logging

# Configure package-level logging for easier debugging in Android logcat
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("music_search_app")

try:
    from .config import LOCAL_MUSIC_FOLDERS, SUPPORTED_EXTENSIONS, YTDLP_OPTIONS
    from .search import search_local, search_online
    from .player import player
    
    logger.info("Core music search app modules initialized successfully.")
except ImportError as e:
    logger.error(f"Failed to initialize package modules: {e}")
    raise

__all__ = [
    "LOCAL_MUSIC_FOLDERS",
    "SUPPORTED_EXTENSIONS",
    "YTDLP_OPTIONS",
    "search_local",
    "search_online",
    "player",
]