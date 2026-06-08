[app]

# (string) Title of your application
title = MusicSearch

# (string) Package name
package.name = musicsearch

# (string) Package domain (needed for android packaging)
package.domain = org.example

# (string) Source code directory
source.dir = .

# Added common audio extensions so local assets are successfully packaged
source.include_exts = py, kv, ttf, png, jpg, mp3, wav, ogg, m4a

# (list) List of directories to exclude
source.exclude_dirs = __pycache__, build_env, .buildozer, bin, .git

# (string) Application version
version = 0.1

# Consolidated requirements: added android, pyjnius, and kept ffmpeg/pillow/certifi
requirements = python3, kivy, yt-dlp, ffmpeg, requests, certifi, pillow, pyjnius, android

# (str) Supported orientations
orientation = portrait

# (int) Fullscreen mode (0 for False, 1 for True)
fullscreen = 0

# Presplash and Icon images paths (leave blank if default or custom not placed yet)
presplash.filename =
icon.filename =

# =============================================================================
# Android specific settings
# =============================================================================

# (int) Target Android API
android.api = 34

# (int) Minimum API required
android.minapi = 21

# (int) Android NDK API to use
android.ndk_api = 21

# (list) The Android architectures to build for
android.archs = armeabi-v7a, arm64-v8a

# ADJUSTED: Mandatory media permissions for Android 13/14 (API 33/34)
android.permissions = INTERNET, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, READ_MEDIA_AUDIO, FOREGROUND_SERVICE, FOREGROUND_SERVICE_MEDIA_PLAYBACK, POST_NOTIFICATIONS

# ADJUSTED: Forces Android to respect legacy storage layouts if users run older device fallbacks
android.manifest_attributes = android:requestLegacyExternalStorage="true"

# (str) Android bootstrap to use (sdl2 / webview)
android.bootstrap = sdl2

# (list) List of extra libraries to include
android.extra_libs = ctypes

# Background Worker Service Declaration
# Keeps naming architecture mapped explicitly to match your main.py layout autoclass hook
android.services = Audioservice:service.py

# ADJUSTED: Kept perfectly on a single line so the Gradle wrapper parses the layout cleanly
android.gradle_dependencies = androidx.media:media:1.6.0, androidx.core:core:1.12.0


[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug and big outputs)
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1