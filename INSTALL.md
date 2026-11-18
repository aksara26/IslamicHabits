# Panduan instalasi IslamicHabits

Berkas ini berisi cara memasang, menjalankan, memperbarui, dan mencopot
IslamicHabits. Untuk daftar fitur, arsitektur, dan perilaku aplikasi, lihat
[`README.md`](README.md). Bila Anda sedang menyiapkan paket rilis, lihat
[`packaging/RELEASE.md`](packaging/RELEASE.md).

## 1. Memilih cara instalasi

| Format | Kegunaan |
|---|---|
| **Flatpak** | Jalur utama yang disarankan untuk aplikasi GNOME; dapat dibagikan sebagai bundle di GitHub Releases |
| **Sumber (Meson)** | Pengembangan dan instalasi lokal |
| **AppImage** | Opsional, satu berkas yang langsung dijalankan |

ID aplikasi yang dipakai di semua jalur adalah `io.github.kurakura.IslamicHabits`.

## 2. Dari sumber (Meson)

Cocok untuk mengubah kode sendiri. Dependensi di Fedora:

```bash
sudo dnf install meson ninja-build python3 python3-gobject python3-cairo gtk4 libadwaita \
  gtk4-devel libadwaita-devel glib2-devel desktop-file-utils appstream gettext
```

Dari folder proyek:

```bash
git clone https://github.com/kurakura/IslamicHabits.git
cd IslamicHabits
meson setup builddir
meson test -C builddir
sudo meson install -C builddir
```

Jalankan dari menu aplikasi atau lewat terminal:

```bash
islamichabits
```

Tanpa instalasi, langsung dari sumber juga bisa:

```bash
python3 -m src.main
```

**Memperbarui:** tarik kode terbaru, lalu ulangi `meson install -C builddir`.

**Mencopot:**

```bash
sudo ninja -C builddir uninstall
```

Perintah uninstall tidak menghapus data pengguna. Hapus manual folder data bila
memang ingin memulai dari kosong (lihat bagian 6).

## 3. Flatpak

Manifest ada di `packaging/io.github.kurakura.IslamicHabits.json` dan memakai
runtime GNOME 51 sesuai target proyek.

Pasang alat dan runtime bila belum ada:

```bash
sudo dnf install flatpak flatpak-builder
flatpak remote-add --if-not-exists flathub \
  https://flathub.org/repo/flathub.flatpakrepo
flatpak install flathub org.gnome.Sdk//51 org.gnome.Platform//51
```

Bangun dan pasang untuk pengguna saat ini:

```bash
cd IslamicHabits
flatpak-builder --user --install --force-clean builddir-flatpak \
  packaging/io.github.kurakura.IslamicHabits.json
flatpak run io.github.kurakura.IslamicHabits
```

Bila ingin berkas bundle untuk dibagikan:

```bash
flatpak-builder --repo=repo-flatpak --force-clean builddir-flatpak \
  packaging/io.github.kurakura.IslamicHabits.json
flatpak build-bundle repo-flatpak IslamicHabits.flatpak \
  io.github.kurakura.IslamicHabits
```

Pasang bundle yang diterima:

```bash
flatpak install --user IslamicHabits.flatpak
flatpak run io.github.kurakura.IslamicHabits
```

**Memperbarui:** bangun lagi dengan `--force-clean`, lalu `flatpak install --user`
berkas bundle baru.

**Mencopot:**

```bash
flatpak uninstall --delete-data io.github.kurakura.IslamicHabits
```

`@delete-data` hanya dipakai bila Anda memang ingin menghapus data aplikasi di
`~/.var/app/io.github.kurakura.IslamicHabits/`.

## 4. AppImage (opsional)

Unduh `IslamicHabits-x86_64.AppImage` dari halaman Releases, atau bangun sendiri:

```bash
cd IslamicHabits
bash packaging/build-appimage.sh
```

Skrip membutuhkan `meson`, `ninja`, dan `appimagetool`. Bila `appimagetool` belum
ada di PATH:

```bash
APPIMAGETOOL=/path/ke/appimagetool bash packaging/build-appimage.sh
```

Jalankan:

```bash
chmod +x IslamicHabits-x86_64.AppImage
./IslamicHabits-x86_64.AppImage
```

AppImage memakai Python, GTK4, dan libadwaita dari sistem host. Jadi paket ini
praktis sebagai satu berkas, tetapi **Flatpak lebih mandiri**. Simpan
ekspor/cadangan ke folder yang sama agar mudah dipindahkan.

**Mencopot:** hapus berkas `.AppImage`. Bila dulu mengintegrasikan dengan
`appimaged` atau launcher manual, hapus entri desktopnya juga. Data tetap ada di
`~/.local/share/io.github.kurakura.IslamicHabits/`.

## 5. Pertama kali menjalankan

1. Dialog pengenalan muncul sekali. Baca prinsipnya, lalu pilih **Mulai mencatat**.
2. Ibadah bawaan (sholat fardhu, sunnah, tilawah, dzikir, dan lain-lain) sudah
   tersedia di **Hari Ini**.
3. Sesuaikan daftar di **Kelola Ibadah**: tambah, ubah, urutkan, atau arsipkan.
   Arsip tidak menghapus riwayat.
4. Isi **Pengaturan** bila ingin tema tertentu, pengingat harian, atau folder
   cadangan.
5. Gunakan `Ctrl+1` / `Ctrl+2` / `Ctrl+3` untuk membuka Riwayat harian, bulanan,
   dan tahunan.

Tidak ada akun dan tidak ada jaringan. Seluruh isian disimpan lokal.

## 6. Lokasi data dan pencopotan

| Instalasi | Basis data | Cadangan bawaan |
|---|---|---|
| Sumber / AppImage | `$XDG_DATA_HOME/io.github.kurakura.IslamicHabits/islamichabits.sqlite3` atau `~/.local/share/io.github.kurakura.IslamicHabits/islamichabits.sqlite3` | `.../io.github.kurakura.IslamicHabits/backups/` |
| Flatpak | `~/.var/app/io.github.kurakura.IslamicHabits/data/io.github.kurakura.IslamicHabits/islamichabits.sqlite3` | `.../data/io.github.kurakura.IslamicHabits/backups/` |

Halaman **Pengaturan → Data → Lokasi data** menampilkan jalur ini dan tombol
**Buka folder**. Folder cadangan bisa diubah ke lokasi lain.

Mencopot aplikasi tidak otomatis menghapus data. Ini disengaja agar data tetap
aman saat aplikasi diperbarui atau dipasang ulang. Untuk menghapus semua data
dari dalam aplikasi, gunakan **Pengaturan → Data → Hapus semua data**; ibadah
bawaan akan dikembalikan. Untuk menghapus folder data sepenuhnya, hapus manual
jalur pada tabel di atas setelah membuat cadangan.

## 7. Mendapatkan paket dari GitHub Releases

- Kode berada di repositori, paket siap pakai berada di halaman Releases.
- Workflow `.github/workflows/build.yml` menjalankan tes, membangun AppImage, dan
  melampirkannya ke rilis saat tag `v*` di-push.
- Bundle Flatpak (`IslamicHabits.flatpak`) juga diunggah ke halaman Releases
  bila sudah dibangun.
- Cara membangun paket dan menerbitkan rilis ada di
  [`packaging/RELEASE.md`](packaging/RELEASE.md).
