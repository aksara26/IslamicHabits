# IslamicHabits

Aplikasi desktop Linux untuk mencatat ibadah **dan kebiasaan** harian secara pribadi. Dibuat untuk penggunaan sendiri, data tersimpan lokal, tanpa akun, tanpa server, dan didistribusikan lewat GitHub.

> **Status:** versi 0.3.1 siap untuk uji pakai. Ibadah dan kebiasaan umum (belajar, baca buku, olahraga, dan lain-lain) memakai satu sistem pencatatan dan satu statistik. Tersedia tren garis **harian, bulanan per hari, dan tahunan per bulan**, Hari Ini sebagai ringkasan dengan tombol tambah cepat, **halaman Memo dengan lampiran foto**, Kalender terpisah, Histori Catatan, Muhasabah, Pengaturan, pengingat dengan izin popup, aksesibilitas dasar, ekspor/impor/cadangan, serta installer satu perintah tanpa `sudo`. Palet sage dan tata letak sudah dirapikan di semua halaman. Uji visual dan penerimaan notifikasi di sesi GNOME 51 nyata tetap disarankan sebelum rilis publik.

> **Panduan instalasi:** [`INSTALL.md`](INSTALL.md). Berkas ini fokus pada fitur, arsitektur, dan perilaku aplikasi.

---

## Daftar Isi

1. [Tujuan dan Prinsip](#1-tujuan-dan-prinsip)
2. [Cakupan](#2-cakupan)
3. [Teknologi dan Lingkungan Pengembangan](#3-teknologi-dan-lingkungan-pengembangan)
4. [Arsitektur](#4-arsitektur)
5. [Model Data](#5-model-data)
6. [Struktur Jendela](#6-struktur-jendela)
7. [Peta Halaman dan Alur](#7-peta-halaman-dan-alur)
8. [Rincian Tiap Halaman](#8-rincian-tiap-halaman)
9. [Komponen Antarmuka](#9-komponen-antarmuka)
10. [Desain Visual](#10-desain-visual)
11. [Interaksi dan Pintasan Keyboard](#11-interaksi-dan-pintasan-keyboard)
12. [Pengingat](#12-pengingat)
13. [Ekspor, Impor, dan Cadangan](#13-ekspor-impor-dan-cadangan)
14. [Aksesibilitas](#14-aksesibilitas)
15. [Pengujian](#15-pengujian)
16. [Pengemasan dan Distribusi](#16-pengemasan-dan-distribusi)
17. [Rencana Pengerjaan](#17-rencana-pengerjaan)
18. [Keputusan yang Masih Terbuka](#18-keputusan-yang-masih-terbuka)
19. [Risiko yang Diketahui](#19-risiko-yang-diketahui)

---

## 1. Tujuan dan Prinsip

Aplikasi ini membantu pengguna mencatat dan merefleksikan ibadah hariannya (sholat, tilawah, puasa sunnah, dzikir, dan lainnya) **serta kebiasaan umum** seperti belajar, baca buku, olahraga, jalan kaki, dan tidur awal dengan cepat dan tenang. Keduanya sengaja tidak dibedakan sebagai dua sistem data: satu kegiatan cukup satu catatan per hari dan ikut dihitung di statistik yang sama.

**Prinsip desain:**

1. **Berbasis kesadaran pengguna.** Semua isian dilakukan sendiri oleh pengguna. Aplikasi adalah alat bantu mengingat dan bercermin, bukan pengawas.
2. **Cepat.** Mencatat satu kegiatan cukup satu klik atau satu tombol. Target seluruh pencatatan harian kurang dari 10 detik.
3. **Tenang.** Tidak ada kalimat menghukum ("gagal", "streak putus"), tidak ada warna merah untuk status belum, tidak ada peringkat atau perbandingan.
4. **Privat dan lokal.** Data hanya ada di komputer pengguna. Tidak ada akun, tidak ada jaringan.
5. **Mudah dikoreksi.** Salah centang, lupa mengisi kemarin, atau salah hapus harus bisa diperbaiki.
6. **Hari ini dulu.** Halaman utama hanya menjawab satu pertanyaan: apa yang sudah dan belum hari ini.

---

## 2. Cakupan

### Termasuk (versi pertama)

- Pencatatan ibadah dan kebiasaan harian: centang, angka, dan status
- Tambah kebiasaan cepat lewat tombol **Tambah kebiasaan** dengan preset belajar, baca buku, olahraga, jalan kaki, dan tidur awal
- Catatan bebas harian per tanggal, terpisah dari catatan kegiatan dan muhasabah
- **Halaman Memo** dengan editor catatan harian dan galeri foto (JPG, PNG, WEBP, GIF); foto disalin ke folder data, bukan disimpan di basis data
- **Kartu Memo harian** ringkas di bawah checklist Hari Ini yang menautkan ke halaman Memo
- Kategori dan pengelolaan kegiatan (tambah, ubah, urutkan, arsipkan), termasuk kategori **Kebiasaan**
- Riwayat dengan tiga tren: harian 30 hari, bulanan per hari, dan tahunan per bulan
- Kalender bulanan terpisah dengan penanda status, penanda catatan, dan penanda pengingat hari ini
- Histori Catatan berisi catatan harian dan jumlah foto, terpisah dari catatan kegiatan dan muhasabah
- Statistik yang sama untuk ibadah dan kebiasaan, dihitung sejak tanggal mulai aktif
- Catatan muhasabah harian
- Ekspor, impor, dan cadangan data (kompatibel dengan berkas lama; foto ikut diekspor sebagai base64)
- Tiga tema dengan aksen sage: **Hijau** (default), **Putih**, dan **Hitam**
- Pengingat berdasarkan jam yang dipilih pengguna, dengan toast dan popup desktop setelah izin diberikan di dalam aplikasi

### Sengaja tidak termasuk

- **Jadwal waktu sholat otomatis.** Ditunda karena risiko ketidakakuratan. Pengguna mengisi sendiri status dan, bila mau, jamnya. Fitur ini bisa dipertimbangkan nanti dengan verifikasi yang cermat terhadap sumber resmi.
- **Akun, sinkronisasi, dan fitur sosial.**
- **Versi web dan versi seluler.** Fokus awal hanya desktop Linux.
- **Kalender Hijriah** dan ibadah yang bergantung padanya (misalnya Ayyamul Bidh). Konversi tanpa sumber otoritatif bisa meleset satu hari. Versi awal hanya memakai Senin-Kamis (berdasarkan hari Masehi) dan penandaan manual.

---

## 3. Teknologi dan Lingkungan Pengembangan

| Lapisan | Pilihan | Catatan |
|---|---|---|
| Bahasa | Python | |
| Antarmuka | GTK4 + libadwaita lewat PyGObject | Native untuk GNOME |
| Build | Meson | Standar aplikasi GNOME |
| Database | SQLite | Satu berkas, tanpa server |
| Pengemasan | Flatpak (utama), AppImage (opsional) | Lihat `INSTALL.md` dan bagian 16 |
| Lisensi | GPL-3.0-or-later | Lihat berkas `LICENSE` |
| ID aplikasi | `io.github.kurakura.IslamicHabits` | Dipakai untuk desktop entry, Flatpak, GSettings, dan path data |

### Lingkungan target: Fedora 45 (Workstation, GNOME 51)

Lingkungan pengembang adalah **Fedora Linux 45**, dirilis 3 November 2026, dengan desktop **GNOME 51**. Versi yang diketahui dari sumber rilis:

- **libadwaita 1.10.0** (paket Fedora 45)
- **Python 3.15** sebagai Python bawaan
- GCC 16, kernel Linux 7.2

Konsekuensinya:

- Ini lingkungan yang sangat baru, jadi komponen libadwaita modern tersedia. Namun **tetap verifikasi tiap komponen pada dokumentasi libadwaita 1.10** sebelum dipakai, karena beberapa komponen lama bisa sudah usang (deprecated).
- **Python 3.15 sangat baru.** Pustaka pihak ketiga dan PyGObject dari paket sistem biasanya mengikuti, tetapi **uji lebih awal** bahwa semua dependensi berjalan di versi ini. Satu laporan rilis menyebut modul `pkg_resources` terdampak pada sebagian proyek Python, jadi hindari ketergantungan padanya.
- Tentukan **versi minimum yang didukung** bila aplikasi nanti ingin dipakai di distribusi lain. Untuk penggunaan pribadi di Fedora 45, ini bukan masalah.
- Bila dikemas sebagai Flatpak, versi runtime ditentukan oleh paket Flatpak itu sendiri, bukan oleh sistem hostmu. Periksa dokumentasi Flatpak untuk runtime yang dipakai.

Kerangka awal sudah diuji dengan **Python 3.15.2** dan **GTK 4.24**: impor `gi` berhasil, tes logika berjalan tanpa jendela, dan komponen garis tren bisa dibuat. Ini bukan pengganti uji pada Fedora 45; tetap cocokkan dokumentasi versi yang dipakai sebelum menambah widget baru.

### Menyiapkan lingkungan pengembangan (Fedora)

Dependensi GTK4, libadwaita, dan PyGObject sebagian besar adalah **paket sistem**, bukan paket pip. Paket yang umum dibutuhkan proyek sejenis di Fedora:

```bash
sudo dnf install meson ninja-build python3 python3-gobject python3-cairo gtk4 libadwaita \
  gtk4-devel libadwaita-devel glib2-devel desktop-file-utils appstream gettext
```

Pasang juga `flatpak` dan `flatpak-builder` bila ingin membuat paket Flatpak. Daftar paket di atas bisa berbeda tergantung kebutuhan akhir proyek, jadi sesuaikan saat implementasi.

### Menjalankan dan menguji dari sumber

```bash
python3 -m src.main          # jalankan aplikasi (data dibuat otomatis di XDG_DATA_HOME)
python3 -m unittest discover -s tests -q
```

Build, uji, dan instal dengan Meson:

```bash
meson setup builddir
meson test -C builddir
DESTDIR=/tmp/install-root meson install -C builddir
```

Setelah terpasang, jalankan `islamichabits`. Paket Python dipasang sebagai `islamichabits`, sedangkan direktori sumber tetap bernama `src`.

---

## 4. Arsitektur

Tiga lapisan dengan pemisahan tegas:

1. **Data**: koneksi SQLite, akses data (tambah, ubah, hapus, ambil), migrasi skema.
2. **Logika**: aturan ibadah (hari aktif, tipe isian), perhitungan statistik, ekspor dan impor, validasi.
3. **Antarmuka**: jendela, halaman, dialog, notifikasi.

**Aturan utama:** lapisan logika tidak boleh bergantung pada antarmuka. Dengan begitu logika bisa diuji tanpa membuka jendela dan antarmuka bisa diubah tanpa menulis ulang inti.

### Struktur proyek saat ini

```
IslamicHabits/
├── README.md               # fitur, arsitektur, dan perilaku
├── INSTALL.md              # panduan instalasi dan lokasi data
├── LICENSE                 # GPL-3.0-or-later
├── .gitignore              # data pengguna & build tidak masuk git
├── meson.build             # build + install
├── data/
│   ├── io.github.kurakura.IslamicHabits.desktop
│   ├── io.github.kurakura.IslamicHabits.metainfo.xml
│   ├── style.css           # aturan + palet tema Hijau (default)
│   ├── style-putih.css     # override warna tema Putih
│   ├── style-hitam.css     # override warna tema Hitam
│   └── icons/hicolor/scalable/apps/io.github.kurakura.IslamicHabits.svg
├── src/
│   ├── __init__.py
│   ├── islamichabits       # launcher setelah terpasang
│   ├── main.py             # Adw.Application, tema, aksi notifikasi, cadangan awal
│   ├── logic/
│   │   ├── __init__.py
│   │   ├── constants.py    # APP_NAME, APP_ID, versi, kunci pengaturan
│   │   ├── defaults.py     # ibadah & kebiasaan bawaan saat basis data dibuat
│   │   ├── statistics.py   # aturan harian/bulanan/tahunan, murni Python
│   │   ├── database.py     # koneksi SQLite, skema, migrasi, seed kebiasaan
│   │   ├── repository.py   # CRUD tanpa GTK
│   │   └── transfer.py     # ekspor/impor/cadangan JSON berversi
│   └── ui/
│       ├── __init__.py
│       ├── main_window.py  # navigasi adaptif 8 menu + aksi/pintasan
│       ├── today_page.py   # halaman Hari Ini + tombol tambah cepat + kartu Memo
│       ├── history_page.py # Riwayat Harian/Bulanan/Tahunan
│       ├── history_common.py  # format tanggal, simbol status, filter bersama
│       ├── calendar_page.py   # Kalender bulanan + banner pengingat
│       ├── note_history_page.py  # Histori Catatan harian
│       ├── memo_page.py    # Memo harian: editor, galeri foto, dialog izin/file
│       ├── muhasabah_page.py
│       ├── settings_page.py
│       ├── manage_page.py  # Kelola Ibadah
│       ├── worship_row.py  # tiga varian baris ibadah
│       ├── worship_dialog.py
│       ├── trend_line.py   # Gtk.DrawingArea + Cairo
│       ├── a11y.py         # label pembaca layar
│       └── theme.py        # tema Adw + CSS
├── tests/
│   ├── test_statistics.py
│   ├── test_database.py
│   ├── test_repository.py
│   ├── test_transfer.py
│   ├── test_theme_contrast.py  # rasio kontras palet sage tanpa GTK
│   └── test_ui_smoke.py
└── packaging/
    ├── io.github.kurakura.IslamicHabits.json  # manifest Flatpak
    ├── AppRun                                 # peluncur AppImage
    ├── build-appimage.sh                      # pembuat AppImage
    ├── install.sh                             # pemasang satu perintah tanpa sudo
    └── RELEASE.md                             # langkah rilis
```

### Lokasi penyimpanan data

Data disimpan di folder data pengguna standar Linux, yaitu `$XDG_DATA_HOME/io.github.kurakura.IslamicHabits/islamichabits.sqlite3` atau `~/.local/share/io.github.kurakura.IslamicHabits/islamichabits.sqlite3` bila `XDG_DATA_HOME` tidak diatur. Cadangan awal ada di `.../io.github.kurakura.IslamicHabits/backups/` dan bisa diubah lewat Pengaturan.

Pada Flatpak lokasinya berbeda, yaitu `~/.var/app/io.github.kurakura.IslamicHabits/data/io.github.kurakura.IslamicHabits/`. Karena itu aplikasi **mengambil lokasi dari sistem**, tidak memakai jalur tetap. Halaman Pengaturan menampilkan lokasi ini dan tombol untuk membuka foldernya.

### Identitas aplikasi

Tetapkan di awal karena mengubahnya belakangan memengaruhi desktop entry, identitas Flatpak, skema pengaturan, dan data pengguna:

- **Nama tampilan:** IslamicHabits
- **ID aplikasi:** `io.github.kurakura.IslamicHabits`
- **Lisensi:** GPL-3.0-or-later (berkas `LICENSE`)
- Ikon SVG bergaya kubah masjid dengan palet sage sudah dipakai; tetap periksa keterbacaan ikon pada ukuran kecil
- Kategori dan deskripsi singkat untuk peluncur aplikasi sudah ada di desktop entry

---

## 5. Model Data

| Tabel | Isi |
|---|---|
| **kategori** | nama, urutan, status lipat (termasuk **Kebiasaan**) |
| **ibadah** | satu tabel untuk ibadah **dan** kebiasaan: nama, kategori, tipe isian (centang / angka / status), target, satuan, hari aktif, **`aktif_mulai`**, urutan, status arsip |
| **catatan** | kegiatan (ibadah atau kebiasaan), tanggal, nilai atau status, jam pelaksanaan (opsional), catatan teks |
| **muhasabah** | tanggal, teks, jawaban pertanyaan pemantik |
| **catatan_harian** | tanggal, catatan bebas untuk hari itu (skema v2) |
| **memo_foto** | id, tanggal, nama berkas di folder `memo/`, keterangan, urutan (skema v3) |
| **pengaturan** | tema, jam pengingat, popup pengingat, izin popup, preferensi tampilan |
| **meta** | nomor versi skema |

**Aturan data:**

- **Satu catatan per kegiatan (ibadah atau kebiasaan) per tanggal.** Kebiasaan tidak memakai tabel terpisah dan tidak masuk Histori Catatan.
- **Satu catatan harian bebas per tanggal**, berbeda dari catatan per kegiatan dan dari muhasabah.
- **Foto memo disimpan sebagai berkas** di `memo/` dalam folder data, bukan sebagai BLOB, supaya basis data tetap ringan dan berkas bisa dicadangkan terpisah. Tabel `memo_foto` hanya menyimpan nama berkas, keterangan, dan urutan.
- Statistik **dihitung dari catatan**, tidak disimpan sebagai angka mati. Dengan begitu koreksi data masa lalu tidak merusak hitungan.
- Kegiatan yang diarsipkan menjadi **arsip**, bukan dihapus fisik, agar riwayat utuh.
- Tanggal disimpan sebagai tanggal lokal murni (tahun-bulan-hari), tanpa jam.
- Nomor versi skema kini **v3**; basis data lama otomatis dimigrasikan tanpa kehilangan data (v1 → v2 menambah `catatan_harian`, v2 → v3 menambah `memo_foto`).
- `aktif_mulai` dipakai sebagai denominator statistik. Kegiatan baru tidak dihitung pada tanggal sebelum ia ditambahkan, agar riwayat lama tidak terasa menghukum.
- Kegiatan arsip tetap disimpan dan boleh ikut statistik lewat toggle "Tampilkan arsip".

### Definisi "terlaksana"

| Tipe | Terlaksana | Catatan |
|---|---|---|
| Centang | nilainya `True` | Ulangi klik untuk membatalkan |
| Angka | `nilai >= target` | Target kosong/0 → cukup `nilai > 0`; yang belum capai target disebut **sebagian** |
| Status | semua kecuali `belum` | `qadha` tetap terhitung sebagai catatan jujur |

Penanda harian: **kosong** (tidak ada catatan), **sebagian** (ada catatan tapi belum lengkap), **penuh** (semua kegiatan aktif terlaksana). Statistik tidak memakai kata "gagal" dan tidak menampilkan streak.

### Daftar kegiatan bawaan (bisa diubah pengguna)

| Kategori | Contoh |
|---|---|
| Sholat fardhu | Subuh, Dzuhur, Ashar, Maghrib, Isya |
| Sholat sunnah | Rawatib, dhuha, tahajud, witir |
| Al-Qur'an | Tilawah (halaman), hafalan, muraja'ah |
| Dzikir | Pagi, petang, setelah sholat |
| Puasa sunnah | Senin-Kamis |
| Amal | Sedekah, silaturahmi |
| Kebiasaan | Belajar (30 menit), Baca buku (10 halaman), Olahraga, Jalan kaki (20 menit), Tidur awal |

Lima kebiasaan di atas dibuat otomatis pada kategori **Kebiasaan**, baik untuk basis data baru maupun saat memperbarui basis data lama. Tombol **Tambah kebiasaan** menyediakan preset yang sama dan tetap bisa diubah nama, target, satuan, serta hari aktifnya.

### Tipe isian

- **Centang**: selesai atau belum
- **Angka**: jumlah terhadap target (misalnya halaman)
- **Status**: pilihan bertingkat. Untuk sholat fardhu: belum, tepat waktu, terlambat, berjamaah, qadha. Murni catatan jujur pengguna.

---

## 6. Struktur Jendela

Satu jendela utama dengan tiga zona:

```
┌───────────────────────────────────────────────┐
│ Bilah judul: [menu]  Judul halaman  [cari][+] │
├────────┬─────────────────────────┬────────────┤
│ SIDE-  │                         │ PANEL      │
│ BAR    │    AREA KONTEN          │ RINGKASAN  │
│        │    (halaman aktif)      │ (opsional) │
└────────┴─────────────────────────┴────────────┘
```

- **Bilah judul**: menu, judul halaman, pencarian, tombol tambah
- **Sidebar kiri**: delapan menu terpisah — Hari Ini, Riwayat, Kalender, Histori Catatan, Memo, Muhasabah, Kelola Ibadah, Pengaturan; bisa dilipat
- **Area konten**: halaman aktif
- **Panel kanan**: ringkasan, bisa disembunyikan; hilang otomatis pada jendela sempit

Jendela harus tetap rapi saat dikecilkan. Tetapkan ukuran minimum dan uji pada layar laptop kecil.

---

## 7. Peta Halaman dan Alur

```
Peluncuran
   ├─ (pertama kali) → Pengenalan → Pilih ibadah awal ─┐
   └─ (selanjutnya) ───────────────────────────────────┤
                                                       ▼
                                                  HARI INI ◄────────┐
       ┌──────────┬──────────┬──────────────┬────────┬────────────┐ │
       ▼          ▼          ▼              ▼        ▼            ▼ │
   RIWAYAT   KALENDER  HISTORI CATATAN   MEMO   MUHASABAH  KELOLA/  │
   Harian/    Bulanan +  Catatan harian  teks +  Refleksi  PENGATURAN│
   Tahunan    detail hari       │        foto        │      data     │
      │           │             ▼          ▼          ▼             │
  capaian +   pilih tanggal  buka tanggal buka memo editor terpandu  │
  catatan                                                           │
```

### Alur pengguna utama

1. **Pertama kali:** pengenalan, lalu masuk ke Hari Ini dengan ibadah dan kebiasaan bawaan.
2. **Harian:** buka aplikasi, centang ibadah dan kebiasaan, selesai.
3. **Malam:** lengkapi yang tertinggal, tulis memo harian (teks dan foto bila mau), lalu muhasabah.
4. **Berkala:** buka Riwayat untuk tren, Kalender atau Histori Catatan untuk rincian, lalu lakukan cadangan.

---

## 8. Rincian Tiap Halaman

### 8.1 Pengenalan (sekali saja)

- Sambutan singkat dan penjelasan prinsip: pencatatan jujur oleh diri sendiri, data lokal, tanpa akun
- Ibadah dan kebiasaan bawaan sudah disiapkan saat basis data pertama kali dibuat; pengguna bisa mengubahnya lewat Kelola Ibadah
- Tidak meminta data pribadi; status "pengenalan selesai" disimpan di tabel `meta`
- Selesai langsung menuju Hari Ini

### 8.2 Hari Ini (halaman utama)

**Tujuan:** menjawab "apa yang sudah dan belum hari ini" secepat mungkin.

**Komponen:**

- Header tanggal dengan tombol hari sebelumnya, berikutnya, dan kembali ke hari ini
- Ringkasan progres berupa kalimat netral dan bilah halus, dengan tombol **Tambah ibadah** dan **Tambah kebiasaan**
- Daftar ibadah **dan kebiasaan** dikelompokkan per kategori, tiap kelompok bisa dilipat
- Kartu **Memo harian** di bawah daftar: pratinjau dua baris, jumlah foto, dan tombol **Buka Memo** yang membuka halaman Memo pada tanggal itu. Teks lengkap dan foto ditulis di halaman Memo agar daftar ibadah tetap ringkas.

**Perilaku per jenis baris:**

- **Centang**: klik atau Spasi menandai selesai, ulangi untuk membatalkan
- **Angka**: tombol kurang dan tambah, atau ketik langsung
- **Status**: klik membuka pilihan kecil (belum, tepat waktu, terlambat, berjamaah, qadha)
- **Aksi sekunder** (detail, catatan): muncul saat kursor di atas baris, dan selalu tersedia lewat keyboard

**Panel detail kegiatan:** panel samping atau jendela kecil berisi status, jam pelaksanaan (opsional, boleh kosong), dan catatan. Tidak berpindah halaman agar konteks tidak hilang.

**Kondisi khusus:**

| Kondisi | Perilaku |
|---|---|
| Tidak ada ibadah atau kebiasaan aktif | Pesan ramah dan dua tombol tambah |
| Hari lampau | Tampil sama, dengan penanda lembut bahwa sedang mengisi hari lampau |
| Hari depan | Boleh dilihat, pencatatan dibatasi |
| Pergantian hari saat aplikasi terbuka | Tawarkan beralih ke hari baru, jangan mengubah tampilan tiba-tiba |

### 8.3 Riwayat

Halaman ini punya switcher **Harian / Bulanan / Tahunan**. Kalender bukan mode di sini, melainkan menu navbar tersendiri (`Ctrl+2`).

- **Harian** (`Ctrl+1`): rekap satu tanggal; penanda `○` kosong, `◐` sebagian, dan `●` penuh **tidak bergantung warna saja**. Setiap kegiatan menampilkan status, jam, nilai/target, dan catatan bila ada. Di bawahnya tampil **memo harian** tanggal itu beserta jumlah foto. Tombol "Lihat dan isi di Hari Ini" membuka tanggal yang sama untuk dikoreksi.
- **Harian — tren 30 hari**: garis lengkung untuk 30 tanggal terakhir. Klik titik untuk membuka tanggal itu di Hari Ini.
- **Bulanan**: garis tren **per hari dalam satu bulan** (satu titik untuk setiap tanggal) plus rincian "Hari 1 … 31". Ini statistik, bukan pengganti Kalender.
- **Tahunan** (`Ctrl+3`): garis tren **12 titik (Jan–Des)** — bukan batang, bukan heatmap. Titik yang tidak punya kegiatan aktif sengaja putus, bukan angka 0. Klik titik/bulan untuk membuka halaman **Kalender** pada bulan itu.
- Filter per kegiatan atau kategori, dengan toggle "Tampilkan arsip".
- Bahasa netral: "Terlaksana 18 dari 30 hari", bukan "gagal".
- Semua garis memakai satu widget `TrendLine` dengan alternatif teks dan navigasi panah kiri/kanan + Enter. Label sumbu ditampilkan untuk 12 titik agar tidak bertumpuk.

### 8.4 Kalender

Menu navbar tersendiri (`Ctrl+2`), hasil pemindahan dari mode bulanan Riwayat — bukan halaman duplikat.

- Kalender bulan berisi penanda status tiap hari, tanda `✎` bila hari itu punya memo, tanda `◷` pada hari ini bila pengingat aktif, panel **detail hari terpilih** berisi capaian per kegiatan, memo hari itu, dan jumlah foto, lalu **ringkasan per kegiatan** untuk sebulan, mis. "Tilawah: 18 dari 30 hari aktif".
- Banner pengingat di atas kalender menampilkan jam dan status izin popup; tombol **Atur** membuka Pengaturan, atau **Aktifkan** bila pengingat belum hidup.
- Klik sebuah tanggal untuk memperbarui panel detail; tombol **Isi hari ini di Hari Ini** membuka tanggal itu untuk dikoreksi, sedangkan **Buka Memo** membuka halaman Memo pada tanggal tersebut.
- Filter per kegiatan/kategori dan toggle "Tampilkan arsip" memakai helper yang sama dengan Riwayat, sehingga simbol dan formatnya konsisten.
- Sel hari diberi kartu lembut dan hari terpilih ditandai dengan latar sage, tetap disertai teks status.

### 8.5 Histori Catatan

Menu navbar tersendiri (`Ctrl+4`) yang **hanya menampilkan memo harian** (teks `catatan_harian` beserta jumlah foto).

- Daftar catatan diurutkan dari tanggal terbaru, dengan pencarian teks dan tanggal; baris yang hanya berisi foto tetap muncul dengan keterangan jumlah foto
- Pratinjau satu catatan yang dipilih; Enter atau klik baris membuka tanggal itu di Hari Ini, sedangkan tombol **Buka Memo** membuka halaman Memo
- Halaman kosong yang ramah bila belum ada catatan atau tidak ada hasil pencarian
- Catatan per kegiatan tetap berada di Riwayat/Kalender; muhasabah tetap berada di halaman Muhasabah

### 8.6 Memo

Menu navbar tersendiri (`Ctrl+5`) untuk menulis memo harian dan melampirkan foto.

- Navigasi tanggal sendiri (sebelumnya, hari ini, berikutnya) tanpa mengubah tanggal di halaman Hari Ini
- Editor teks dengan simpan otomatis setelah jeda singkat; teks ikut tersimpan saat pindah tanggal atau menutup jendela
- Tata letak dipusatkan dengan lebar maksimum 820 px: kartu editor dan kartu foto tidak melebar di layar besar, dengan jarak dan margin yang konsisten
- Kepala editor menampilkan jumlah karakter dan status simpan; area tulisan memakai permukaan `ih-editor-bg` yang berbeda dari latar aplikasi maupun kartu di sekelilingnya
- Galeri foto berbentuk ubin: **Tambah foto** membuka dialog berkas (boleh beberapa sekaligus), klik ubin membuka foto ukuran penuh, dan tombol hapus meminta konfirmasi. Saat belum ada foto, tampil keadaan kosong dengan ikon dan petunjuk, bukan bidang putih kosong
- Format yang diterima: JPG, PNG, WEBP, dan GIF, maksimal 25 MB per berkas. Berkas disalin ke `memo/` di folder data dengan nama unik
- Hari lampau dan hari depan boleh diisi; label halus mengingatkan konteks tanggalnya
- Kartu **Memo harian** di Hari Ini, Kalender, dan Histori Catatan menautkan ke halaman ini pada tanggal yang sesuai

### 8.7 Muhasabah

Halaman ini berisi refleksi terpandu dengan pertanyaan pemantik, berbeda dari **catatan harian** bebas di Hari Ini, Kalender, dan Histori Catatan.

- Dua kolom: daftar catatan lama (kiri), editor (kanan)
- Pertanyaan pemantik yang bisa diganti pengguna
- Pencarian teks di seluruh catatan muhasabah
- Simpan otomatis agar tulisan tidak hilang

### 8.8 Kelola Ibadah

Label navbar tetap **Kelola Ibadah**, tetapi halaman ini mengelola ibadah **dan kebiasaan** dalam satu daftar.

- Daftar kegiatan dikelompokkan menurut kategori, dengan seret untuk mengurutkan
- Tombol **Tambah ibadah** dan **Tambah kebiasaan**; yang terakhir memakai preset belajar, baca buku, olahraga, jalan kaki, dan tidur awal
- Formulir tambah dan ubah: nama, kategori, tipe isian, target, hari aktif, dan tanggal mulai aktif
- Arsipkan (bukan hapus), lalu lihat dan pulihkan lewat toggle "Tampilkan arsip"
- Hapus permanen hanya lewat konfirmasi tegas karena riwayatnya ikut hilang

### 8.9 Pengaturan

- **Tampilan**: tema **Hijau** (default), **Putih**, atau **Hitam**; area tulisan selalu memakai permukaan tersendiri yang berbeda dari latar aplikasi
- **Pengingat**: hidup atau mati, jam (HH:MM), sakelar **Popup pemberitahuan** (default aktif), baris **Izin popup**, dan tombol **Uji notifikasi**; tetap hanya berjalan saat aplikasi terbuka
- Izin popup diminta lewat dialog di dalam aplikasi hanya ketika pengguna menyalakan popup pemberitahuan, termasuk saat menyalakan pengingat dengan popup aktif. Bila ditolak, sakelar kembali mati dan pengaturan menyimpan `pengingat_izin = 0`, sehingga tidak ada popup yang dikirim tanpa izin
- **Data**: ekspor, impor dengan pratinjau (gabungkan/timpa), pilih folder cadangan, cadangkan sekarang, lokasi data, hapus semua data (termasuk berkas foto memo)
- **Tentang**: versi, lisensi, tautan repositori

---

## 9. Komponen Antarmuka

Daftar untuk memperkirakan besar pekerjaan:

1. Jendela utama dan sidebar delapan menu
2. Baris kegiatan (tiga varian: centang, angka, status) untuk ibadah maupun kebiasaan, dengan tinggi ringkas dan subtitle seperlunya
3. Kepala kelompok yang bisa dilipat
4. Kartu ringkasan dengan bilah progres dan dua tombol tambah cepat
5. Panel detail kegiatan
6. Kartu Memo harian dengan pratinjau dan tautan ke halaman Memo
7. Kalender bulanan dengan penanda status, penanda memo, penanda pengingat, dan banner izin
8. Panel detail hari terpilih di Kalender
9. Halaman Histori Catatan dengan pencarian, jumlah foto, dan pratinjau
10. Halaman Memo dengan editor autosave dan galeri foto
11. Editor muhasabah
12. Formulir ibadah/kebiasaan dengan preset kebiasaan
13. Dialog konfirmasi (hapus, hapus foto, impor yang menimpa data)
14. Dialog izin popup dan dialog pilih berkas foto
15. Toast singkat berisi tombol "Urungkan"
16. Popup notifikasi desktop lewat `Gio.Notification`
17. Halaman kosong dengan pesan ramah
18. Halaman pengenalan
19. `TrendLine` — garis tren harian, bulanan, dan tahunan (`src/ui/trend_line.py`), dengan alternatif teks dan navigasi keyboard

> **Catatan versi pustaka:** target pengembangan adalah libadwaita 1.10 (Fedora 45). Cek dokumentasi versi tersebut sebelum memakai suatu komponen, dan hindari komponen yang sudah ditandai usang.

---

## 10. Desain Visual

**Warna (sage, tenang, dan netral) — tiga tema:**

| Peran | Hijau (default) | Putih | Hitam |
|---|---|---|---|
| Latar aplikasi | `#EDF2EC` | `#F4F6F4` | `#0D0F0E` |
| Kartu | `#FFFFFF` | `#FFFFFF` | `#171A18` |
| Area tulisan | `#F9FCF9` | `#FBFCFB` | `#111412` |
| Teks | `#1C2B24` | `#1A1F1B` | `#EDF1EE` |
| Utama | `#284A3A` | `#2F5D48` | `#B4D0BF` |
| Aksen | `#466951` | `#3F6F57` | `#A6C7B3` |
| Selesai | `#356044` | `#2F6B46` | `#8FC6A3` |
| Belum | `#5D6A61` | `#5B665E` | `#AAB1AB` |
| Titik tren | `#866626` | `#866626` | `#D9B866` |

- **Hindari merah untuk status belum** karena memberi kesan bersalah. Status belum memakai abu kehijauan yang tetap memenuhi kontras 4.5:1 di ketiga tema, tanpa transparansi.
- Kontras teks terhadap latar aplikasi minimal **5.00:1** (Hijau), **5.34:1** (Putih), dan **8.78:1** (Hitam). Titik tren terhadap kartu **5.33:1**, **5.33:1**, dan **9.19:1**. Rasio dihitung dengan rumus kontras WCAG.
- **Tema Hijau dan Putih memakai skema terang; tema Hitam memakai skema gelap** lewat `Adw.StyleManager`, sehingga kontrol bawaan Adwaita tetap konsisten.
- Kartu, garis pemisah, teks pendukung, dan tombol cepat memakai variabel tambahan `ih-surface-card`, `ih-line`, `ih-muted`, dan `ih-gold` supaya tata letak konsisten di semua halaman. `ih-hover` dan `ih-selected` menyediakan umpan balik saat baris atau tombol disentuh.
- **Area tulisan berbeda dari latar aplikasi.** Memo memakai variabel `ih-editor-bg` dengan kelas `.ih-editor-surface`; warnanya sengaja tidak sama dengan `ih-surface` maupun `ih-surface-card` agar batas editor langsung terlihat.
- Aturan dan palet **Hijau** ada di `data/style.css`. `data/style-putih.css` dan `data/style-hitam.css` hanya mengganti definisi warna; `src/ui/theme.py` memasang berkas palet yang sesuai di atas stylesheet dasar. Nilai tema lama tetap dibaca: `sistem`/`terang` menjadi `hijau`, `gelap` menjadi `hitam`.
- **Palet aplikasi didahulukan di atas tema GTK pengguna.** Banyak tema pihak ketiga (mis. Graphite) menulis warna literal pada `.background` di `~/.config/gtk-4.0/gtk.css`, yang dimuat GTK pada prioritas `USER`. Karena itu provider aplikasi dipasang satu tingkat di atasnya dan permukaan utama ditulis eksplisit. Pencarian CSS juga menyertakan `XDG_DATA_HOME` dan `~/.local/share` karena instalasi `--user` tidak menambahkan folder itu ke `XDG_DATA_DIRS`.
- Penanda tetap memakai simbol dan teks (`○`, `◐`, `●`), bukan warna saja, lewat kelas `.state-kosong`, `.state-sebagian`, dan `.state-penuh`.

> **Catatan:** kontras dihitung secara statis. Penilaian visual pada layar nyata, termasuk tema sistem yang berubah saat aplikasi terbuka, masih perlu diverifikasi di sesi GNOME 51.

**Tipografi:**

- Teks umum: huruf sans-serif yang bersih
- Teks Arab: huruf Naskh dengan ukuran lebih besar dari teks Latin agar harakat terbaca
- Maksimal dua keluarga huruf

**Bentuk:** ikuti bahasa desain GNOME agar menyatu dengan sistem. Ornamen geometris islami hanya sebagai latar tipis, jangan mengganggu keterbacaan. Ikon aplikasi berbentuk kubah masjid dengan menara dan bulan sabit, memakai palet sage yang sama dan tetap berupa SVG scalable.

**Umpan balik:** animasi halus dan singkat saat mencentang. Hindari suara dan konfeti yang terasa seperti permainan untuk ibadah.

---

## 11. Interaksi dan Pintasan Keyboard

Semua fungsi harus bisa dicapai dengan keyboard, dengan penanda fokus yang jelas.

| Aksi | Pintasan |
|---|---|
| Centang ibadah terpilih | Spasi |
| Pindah antar ibadah | Panah atas / bawah |
| Hari sebelumnya / berikutnya | Ctrl+← / Ctrl+→ |
| Kembali ke hari ini | Ctrl+T |
| Riwayat harian | Ctrl+1 |
| Kalender (halaman navbar) | Ctrl+2 |
| Riwayat tahunan | Ctrl+3 |
| Histori Catatan | Ctrl+4 |
| Memo | Ctrl+5 |
| Ibadah baru | Ctrl+N |
| Kebiasaan baru | Ctrl+Shift+N |
| Cari | Ctrl+F (kontekstual: catatan harian di Histori Catatan, selain itu muhasabah) |
| Urungkan | Ctrl+Z |
| Pengaturan | Ctrl+, |
| Daftar pintasan | Ctrl+? |

Jangan menyembunyikan aksi penting hanya di balik hover. Sediakan jalur keyboard dan tombol yang selalu terlihat.

---

## 12. Pengingat

**Keputusan v1:** opsi **Sederhana + popup** (pengingat hanya muncul saat aplikasi terbuka). Opsi Lengkap ditunda.

Karena jadwal sholat tidak disediakan, pengingat memakai **jam yang dipilih pengguna**, bukan waktu sholat.

| Opsi | Keterangan |
|---|---|
| **Sederhana + popup** | Saat aplikasi terbuka: toast di dalam aplikasi dan popup notifikasi desktop bila diizinkan sistem |
| **Lengkap** | Aplikasi berjalan di latar belakang dan mengirim notifikasi walau jendela tertutup |

Pengaturan menyimpan `pengingat_aktif`, `pengingat_jam`, `pengingat_popup` (default aktif), dan `pengingat_izin` (default `0`). Jendela memeriksa jam tiap menit dan menjalankan pengingat sekali per hari:

1. Lewati pengingat bila semua kegiatan aktif hari itu sudah terlaksana **dan** memo atau fotonya sudah ada.
2. Kirim `Gio.Notification` berjudul "IslamicHabits" hanya bila popup aktif **dan** `pengingat_izin = 1`.
3. Tetap tampilkan toast di dalam aplikasi agar pengingat tidak hilang bila izin desktop ditolak.
4. Klik popup atau tombol **Buka Memo** pada toast menjalankan aksi `app.open-memo`, lalu membuka halaman Memo pada hari ini.

Izin popup diminta lewat dialog `Adw.AlertDialog` di dalam aplikasi, bukan langsung dari sistem. Dialog hanya muncul saat pengguna menyalakan popup pemberitahuan (termasuk saat menyalakan pengingat dengan popup aktif), dan menjelaskan bahwa izin dipakai untuk pengingat saja tanpa mengirim data ke server. Bila pengguna memilih **Nanti**, sakelar kembali mati dan `pengingat_izin` tetap `0`, sehingga tidak ada popup yang dikirim tanpa persetujuan. Beberapa desktop tetap dapat memblokir notifikasi lewat pengaturan sistem meskipun izin aplikasi sudah diberikan.

Tombol **Uji notifikasi** di Pengaturan mengirim satu popup contoh sekaligus toast, supaya izin notifikasi bisa diperiksa tanpa menunggu jam pengingat. Kegagalan mengirim notifikasi dibungkus `try/except` dan tidak pernah menghalangi pencatatan.

Opsi lengkap masih ditunda karena menambah kerumitan (apakah aplikasi tetap hidup setelah jendela ditutup?) dan pada Flatpak ada aturan izin tersendiri. Popup v1 **tidak** berjalan saat aplikasi tertutup.

---

## 13. Ekspor, Impor, dan Cadangan

Fitur inti, bukan pelengkap, karena tidak ada server dan data hanya ada di satu komputer.

**Keputusan v1:** format ekspor = **JSON berversi** (`islamichabits-export`, `schema_version`, metadata, array per tabel, dan bagian `photos`). Versi ekspor dan skema saat ini adalah **3**. Cadangan otomatis **mingguan** ke folder pilihan pengguna, memakai format yang sama.

- **Ekspor** semua data ke satu berkas JSON dengan penanda `islamichabits-export`, `schema_version`, metadata, dan array per tabel, termasuk `catatan_harian` dan `memo_foto`
- **Foto memo** diekspor sebagai teks base64 di kunci `photos` dengan nama berkas sebagai kuncinya, sehingga satu berkas JSON cukup untuk memindahkan memo beserta gambarnya
- **Impor** dengan pilihan gabungkan atau timpa, disertai pratinjau jumlah kegiatan, catatan kegiatan, catatan harian, foto, muhasabah, baris baru, dan kunci yang sudah ada. Impor menulis ulang berkas foto ke folder `memo/`; mode timpa menghapus berkas foto lama yang tidak ada di berkas impor
- Ekspor lama (v1 tanpa `catatan_harian`, v2 tanpa `memo_foto`) tetap diterima; tabel yang hilang dibaca sebagai array kosong sehingga catatan lokal tidak ikut terhapus
- Nama berkas foto divalidasi (harus nama polos dengan ekstensi gambar yang didukung) dan isi base64 diperiksa sebelum data ditulis, agar berkas impor tidak bisa menulis ke luar folder data
- **Cadangan otomatis** mingguan ke folder pilihan pengguna; dijalankan sekali saat aplikasi dibuka, dengan tombol "Cadangkan sekarang" sebagai pelengkap
- **Validasi** berkas impor agar berkas rusak atau versi tidak dikenal tidak merusak data yang ada
- Beri tahu pengguna secara jelas bahwa tidak ada cadangan otomatis ke luar komputer kecuali ia mengaturnya

Logika ekspor/impor berada di `src/logic/transfer.py` dan diuji tanpa GTK di `tests/test_transfer.py`.

---

## 14. Aksesibilitas

- Seluruh fungsi bisa dioperasikan dengan keyboard; pintasan penting tercantum di bagian 11
- Elemen berikon memakai `Gtk.Accessible.update_property` lewat `src/ui/a11y.py` agar terbaca pembaca layar
- Garis tren harian, bulanan, dan tahunan punya alternatif teks per titik dan navigasi keyboard (panah kiri/kanan + Enter)
- Status tidak bergantung warna saja: `○` kosong, `◐` sebagian, `●` penuh, disertai teks
- Titik tren tanpa kegiatan aktif dilewati dan dibaca sebagai "tidak ada kegiatan aktif", bukan angka nol
- Ukuran huruf mengikuti pengaturan sistem
- Area klik cukup besar dan tidak terlalu rapat; rasio kontras sage sudah dihitung (bagian 10), tetapi tetap diverifikasi secara visual pada sesi nyata
- Hari dengan memo ditandai `✎` di Kalender dan disertai teks "ada catatan harian" pada label pembaca layar, bukan sekadar ikon; hari ini dengan pengingat aktif ditandai `◷`
- Setiap ubin foto punya label pembaca layar untuk membuka dan menghapus foto; gambar yang hilang menampilkan ikon pengganti, bukan area kosong
- Baris di Histori Catatan bisa dipilih dengan panah dan dibuka dengan Enter; `Ctrl+F` langsung memfokuskan kolom cari catatan harian di halaman itu

---

## 15. Pengujian

- **Logika** (statistik, hari aktif, kebiasaan, memo harian, foto, ekspor/impor, cadangan) dan smoke test konstruksi UI diuji tanpa jendela: **83 pengujian lolos** dengan `python3 -m unittest discover -s tests -q`
- **Versi skema** divalidasi, termasuk migrasi v1 → v2 → v3 (tabel `catatan_harian` dan `memo_foto`) serta seed kebiasaan bawaan pada basis data lama tanpa menghapus data
- **Deret tren** diuji untuk 30 hari, per hari dalam bulan, dan per bulan dalam tahun, memakai `aktif_mulai` sebagai denominator
- **Ekspor/impor** diuji untuk tabel baru, foto base64, penolakan nama berkas tidak aman, pratinjau, serta kompatibilitas berkas v1 yang tidak memiliki `catatan_harian` dan v2 yang tidak memiliki `memo_foto`
- **Kontras palet** diuji dari berkas CSS dengan rumus WCAG; status kosong tidak memakai transparansi yang menurunkan kontras
- **Smoke test UI** mencakup penyimpanan memo, kartu Memo harian yang menautkan ke halaman Memo, galeri foto, Kalender dengan banner pengingat, Histori Catatan yang hanya memuat memo harian, kelima kebiasaan bawaan di Hari Ini, tiga mode Riwayat, dan klik tren tahunan yang membuka Kalender
- **Kasus tepi:**
  - Pergantian tengah malam saat aplikasi terbuka
  - Mengisi hari lampau dan hari depan
  - Menghapus ibadah yang punya riwayat
  - Impor berkas rusak atau berversi tidak dikenal
  - Foto hilang dari folder data dan impor foto dengan nama/isi tidak valid
  - Jendela sangat kecil
  - Data kosong dan data sangat banyak
- **Uji manual** pada lingkungan target (Fedora 45, GNOME 51): tiga tema (Hijau, Putih, Hitam), perbedaan latar area tulisan Memo, popup notifikasi dan tombol Uji notifikasi, serta, bila memungkinkan, distribusi atau versi GNOME lain bila aplikasi akan dibagikan

---

## 16. Pengemasan dan Distribusi

| Format | Kegunaan |
|---|---|
| **Installer satu perintah** | `curl ... \| bash` dari Releases; tanpa `sudo`, verifikasi checksum, pasang ke `~/.local` |
| **Flatpak** | Jalur mandiri yang disarankan untuk aplikasi GNOME; dapat dibagikan sebagai bundle di GitHub Releases |
| **Sumber (Meson)** | Pengembangan dan instalasi lokal |
| **AppImage** | Satu berkas yang juga dipakai installer di atas |

Lisensi sudah ditetapkan: **GPL-3.0-or-later** (berkas `LICENSE`). `.gitignore` menyembunyikan data pengguna dan berkas build. Menerbitkan ke Flathub adalah langkah terpisah dan tidak wajib karena distribusi lewat GitHub Releases.

Cara memasang, menjalankan, memperbarui, dan mencopot aplikasi, serta lokasi data dan langkah pertama setelah instalasi, ada di [`INSTALL.md`](INSTALL.md). Panduan bagi pembuat paket rilis ada di [`packaging/RELEASE.md`](packaging/RELEASE.md).

---

## 17. Rencana Pengerjaan

- [x] 1. Tetapkan nama (`IslamicHabits`), ID (`io.github.kurakura.IslamicHabits`), lisensi (GPL-3.0-or-later), format ekspor JSON, dan target v1 = Fedora 45
- [x] 2. Siapkan lingkungan pengembangan dan jendela kosong (`Adw.Application` + `Adw.StatusPage`), plus `meson.build`, desktop entry, metadata AppStream, dan ikon
- [x] 3. Bangun lapisan data dan skema, disertai pengujian
- [x] 4. Jendela utama dan navigasi
- [x] 5. Halaman **Hari Ini** dengan tiga jenis baris kegiatan dan tombol tambah cepat
- [x] 6. **Kelola Ibadah** untuk ibadah dan kebiasaan dalam satu daftar
- [x] 7. **Riwayat** harian/bulanan/tahunan, **Kalender** terpisah di navbar, dan **Histori Catatan**
- [x] 8. **Catatan harian** dan **Muhasabah**
- [x] 9. Statistik harian / bulanan / tahunan (satu garis tren generik)
- [x] 10. **Ekspor, impor, dan cadangan** (skema v2 → v3, kompatibel dengan v1/v2)
- [x] 11. Pengaturan, tiga tema (Hijau, Putih, Hitam), pengingat dengan popup dan izin
- [x] 12. Pengenalan, aksesibilitas, pemolesan
- [x] 13. Pengemasan dan rilis `v0.1.0` di GitHub
- [x] 14. Kebiasaan umum dalam tabel yang sama dengan ibadah, preset, dan seed migrasi
- [x] 15. Tren bulanan per hari, kartu visual, dan sinkronisasi versi `0.2.0`
- [x] 16. Halaman **Memo** dengan lampiran foto, kartu Memo harian, izin popup, dan baris daftar yang lebih ringkas (skema v3)
- [x] 17. Rilis `v0.3.0` dengan Memo, foto, izin popup, dan format ekspor v3
- [x] 18. Rilis patch `v0.3.1`: pemulihan tiga tema, pencarian stylesheet instalasi `--user`, tata letak Memo, dan launcher absolut

**Status akhir:** seluruh langkah 1–18 selesai. 83 pengujian (logika/data, kontras CSS, dan smoke test UI headless) lolos, dan instalasi Meson berhasil. Navbar delapan menu, Kalender terpisah, Histori Catatan, Memo dengan foto, tiga tema, dan ikon kubah masjid sudah terpasang. Rilis `v0.1.0`, `v0.2.0`, dan `v0.3.0` sudah hidup; `v0.3.1` memperbaiki pemuatan tema, launcher desktop, dan tata letak Memo. Uji visual tiga tema, halaman Memo, serta penerimaan popup di sesi GNOME 51 nyata masih disarankan sebelum menandai rilis publik sebagai final.

---

## 18. Keputusan yang Masih Terbuka

- [x] Nama, ID, lisensi, format ekspor, dan target v1 sudah diputuskan (lihat bagian 3, 5, 12, 13, 17)
- [x] Kebiasaan memakai tabel `ibadah` yang sama dengan kategori **Kebiasaan**, bukan tabel atau halaman data terpisah
- [x] Bulanan di Riwayat adalah tren per hari, sedangkan Kalender tetap halaman navbar tersendiri
- [ ] Apakah heatmap 365 hari ditambahkan setelah v1 (v1 memakai garis saja)
- [ ] Dukungan distro/versi GNOME lain setelah v1
- [ ] Apakah ibadah berbasis tanggal Hijriah masuk, dan dengan sumber apa
- [ ] Pengingat versi latar belakang (v1: hanya saat aplikasi terbuka)
- [ ] Kapan (dan apakah) jadwal waktu sholat dipertimbangkan kembali
- [ ] Verifikasi sumber untuk teks bawaan muhasabah/dzikir sebelum rilis publik

---

## 19. Risiko yang Diketahui

1. **Versi sangat baru.** Fedora 45 baru dirilis 3 November 2026 dengan Python 3.15 dan libadwaita 1.10. Dokumentasi, contoh kode, dan tutorial di internet banyak yang masih untuk versi lama, jadi sebagian contoh bisa tidak cocok atau memakai komponen usang. Selalu cocokkan dengan dokumentasi versi yang dipakai. Kerangka awal sudah lolos uji di Python 3.15.2 / GTK 4.24, termasuk pemakaian `set_draw_func` (bukan sinyal `draw` ala GTK3).
2. **Lingkungan pengembangan.** Pengembangan GTK4 lewat Python bergantung pada banyak paket sistem, lebih rumit daripada proyek web. Siapkan dan uji lebih dulu.
3. **Kehilangan data.** Tanpa server tidak ada cadangan ke luar komputer. Cadangan mingguan dan ekspor manual sudah tersedia, tetapi pengguna tetap perlu memilih folder cadangan atau menyimpan salinan di tempat lain.
4. **Ruang lingkup.** Rencana ini cukup besar untuk satu pengembang. Disiplin pada urutan pengerjaan dan selesaikan inti sebelum menambah fitur.
5. **Kontras dan tema sistem.** Palet sage sudah memenuhi 4.5:1 secara statis di kedua tema, tetapi perubahan skema sistem saat aplikasi terbuka, kalibrasi layar, dan pembaca layar tetap perlu dicek secara visual di GNOME 51.
6. **Izin notifikasi.** Popup memakai `Gio.Notification` dan dapat ditolak oleh pengaturan notifikasi GNOME atau Flatpak. Toast di dalam aplikasi sengaja dipertahankan sebagai cadangan, dan tombol Uji notifikasi disediakan untuk memeriksa izin.
7. **Akurasi isi keagamaan.** Teks bawaan seperti daftar ibadah, pertanyaan muhasabah, atau dzikir sebaiknya diverifikasi pada sumber yang dipercaya sebelum dipublikasikan.

---

## Lisensi

GPL-3.0-or-later. Teks lengkap ada di berkas [`LICENSE`](LICENSE).
