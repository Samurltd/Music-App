# Build Android APK for MusicSearch

## Requirements
- Linux environment (WSL2 Ubuntu or native Linux)
- Python 3
- Buildozer
- Android SDK/NDK
- Java JDK

## Setup
1. Open WSL/Ubuntu and go to the app folder:
   ```bash
   cd /mnt/c/Users/bensm/OneDrive/Desktop/Learning/music_search_app
   ```
2. Install Buildozer and dependencies:
   ```bash
   sudo apt update
   sudo apt install -y python3 python3-pip python3-venv git build-essential libssl-dev libffi-dev libsqlite3-dev libncurses5 libjpeg-dev libfreetype6-dev openjdk-11-jdk zip unzip
   python3 -m pip install --user buildozer
   export PATH=$PATH:~/.local/bin
   ```
3. Initialize Buildozer if needed:
   ```bash
   buildozer init
   ```
   This is optional since `buildozer.spec` is already provided.

## Build APK
1. Run the debug build:
   ```bash
   buildozer android debug
   ```
2. After the build completes, the APK is in:
   ```bash
   bin/musicsearch-0.1-debug.apk
   ```

## Install on device
1. Enable USB debugging on your Android phone.
2. Connect the phone by USB.
3. Install the APK:
   ```bash
   adb install -r bin/musicsearch-0.1-debug.apk
   ```
4. Optionally run directly:
   ```bash
   buildozer android debug deploy run
   ```

## Notes
- `yt-dlp` and `ffmpeg` may increase package size and build complexity.
- If the build fails, remove online download logic first and keep local playback only for a simpler APK.
- Building must happen on Linux/WSL; Windows native Buildozer is not supported.
