#!/usr/bin/env bash
# Pemasang IslamicHabits untuk pengguna saat ini, tanpa sudo.
# Ambil aset terbaru dari GitHub Releases, verifikasi checksum, lalu pasang
# AppImage dan entri menu ke direktori data pengguna.
set -euo pipefail

APP_ID="io.github.kurakura.IslamicHabits"
APPIMAGE_NAME="IslamicHabits-x86_64.AppImage"
ICON_NAME="$APP_ID.svg"
BASE_URL="${ISLAMICHABITS_RELEASE_URL:-https://github.com/aksara26/IslamicHabits/releases/latest/download}"

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
APP_DIR="$DATA_HOME/islamichabits"
ICON_DIR="$DATA_HOME/icons/hicolor/scalable/apps"
DESKTOP_DIR="$DATA_HOME/applications"

for tool in curl sha256sum install mkdir mktemp; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "IslamicHabits: '$tool' tidak ditemukan di PATH." >&2
    exit 1
  fi
done

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "Mengunduh IslamicHabits dari $BASE_URL"
for asset in "$APPIMAGE_NAME" "$ICON_NAME" SHA256SUMS; do
  curl -fsSL "$BASE_URL/$asset" -o "$tmp/$asset"
done

echo "Memverifikasi checksum..."
(cd "$tmp" && sha256sum -c --status --ignore-missing SHA256SUMS)
echo "Checksum sesuai."

mkdir -p "$APP_DIR" "$BIN_DIR" "$ICON_DIR" "$DESKTOP_DIR"

install -m 0755 "$tmp/$APPIMAGE_NAME" "$APP_DIR/$APPIMAGE_NAME"
install -m 0644 "$tmp/$ICON_NAME" "$ICON_DIR/$ICON_NAME"

wrapper="$BIN_DIR/islamichabits"
cat >"$wrapper" <<EOF
#!/usr/bin/env bash
# Pembungkus AppImage IslamicHabits.
APPIMAGE='$APP_DIR/$APPIMAGE_NAME'
if ! "\$APPIMAGE" "\$@"; then
  APPIMAGE_EXTRACT_AND_RUN=1 exec "\$APPIMAGE" "\$@"
fi
EOF
chmod 0755 "$wrapper"

cat >"$DESKTOP_DIR/$APP_ID.desktop" <<EOF
[Desktop Entry]
Name=IslamicHabits
GenericName=Pelacak Ibadah
Comment=Catat ibadah harian secara lokal, cepat, dan tenang
Exec="$wrapper"
Icon=$APP_ID
Terminal=false
Type=Application
Categories=GTK;Utility;
StartupNotify=true
Keywords=ibadah;sholat;tilawah;dzikir;puasa;
EOF

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi

echo "IslamicHabits terpasang untuk pengguna ini."
echo "  Peluncur: $wrapper"
echo "  Data AppImage: $APP_DIR/$APPIMAGE_NAME"
echo "  Ikon: $ICON_DIR/$ICON_NAME"

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "Tambahkan $BIN_DIR ke PATH bila 'islamichabits' belum dikenali." ;;
esac

echo "Jalankan dengan: islamichabits"
