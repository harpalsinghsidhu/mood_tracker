[app]
title = Mood Tracker
package.name = moodtracker
package.domain = org.mood
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.1

icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png
presplash.color = #14141C

requirements = python3,kivy,sqlite3,pyjnius,android
orientation = portrait
fullscreen = 0

services = reminder:service.py:foreground

android.permissions = POST_NOTIFICATIONS,FOREGROUND_SERVICE,WAKE_LOCK
android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True

p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
