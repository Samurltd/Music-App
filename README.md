# MusicSearch App

A modern, responsive multi-source audio player and streaming application built with Python and the Kivy framework. Developed specifically to bridge high-performance local music index management with external recommendation streams, the application operates robustly in mobile configurations by isolating heavyweight networking operations onto independent background threads.

## Features

- **Hybrid Library Aggregation:** Indexes local file structures instantly using memory caching while concurrently fetching metadata across active network streams.
- **Persistent Background Audio:** Utilizes an independent native Android Background Service via Python-for-Android (`pfa`) to ensure seamless audio playback even when the main user interface is minimized or suspended by the operating system.
- **YouTube Recommendations:** Integrates high-speed, flat-extraction pipelines using `yt-dlp` to query and serve music recommendations dynamically based on user search inputs.
- **Asynchronous Artwork Fetching:** Lazily pulls and renders contextual album and artist visual art assets via public REST endpoints without locking or stalling the main UI render loop.
- **Scrubbing Timeline Control:** Offers high-precision audio scrubbing and seeking controls calibrated around safe floating-point arithmetic.

## Tech Stack

- **Core Framework:** Python 3 & Kivy
- **Streaming Pipeline:** `yt-dlp`
- **Background Multiprocessing:** Python-for-Android Services & `pyjnius` (Java Native Interface Wrapper)
- **Asset Processing:** Pillow & Certifi
- **Media Engine:** FFmpeg & SDL2

---

## Directory Layout

```text
music_search_app/
├── main.py               # Application Entry Point & UI Logic
├── search.py             # Local In-Memory Indexer & YouTube Recommendation Pipeline
├── player.py             # Audio Driver Engine Controller
├── service.py            # Android Background Audio Isolation Worker
├── config.py             # Shared Configurations & Active Media Extensions
├── app_modern.kv         # Modern Styling Layout Instructions File
├── assets/
│   └── images/
│       └── dancing_lion.png  # Default Fallback Application Artwork
├── buildozer.spec        # Production Android Blueprint & Dependency Mappings
└── .gitignore            # Deployment Rules Filter File
