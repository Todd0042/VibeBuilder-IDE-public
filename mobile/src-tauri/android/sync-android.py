#!/usr/bin/env python3
"""Sync tracked Android Kotlin sources and manifest entries into Tauri's generated Android project."""
from pathlib import Path
import shutil

ANDROID_DIR = Path(__file__).resolve().parent
GEN_MAIN = ANDROID_DIR.parent / "gen" / "android" / "app" / "src" / "main"
ICONS_DIR = ANDROID_DIR.parent / "icons" / "android"
RES_DIR = GEN_MAIN / "res"
PKG_DIR = GEN_MAIN / "java" / "dev" / "vibebuilder" / "ide" / "mobile"
MANIFEST = GEN_MAIN / "AndroidManifest.xml"
GRADLE = ANDROID_DIR.parent / "gen" / "android" / "app" / "build.gradle.kts"

if not GEN_MAIN.exists():
    raise SystemExit("gen/android not initialized yet; run: bin/vb-android init")

PKG_DIR.mkdir(parents=True, exist_ok=True)
for kt in ANDROID_DIR.glob("*.kt"):
    shutil.copy2(kt, PKG_DIR / kt.name)

if ICONS_DIR.exists():
    for sub in ICONS_DIR.iterdir():
        if sub.is_dir():
            dst_sub = RES_DIR / sub.name
            dst_sub.mkdir(parents=True, exist_ok=True)
            for f in sub.iterdir():
                if f.is_file():
                    shutil.copy2(f, dst_sub / f.name)
    # Remove Android template placeholder vector drawables if present
    for stale in [
        RES_DIR / "drawable" / "ic_launcher_background.xml",
        RES_DIR / "drawable-v24" / "ic_launcher_foreground.xml",
    ]:
        if stale.exists():
            stale.unlink()

if GRADLE.exists():
    gtext = GRADLE.read_text()
    gtext = gtext.replace("compileSdk = 37", "compileSdk = 36").replace("targetSdk = 37", "targetSdk = 36")
    GRADLE.write_text(gtext)

text = MANIFEST.read_text()

perms = [
    '<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />',
    '<uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />',
    '<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />',
]
for p in perms:
    if p not in text:
        text = text.replace(
            '<uses-permission android:name="android.permission.INTERNET" />',
            '<uses-permission android:name="android.permission.INTERNET" />\n    ' + p,
        )

if 'android:roundIcon=' not in text:
    text = text.replace(
        'android:icon="@mipmap/ic_launcher"',
        'android:icon="@mipmap/ic_launcher"\n        android:roundIcon="@mipmap/ic_launcher_round"',
    )

if 'android:windowSoftInputMode=' not in text:
    text = text.replace(
        'android:name=".MainActivity"',
        'android:name=".MainActivity"\n            android:windowSoftInputMode="adjustResize"',
    )

service = '<service android:name=".TunnelForegroundService" android:exported="false" android:foregroundServiceType="dataSync" />'
if 'TunnelForegroundService' not in text:
    text = text.replace('</application>', f'        {service}\n    </application>')

MANIFEST.write_text(text)
print(f"[vb-android] synced Kotlin plugin & manifest into {GEN_MAIN}")
