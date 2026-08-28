[app]

# (str) Title of your application
title = XAUUSD Signal Desk Pro

# (str) Package name
package.name = xauusd_desk

# (str) Package domain (needed for android/ios packaging)
package.domain = org.botpython

# (str) Source code where the main.py lives
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,html,css,js,json,svg,txt,md

# (list) List of inclusions using pattern matching
source.include_patterns = web/*,data/*

# (list) Source files to exclude (let empty to not exclude anything)
source.exclude_exts = spec,pyc,pyo,pyd,bak

# (list) List of directory to exclude
source.exclude_dirs = tests,bin,.venv,.git,.github,.agents,.system_generated

# (str) Application versioning
version = 1.0.0

# (list) Application requirements
# comma separated e.g. requirements = sqlite3,kivy
requirements = python3,kivy,requests,urllib3,pytz,jinja2,certifi,idna,charset-normalizer,pyjnius

# (str) Presplash of the application
presplash.filename = %(source.dir)s/web/presplash.png

# (str) Icon of the application
icon.filename = %(source.dir)s/web/icon.png

# (str) Supported orientation (one of landscape, sensorLandscape, portrait or all)
orientation = all

# (list) List of service to declare
#services = NAME:ENTRYPOINT_TO_PY,NAME2:ENTRYPOINT2_TO_PY

#
# Android specific
#

# (bool) Indicate if the application should be fullscreen
fullscreen = 1

# (string) Presplash background color (for new android presplash)
android.presplash_color = #181a20

# (list) Permissions
android.permissions = INTERNET,ACCESS_NETWORK_STATE,WAKE_LOCK,VIBRATE

# (int) Target Android API, should be as high as possible.
android.api = 33

# (int) Minimum API your APK will support.
android.minapi = 21

# (int) Android SDK version to use
android.sdk = 33

# (str) Android NDK version to use
android.ndk = 25b

# (int) Android NDK API to use
android.ndk_api = 21

# (bool) Automatically accept SDK license
android.accept_sdk_license = True

# (bool) Use --private data storage (True) or --dir public storage (False)
android.private_storage = True

# (list) The Android architectures to build for
android.archs = arm64-v8a

# (bool) enables Android auto backup feature (Android API >=23)
android.allow_backup = True

# (str) Entrypoint file
#android.entrypoint = main.py

# (list) Android app theme, default is ok for most cases
#android.theme = "@android:style/Theme.NoTitleBar"

# (list) Java classes to add to the compilation
#android.add_jars = foo.jar,bar.jar,etc.

# (list) Gradle dependencies
#android.gradle_dependencies =

# (list) add java files
#android.add_src =

# (bool) enable AndroidX support. Enable when you use Gradle dependencies.
android.enable_androidx = True

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug with command output)
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1

# (str) Path to build artifact storage, default is ./bin
bin_dir = ./bin
