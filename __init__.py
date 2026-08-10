"""
Mobile Music Search App Package.
Initializes core configuration, search utilities, and audio playback engines.
"""

import logging

__version__ = "1.0.0"

# Module-level logger using the module's namespace
logger = logging.getLogger(__name__)

try:
    from .config import LOCAL_MUSIC_FOLDERS, SUPPORTED_EXTENSIONS, YTDLP_OPTIONS
    from .search import search_local, search_online
    from .player import player

    logger.info("Core music search app modules initialized successfully.")
except ImportError as e:
    logger.critical(f"Failed to initialize package modules: {e}", exc_info=True)
    raise

__all__ = [
    "LOCAL_MUSIC_FOLDERS",
    "SUPPORTED_EXTENSIONS",
    "YTDLP_OPTIONS",
    "search_local",
    "search_online",
    "player",
    "__version__",
]