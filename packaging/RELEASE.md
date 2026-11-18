# Catatan pengemasan rilis

Semua perintah dijalankan dari folder proyek.

## 1. Pastikan versi sudah tepat

Ubah `APP_VERSION` di `src/logic/constants.py`, `version` di `meson.build`, dan
`Version` di `data/io.github.kurakura.IslamicHabits.metainfo.xml` dengan nomor
yang sama. Jalankan tes sebelum melanjutkan:

```bash
python3 -m unittest discover -s tests -q
meson setup builddir
meson test -C builddir
```

## 2. Flatpak (utama)

```bash
flatpak install flathub org.gnome.Sdk//51 org.gnome.Platform//51
flatpak-builder --user --install --force-clean builddir-flatpak \
  packaging/io.github.kurakura.IslamicHabits.json
```

Untuk membuat berkas bundle yang bisa diunggah ke GitHub Releases:

```bash
flatpak-builder --repo=repo-flatpak --force-clean builddir-flatpak \
  packaging/io.github.kurakura.IslamicHabits.json
flatpak build-bundle repo-flatpak IslamicHabits.flatpak \
  io.github.kurakura.IslamicHabits
```

Pasang bundle di komputer lain dengan:

```bash
flatpak install --user IslamicHabits.flatpak
```

## 3. AppImage (opsional)

```bash
APPIMAGETOOL=/path/ke/appimagetool bash packaging/build-appimage.sh
```

AppImage tetap memakai Python, GTK4, dan libadwaita dari sistem host. Flatpak
lebih mandiri dan tetap disarankan untuk pengguna GNOME.

## 4. GitHub Releases

1. Buat tag `v0.1.0` (sesuaikan nomor versi) dan push ke GitHub.
2. Workflow `.github/workflows/build.yml` menjalankan tes, membangun AppImage,
   lalu melampirkannya ke rilis tag.
3. Unggah pula `IslamicHabits.flatpak` bila sudah dibangun.
4. Tulis catatan rilis singkat: fitur, perbaikan, dan cara instalasi.

Menerbitkan ke Flathub adalah langkah terpisah dan tidak wajib.
