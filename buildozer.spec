[app]
title = MusicSearch
package.name = musicsearch
package.domain = org.example
source.dir = .
# Added common audio extensions so local assets are successfully packaged
source.include_exts = py, kv, ttf, png, jpg, mp3, wav, ogg, m4a
source.exclude_dirs = __pycache__, build_env, .buildozer, bin, .git
version = 0.1

# Consolidated requirements: added android, pyjnius, and kept ffmpeg/pillow/certifi
requirements = python3, kivy, yt-dlp, ffmpeg, requests, certifi, pillow, pyjnius, android

orientation = portrait
fullscreen = 0
presplash.filename =
icon.filename =

# Android-specific settings
android.api = 33
android.minapi = 21
android.ndk_api = 21
android.archs = armeabi-v7a, arm64-v8a
android.permissions = INTERNET, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, READ_MEDIA_AUDIO
android.bootstrap = sdl2
android.extra_libs = ctypes

# Background Worker Service Declaration
services = AudioService:service.py

[buildozer]
log_level = 2
warn_on_root = 1

[app:android]
# If you need to include additional Java libraries, add them here.
# android.gradle_dependencies =