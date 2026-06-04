import os
import random
import re
import requests
from yt_dlp import YoutubeDL
import config  # Importing config directly to reference dynamic attributes

# Fast in-memory cache to prevent constant disk scraping
_LOCAL_TRACKS_CACHE = []


def get_available_local_music_folders():
    """Queries your dynamic config layer for valid, existing music paths."""
    folders = config.load_directories()
    return [folder for folder in folders if folder and os.path.isdir(folder)]


def clear_local_cache():
    """Forces the system to re-index storage directories on next query."""
    global _LOCAL_TRACKS_CACHE
    _LOCAL_TRACKS_CACHE = []


def _iter_local_tracks():
    """
    Iterates local storage targets cleanly. 
    Uses internal memory caching to keep searches instantaneous.
    """
    global _LOCAL_TRACKS_CACHE
    if _LOCAL_TRACKS_CACHE:
        for track in _LOCAL_TRACKS_CACHE:
            yield track
        return

    temp_cache = []
    available_folders = get_available_local_music_folders()
    
    for folder in available_folders:
        for root, _, files in os.walk(folder):
            for name in files:
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
                    
    _LOCAL_TRACKS_CACHE = temp_cache


def get_random_track():
    tracks = list(_iter_local_tracks())
    if not tracks:
        return None
    track = random.choice(tracks)
    return {"title": track["title"], "path": track["path"], "source": "local"}


def fetch_artist_image(artist_name, song_title):
    """Fetches album visual art configurations from public API end-points."""
    try:
        url = f"https://ws.audioscrobbler.com/2.0/?method=album.search&album={song_title}&format=json&limit=1&api_key=0"
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
    """
    Downloads targeted audio streams via optimized yt-dlp pipelines.
    Runs isolated on a background thread.
    """
    if not query:
        return []
    _ensure_cache_directory()
    search_query = f"ytsearch1:{query}"
    
    # Clone option dictionary profile and trim extractors to optimize download initialization speed
    options = dict(config.YTDLP_OPTIONS)
    options.update({
        "extract_flat": "in_playlist", 
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

        # Fallback resolution check for audio format adjustments
        if downloaded_path:
            fallback = os.path.splitext(downloaded_path)[0] + ".mp3"
            if os.path.exists(fallback):
                title = metadata.get("title") or query
                return [{"title": title, "path": fallback, "source": "online"}]
                
    except Exception:
        pass

    return []


def fetch_youtube_recommendations(query, max_results=5):
    """
    Queries YouTube search indices to populate recommended streams.
    Uses strict flat extraction properties to eliminate overhead.
    """
    if not query:
        return []

    # Configure a fast, metadata-only lookup using yt-dlp options base
    search_query = f"ytsearch{max_results}:{query} recommendation"
    ydl_opts = {
        "extract_flat": True,          # Essential: Stops download execution entirely
        "skip_download": True,         # Extra safety wrapper layer
        "quiet": True,                 # Prevent terminal spam clogging build logs
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
                        # Standardized streaming structure signature using its video url context
                        video_url = f"https://www.youtube.com/watch?v={entry.get('id')}" if entry.get("id") else entry.get("url")
                        
                        if video_url:
                            recommendations.append({
                                "title": title,
                                "path": video_url,
                                "source": "youtube"
                            })
    except Exception as e:
        print(f"YouTube Recommendation fetch silent exception handled: {e}")

    return recommendations