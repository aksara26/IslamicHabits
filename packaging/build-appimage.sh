#!/usr/bin/env bash
# Bangun AppImage satu berkas. Membutuhkan meson, ninja, dan appimagetool.
# GTK4/libadwaita/PyGObject tetap diambil dari sistem host.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_ID="io.github.kurakura.IslamicHabits"
BUILD_DIR="$ROOT/builddir-appimage"
APPDIR="$BUILD_DIR/AppDir"
TOOL="${APPIMAGETOOL:-appimagetool}"

if ! command -v meson >/dev/null 2>&1; then
  echo "meson tidak ditemukan di PATH." >&2
  exit 1
fi
if ! command -v "$TOOL" >/dev/null 2>&1; then
  echo "appimagetool tidak ditemukan. Pasang atau set APPIMAGETOOL=/path/appimagetool." >&2
  exit 1
fi

rm -rf "$BUILD_DIR"
mkdir -p "$APPDIR"

meson setup "$BUILD_DIR/build" --prefix=/usr
DESTDIR="$APPDIR" meson install -C "$BUILD_DIR/build"

install -m 0755 "$ROOT/packaging/AppRun" "$APPDIR/AppRun"
install -Dm0644 "$ROOT/data/icons/hicolor/scalable/apps/$APP_ID.svg" \
  "$APPDIR/usr/share/icons/hicolor/scalable/apps/$APP_ID.svg"
install -m0644 "$ROOT/data/icons/hicolor/scalable/apps/$APP_ID.svg" \
  "$APPDIR/$APP_ID.svg"
# appimagetool mencari berkas .desktop di akar AppDir. Pakai berkas hasil
# konfigurasi Meson agar Exec memakai jalur absolut di dalam AppImage.
install -m0644 "$BUILD_DIR/build/$APP_ID.desktop" "$APPDIR/$APP_ID.desktop"

# AppDir tidak punya direktori spesifik arsitektur, jadi tentukan eksplisit.
export ARCH="${ARCH:-x86_64}"

# appimagetool lebih yakin dengan PNG di akar AppDir bila tersedia.
if command -v rsvg-convert >/dev/null 2>&1; then
  rsvg-convert -w 128 -h 128 \
    "$ROOT/data/icons/hicolor/scalable/apps/$APP_ID.svg" \
    > "$APPDIR/$APP_ID.png"
fi

"$TOOL" "$APPDIR" "$ROOT/IslamicHabits-x86_64.AppImage"
echo "AppImage selesai: $ROOT/IslamicHabits-x86_64.AppImage"
