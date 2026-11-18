# Panduan instalasi IslamicHabits

Berkas ini berisi cara memasang, menjalankan, memperbarui, dan mencopot
IslamicHabits. Untuk daftar fitur, arsitektur, dan perilaku aplikasi, lihat
[`README.md`](README.md). Bila Anda sedang menyiapkan paket rilis, lihat
[`packaging/RELEASE.md`](packaging/RELEASE.md).

### Pertanyaan cepat: apa yang sebenarnya terdownload?

| Yang Anda lakukan | Yang terdownload | Aplikasi langsung jalan? |
|---|---|---|
| Menjalankan perintah installer di bagian 1 | Skrip `install.sh`, lalu skrip itu mengunduh AppImage, ikon, dan `SHA256SUMS` | **Ya.** AppImage terpasang otomatis di `~/.local` |
| Mengunduh `IslamicHabits-x86_64.AppImage` dari halaman Releases | Satu file AppImage | **Ya.** Beri izin jalankan, lalu buka file tersebut |
| `git clone https://github.com/aksara26/IslamicHabits.git` | Kode sumber, **bukan** aplikasi yang sudah jadi | **Belum.** Harus di-build/dipasang dulu, lihat bagian 3 |

Jadi, **clone tidak otomatis memasang aplikasi**. Clone dipakai kalau Anda ingin
mengubah kode. Kalau hanya ingin memakai aplikasinya, pakai installer satu
perintah atau unduh AppImage dari Releases.

## 1. Cara tercepat: satu perintah

Bila rilis sudah tersedia di GitHub Releases, pemasangan cukup satu baris:

```bash
curl -fsSL https://github.com/aksara26/IslamicHabits/releases/latest/download/install.sh | bash
```

Tidak perlu `sudo`. Script ini mengunduh AppImage dan ikon terbaru, memeriksa
checksum SHA256, lalu memasangnya untuk pengguna saat ini:

- peluncur: `~/.local/bin/islamichabits`
- AppImage: `~/.local/share/islamichabits/IslamicHabits-x86_64.AppImage`
- ikon: `~/.local/share/icons/hicolor/scalable/apps/`
- entri menu: `~/.local/share/applications/io.github.kurakura.IslamicHabits.desktop`

Bila `islamichabits` belum dikenali, tambahkan `~/.local/bin` ke `PATH` dan buka
terminal baru. Jalankan perintah yang sama untuk memperbarui ke rilis terbaru.

Untuk mencopot pemasangan ini, hapus peluncur, folder AppImage, ikon, dan entri
menu di atas. Data pengguna di `~/.local/share/io.github.kurakura.IslamicHabits/`
tidak ikut terhapus.

Catatan: AppImage memakai GTK4, libadwaita, dan PyGObject dari sistem host.
Script akan mencoba menjalankan AppImage langsung, lalu memakai mode ekstrak bila
FUSE tidak tersedia.

## 2. Memilih cara instalasi

| Format | Kegunaan |
|---|---|
| **Installer satu perintah** | Cara tercepat; mengunduh AppImage terbaru dari Releases tanpa `sudo` |
| **Flatpak** | Jalur mandiri yang disarankan untuk aplikasi GNOME; dapat dibagikan sebagai bundle di GitHub Releases |
| **Sumber (Meson)** | Pengembangan dan instalasi lokal |
| **AppImage** | Satu berkas yang juga dipakai installer di atas |

ID aplikasi yang dipakai di semua jalur adalah `io.github.kurakura.IslamicHabits`.

## 3. Dari sumber (Meson)

Cocok untuk mengubah kode sendiri. Dependensi di Fedora:

```bash
sudo dnf install meson ninja-build python3 python3-gobject python3-cairo gtk4 libadwaita \
  gtk4-devel libadwaita-devel glib2-devel desktop-file-utils appstream gettext
```

Dari folder proyek:

```bash
git clone https://github.com/aksara26/IslamicHabits.git
cd IslamicHabits
meson setup builddir
meson test -C builddir
sudo meson install -C builddir
```

Kalau tidak ingin memakai `sudo`, pasang ke folder pengguna saja:

```bash
meson configure builddir --prefix="$HOME/.local"
meson install -C builddir
export PATH="$HOME/.local/bin:$PATH"
```

Bila memakai jalur pengguna, lewati perintah `sudo ninja -C builddir uninstall`
di bawah. Untuk mencopotnya, jalankan `ninja -C builddir uninstall` tanpa `sudo`.

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
memang ingin memulai dari kosong (lihat bagian 7).

## 4. Flatpak

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

## 5. AppImage (opsional)

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

## 6. Pertama kali menjalankan

1. Dialog pengenalan muncul sekali. Baca prinsipnya, lalu pilih **Mulai mencatat**.
2. Ibadah bawaan (sholat fardhu, sunnah, tilawah, dzikir, dan lain-lain) serta
   kebiasaan bawaan (Belajar, Baca buku, Olahraga, Jalan kaki, Tidur awal) sudah
   tersedia di **Hari Ini** dan ikut dihitung di statistik yang sama.
3. Sesuaikan daftar di **Kelola Ibadah**: tambah, ubah, urutkan, atau arsipkan.
   Arsip tidak menghapus riwayat. Tombol **Tambah kebiasaan** menyiapkan preset
   kebiasaan dengan kategori **Kebiasaan**; pintasannya `Ctrl+Shift+N`.
4. Isi **Pengaturan** bila ingin tema tertentu (**Hijau** default, **Putih**,
   atau **Hitam**), pengingat harian, popup pemberitahuan, atau folder cadangan.
5. Sidebar memiliki tujuh menu terpisah: **Hari Ini**, **Riwayat**,
   **Kalender**, **Memo**, **Muhasabah**, **Kelola Ibadah**, dan
   **Pengaturan**. Pintasannya: `Ctrl+1` Riwayat harian, `Ctrl+2` Kalender,
   `Ctrl+3` Riwayat tahunan, `Ctrl+4` Muhasabah, `Ctrl+5` Memo, dan
   `Ctrl+Shift+N` kebiasaan baru.
6. Halaman **Riwayat** memuat tiga tren garis: 30 hari terakhir, per hari dalam
   satu bulan, dan per bulan dalam satu tahun. Klik titik tren harian untuk
   membuka tanggal itu; klik titik tren tahunan untuk membuka Kalender.
7. Halaman **Memo** (`Ctrl+5`) menyimpan teks memo harian dan lampiran foto
   (JPG, PNG, WEBP, GIF; maksimal 25 MB per berkas). Teks tersimpan otomatis,
   tombol **Simpan** dan `Ctrl+S` menyimpan segera, dan foto disalin ke folder
   `memo/` di folder data. Tombol **Memo sebelumnya** membuka daftar memo lama
   dengan pencarian, cuplikan, dan jumlah foto. Kartu **Memo harian** di atas
   daftar **Hari Ini** menautkan ke halaman ini.
8. Tombol **Kalender** di halaman Memo membuka dialog **Kalender Memo**. Pilih
   satu tanggal untuk melihat checklist kegiatan, pratinjau memo, dan pengingat
   tanggal itu. Pengingat di sini **terpisah dari memo** dan punya jam sendiri;
   isian ini bisa dibuat untuk tanggal lampau, hari ini, atau masa depan.
   Pengingat hari ini akan muncul sebagai toast dan popup saat jamnya tiba bila
   popup diizinkan.
9. `Ctrl+F` membuka **pencarian global** untuk memo, pengingat, muhasabah,
   catatan ibadah, dan nama ibadah; memilih hasil langsung membuka halaman dan
   tanggal yang tepat.

Tidak ada akun dan tidak ada jaringan. Seluruh isian disimpan lokal.

### Izin notifikasi

Pengingat hanya berjalan saat aplikasi terbuka. Saat Anda menyalakan **Popup
pemberitahuan** atau pengingat, aplikasi meminta izin lewat dialog di dalam
aplikasi. Setelah diizinkan, aplikasi mengirim notifikasi desktop lewat GNOME.
Tombol **Uji notifikasi** mengirim satu popup contoh:

- Jika popup tidak muncul, periksa **Pengaturan Sistem → Notifikasi** dan
  pastikan `IslamicHabits` diizinkan.
- Toast di dalam aplikasi tetap muncul walaupun izin popup ditolak.
- Klik popup akan membuka halaman Memo pada hari ini.
- Pengingat per tanggal dari dialog **Kalender Memo** memakai izin popup yang
  sama; hanya pengingat hari ini yang memicu notifikasi, dan status terkirim
  mencegah pesan yang sama muncul berulang.
- Versi Flatpak memakai ID `io.github.kurakura.IslamicHabits` dalam pengaturan
  notifikasi sistem.

## 7. Lokasi data dan pencopotan

| Instalasi | Basis data | Foto memo | Cadangan bawaan |
|---|---|---|---|
| Sumber / AppImage | `$XDG_DATA_HOME/io.github.kurakura.IslamicHabits/islamichabits.sqlite3` atau `~/.local/share/io.github.kurakura.IslamicHabits/islamichabits.sqlite3` | `.../io.github.kurakura.IslamicHabits/memo/` | `.../io.github.kurakura.IslamicHabits/backups/` |
| Flatpak | `~/.var/app/io.github.kurakura.IslamicHabits/data/io.github.kurakura.IslamicHabits/islamichabits.sqlite3` | `.../data/io.github.kurakura.IslamicHabits/memo/` | `.../data/io.github.kurakura.IslamicHabits/backups/` |

Halaman **Pengaturan → Data → Lokasi data** menampilkan jalur ini dan tombol
**Buka folder**. Folder cadangan bisa diubah ke lokasi lain. Foto memo adalah
berkas biasa di folder `memo/`; ekspor JSON menyertakannya sebagai base64,
sedangkan cadangan mingguan memakai format yang sama.

Mencopot aplikasi tidak otomatis menghapus data. Ini disengaja agar data tetap
aman saat aplikasi diperbarui atau dipasang ulang. Untuk menghapus semua data
dari dalam aplikasi, gunakan **Pengaturan → Data → Hapus semua data**; ibadah,
kebiasaan bawaan, dan berkas foto memo akan dibersihkan, lalu ibadah dan
kebiasaan bawaan dikembalikan. Untuk menghapus folder data sepenuhnya, hapus manual
jalur pada tabel di atas setelah membuat cadangan.

## 8. Mendapatkan paket dari GitHub Releases

- Kode berada di repositori, paket siap pakai berada di halaman Releases.
- Workflow `.github/workflows/build.yml` menjalankan tes, membangun AppImage, dan
  melampirkannya ke rilis saat tag `v*` di-push. Aset yang diunggah: AppImage,
  `install.sh`, `SHA256SUMS`, dan ikon SVG.
- Bundle Flatpak (`IslamicHabits.flatpak`) juga diunggah ke halaman Releases
  bila sudah dibangun.
- Cara membangun paket dan menerbitkan rilis ada di
  [`packaging/RELEASE.md`](packaging/RELEASE.md).
