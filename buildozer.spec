[app]

# (string) Title of your application
title = MusicSearch

# (string) Package name
package.name = musicsearch

# (string) Package domain (needed for android packaging)
package.domain = org.example

# (string) Source code directory
source.dir = .

# Common source extensions to include
source.include_exts = py, kv, ttf, png, jpg, mp3, wav, ogg, m4a

# List of directories to exclude
source.exclude_dirs = __pycache__, build_env, .buildozer, bin, .git

# (string) Application version
version = 0.1

# Core Python packages & Android binders
requirements = python3, kivy, yt-dlp, ffpyplayer, requests, certifi, pillow, pyjnius, android

# (str) Supported orientations
orientation = portrait

# (int) Fullscreen mode (0 for False, 1 for True)
fullscreen = 0

# Presplash and Icon images paths
presplash.filename = %(source.dir)s/assets/images/dancing_lion.png
icon.filename = %(source.dir)s/assets/images/dancing_lion.png

# =============================================================================
# Android specific settings
# =============================================================================

# Auto-accept SDK licenses to prevent build failures on CI/CD runners
android.accept_sdk_license = True

# (int) Target Android API level
android.api = 34

# (int) Minimum API required
android.minapi = 24

# Explicitly pin NDK version across both Buildozer and P4A settings
android.ndk = 25c
p4a.ndk_version = 25c

# (list) The Android architectures to build for
android.archs = armeabi-v7a, arm64-v8a

# Complete permission declarations required for API 34 audio services & wake lock
android.permissions = INTERNET, READ_MEDIA_AUDIO, FOREGROUND_SERVICE, FOREGROUND_SERVICE_MEDIA_PLAYBACK, POST_NOTIFICATIONS, WAKE_LOCK

# Bootstrap configuration for Kivy/SDL2
p4a.bootstrap = sdl2

# Foreground Service declaration (myservice runs service.py)
android.services = myservice:service.py:foreground

# Fixed XML attribute syntax for API 34 foreground service compliance
android.manifest.service_attributes = myservice:android.foregroundServiceType="mediaPlayback"

# Single-line Gradle dependencies required for API 34 media controls & notifications
android.gradle_dependencies = androidx.media:media:1.6.0, androidx.core:core:1.12.0

# Request legacy external storage for backward compatibility on API 29-30
android.request_legacy_external_storage = True


[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug and big outputs)
log_level = 2

# (int) Display warning if buildozer is run as root
warn_on_root = 1