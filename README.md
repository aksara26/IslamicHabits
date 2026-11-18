# IslamicHabits

Aplikasi desktop Linux untuk mencatat ibadah harian secara pribadi. Dibuat untuk penggunaan sendiri, data tersimpan lokal, tanpa akun, tanpa server, dan didistribusikan lewat GitHub.

> **Status:** tahap implementasi awal. Keputusan desain sudah dikunci. Lapisan data SQLite, jendela utama dengan navigasi, halaman **Hari Ini**, dan **Kelola Ibadah** sudah berjalan. Halaman Riwayat, Muhasabah, Pengaturan, pengenalan, ekspor/impor, dan pengemasan masih berupa placeholder atau belum dibuat.

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

Aplikasi ini membantu pengguna mencatat dan merefleksikan ibadah hariannya (sholat, tilawah, puasa sunnah, dzikir, dan lainnya) dengan cepat dan tenang.

**Prinsip desain:**

1. **Berbasis kesadaran pengguna.** Semua isian dilakukan sendiri oleh pengguna. Aplikasi adalah alat bantu mengingat dan bercermin, bukan pengawas.
2. **Cepat.** Mencatat satu ibadah cukup satu klik atau satu tombol. Target seluruh pencatatan harian kurang dari 10 detik.
3. **Tenang.** Tidak ada kalimat menghukum ("gagal", "streak putus"), tidak ada warna merah untuk status belum, tidak ada peringkat atau perbandingan.
4. **Privat dan lokal.** Data hanya ada di komputer pengguna. Tidak ada akun, tidak ada jaringan.
5. **Mudah dikoreksi.** Salah centang, lupa mengisi kemarin, atau salah hapus harus bisa diperbaiki.
6. **Hari ini dulu.** Halaman utama hanya menjawab satu pertanyaan: apa yang sudah dan belum hari ini.

---

## 2. Cakupan

### Termasuk (versi pertama)

- Pencatatan ibadah harian: centang, angka, dan status
- Kategori dan pengelolaan ibadah (tambah, ubah, urutkan, arsipkan)
- Riwayat dalam kalender bulanan dan pengisian hari lampau
- Statistik sederhana per ibadah
- Catatan muhasabah harian
- Ekspor, impor, dan cadangan data
- Tema terang dan gelap
- Pengingat berdasarkan jam yang dipilih pengguna

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
| Pengemasan | Flatpak (utama), AppImage (opsional) | Lihat bagian 16 |
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
sudo dnf install meson ninja-build python3 python3-gobject gtk4 libadwaita \
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
├── README.md
├── LICENSE                 # GPL-3.0-or-later
├── .gitignore              # data pengguna & build tidak masuk git
├── meson.build             # build + install
├── data/
│   ├── io.github.kurakura.IslamicHabits.desktop
│   ├── io.github.kurakura.IslamicHabits.metainfo.xml
│   └── icons/hicolor/scalable/apps/io.github.kurakura.IslamicHabits.svg
├── src/
│   ├── __init__.py
│   ├── islamichabits       # launcher setelah terpasang
│   ├── main.py             # Adw.Application + pembukaan basis data
│   ├── logic/
│   │   ├── __init__.py
│   │   ├── constants.py    # APP_NAME, APP_ID, versi skema/ekspor
│   │   ├── defaults.py     # ibadah bawaan saat basis data dibuat
│   │   ├── statistics.py   # aturan harian/bulanan/tahunan, murni Python
│   │   ├── database.py     # koneksi SQLite, skema, migrasi
│   │   └── repository.py   # CRUD tanpa GTK
│   └── ui/
│       ├── __init__.py
│       ├── main_window.py  # navigasi adaptif + aksi/pintasan
│       ├── today_page.py   # halaman Hari Ini
│       ├── worship_row.py  # tiga varian baris ibadah
│       ├── worship_dialog.py
│       ├── manage_page.py  # Kelola Ibadah
│       └── trend_line.py   # Gtk.DrawingArea + Cairo
├── tests/
│   ├── test_statistics.py
│   ├── test_database.py
│   └── test_repository.py
└── packaging/              # belum dibuat: Flatpak, AppImage
```

### Lokasi penyimpanan data

Data disimpan di folder data pengguna standar Linux. Pada Flatpak lokasinya berbeda (di bawah `~/.var/app/<id-aplikasi>/`). Karena itu aplikasi **harus mengambil lokasi dari sistem**, tidak boleh memakai jalur tetap.

### Identitas aplikasi

Tetapkan di awal karena mengubahnya belakangan memengaruhi desktop entry, identitas Flatpak, skema pengaturan, dan data pengguna:

- **Nama tampilan:** IslamicHabits
- **ID aplikasi:** `io.github.kurakura.IslamicHabits`
- **Lisensi:** GPL-3.0-or-later (berkas `LICENSE`)
- Ikon SVG dan desktop entry sudah dibuat; tetap periksa keterbacaan ikon pada ukuran kecil
- Kategori dan deskripsi singkat untuk peluncur aplikasi sudah ada di desktop entry

---

## 5. Model Data

| Tabel | Isi |
|---|---|
| **kategori** | nama, urutan, status lipat |
| **ibadah** | nama, kategori, tipe isian (centang / angka / status), target, satuan, hari aktif, **`aktif_mulai`**, urutan, status arsip |
| **catatan** | ibadah, tanggal, nilai atau status, jam pelaksanaan (opsional), catatan teks |
| **muhasabah** | tanggal, teks, jawaban pertanyaan pemantik |
| **pengaturan** | tema, jam pengingat, preferensi tampilan |
| **meta** | nomor versi skema |

**Aturan data:**

- **Satu catatan per ibadah per tanggal.**
- Statistik **dihitung dari catatan**, tidak disimpan sebagai angka mati. Dengan begitu koreksi data masa lalu tidak merusak hitungan.
- Ibadah yang dihapus menjadi **arsip**, bukan dihapus fisik, agar riwayat utuh.
- Tanggal disimpan sebagai tanggal lokal murni (tahun-bulan-hari), tanpa jam.
- Nomor versi skema disimpan agar pembaruan aplikasi bisa memigrasi data lama.
- `aktif_mulai` dipakai sebagai denominator statistik. Ibadah baru tidak dihitung pada tanggal sebelum ia ditambahkan, agar riwayat lama tidak terasa menghukum.
- Ibadah arsip tetap disimpan dan boleh ikut statistik lewat toggle "Tampilkan arsip".

### Definisi "terlaksana"

| Tipe | Terlaksana | Catatan |
|---|---|---|
| Centang | nilainya `True` | Ulangi klik untuk membatalkan |
| Angka | `nilai >= target` | Target kosong/0 → cukup `nilai > 0`; yang belum capai target disebut **sebagian** |
| Status | semua kecuali `belum` | `qadha` tetap terhitung sebagai catatan jujur |

Penanda harian: **kosong** (tidak ada catatan), **sebagian** (ada catatan tapi belum lengkap), **penuh** (semua ibadah aktif terlaksana). Statistik tidak memakai kata "gagal" dan tidak menampilkan streak.

### Daftar ibadah bawaan (bisa diubah pengguna)

| Kategori | Contoh |
|---|---|
| Sholat fardhu | Subuh, Dzuhur, Ashar, Maghrib, Isya |
| Sholat sunnah | Rawatib, dhuha, tahajud, witir |
| Al-Qur'an | Tilawah (halaman), hafalan, muraja'ah |
| Dzikir | Pagi, petang, setelah sholat |
| Puasa sunnah | Senin-Kamis |
| Amal | Sedekah, silaturahmi |
| Pribadi | Kebiasaan buatan sendiri |

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
- **Sidebar kiri**: navigasi antar halaman, bisa dilipat
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
                       ┌────────────┬───────────┬───────┴──────┐    │
                       ▼            ▼           ▼              ▼    │
                    RIWAYAT    MUHASABAH   KELOLA IBADAH   PENGATURAN│
                       │                        │              │    │
                  Detail hari            Form ibadah     Ekspor/Impor ┘
```

### Alur pengguna utama

1. **Pertama kali:** pengenalan, pilih ibadah awal, masuk ke Hari Ini.
2. **Harian:** buka aplikasi, centang ibadah, selesai.
3. **Malam:** lengkapi yang tertinggal, tulis muhasabah bila mau.
4. **Berkala:** buka Riwayat untuk melihat gambaran, lakukan cadangan.

---

## 8. Rincian Tiap Halaman

### 8.1 Pengenalan (sekali saja)

- Sambutan singkat dan penjelasan prinsip: pencatatan jujur oleh diri sendiri, data lokal, tanpa akun
- Pilih ibadah awal dari daftar bawaan
- Tidak meminta data pribadi, kecuali nama panggilan (opsional)
- Selesai langsung menuju Hari Ini

### 8.2 Hari Ini (halaman utama)

**Tujuan:** menjawab "apa yang sudah dan belum hari ini" secepat mungkin.

**Komponen:**

- Header tanggal dengan tombol hari sebelumnya, berikutnya, dan kembali ke hari ini
- Ringkasan progres berupa kalimat netral dan bilah halus
- Daftar ibadah dikelompokkan per kategori, tiap kelompok bisa dilipat

**Perilaku per jenis baris:**

- **Centang**: klik atau Spasi menandai selesai, ulangi untuk membatalkan
- **Angka**: tombol kurang dan tambah, atau ketik langsung
- **Status**: klik membuka pilihan kecil (belum, tepat waktu, terlambat, berjamaah, qadha)
- **Aksi sekunder** (detail, catatan): muncul saat kursor di atas baris, dan selalu tersedia lewat keyboard

**Panel detail ibadah:** panel samping atau jendela kecil berisi status, jam pelaksanaan (opsional, boleh kosong), dan catatan. Tidak berpindah halaman agar konteks tidak hilang.

**Kondisi khusus:**

| Kondisi | Perilaku |
|---|---|
| Tidak ada ibadah aktif | Pesan ramah dan tombol tambah |
| Hari lampau | Tampil sama, dengan penanda lembut bahwa sedang mengisi hari lampau |
| Hari depan | Boleh dilihat, pencatatan dibatasi |
| Pergantian hari saat aplikasi terbuka | Tawarkan beralih ke hari baru, jangan mengubah tampilan tiba-tiba |

### 8.3 Riwayat

Halaman ini punya switcher **Harian / Bulanan / Tahunan** (`Ctrl+1` / `Ctrl+2` / `Ctrl+3`).

- **Harian**: rekap satu tanggal; penanda kosong/sebagian/penuh **tidak bergantung warna saja**. Klik tanggal untuk melihat atau mengisi mundur.
- **Bulanan**: kalender besar + ringkasan per ibadah, mis. "Tilawah: 18 dari 30 hari aktif".
- **Tahunan**: **garis tren 12 titik (Jan–Des)** — bukan batang, bukan heatmap. Titik yang tidak punya ibadah aktif sengaja putus, bukan angka 0. Klik titik/bulan untuk masuk ke Bulanan, lalu klik tanggal untuk masuk ke Harian.
- Filter per ibadah atau kategori, dengan toggle "Tampilkan arsip".
- Bahasa netral: "Terlaksana 18 dari 30 hari", bukan "gagal".
- Alternatif teks 12 bulan dan navigasi panah kiri/kanan + Enter disediakan untuk garis tahunan.

### 8.4 Muhasabah

- Dua kolom: daftar catatan lama (kiri), editor (kanan)
- Pertanyaan pemantik yang bisa diganti pengguna
- Pencarian teks di seluruh catatan
- Simpan otomatis agar tulisan tidak hilang

### 8.5 Kelola Ibadah

- Daftar ibadah dengan seret untuk mengurutkan
- Formulir tambah dan ubah: nama, kategori, tipe isian, target, hari aktif
- Arsipkan (bukan hapus), dengan halaman terpisah untuk melihat dan memulihkan arsip
- Hapus permanen hanya lewat konfirmasi tegas karena riwayatnya ikut hilang

### 8.6 Pengaturan

- **Tampilan**: terang, gelap, atau ikut sistem
- **Pengingat**: hidup atau mati, dan jam
- **Data**: ekspor, impor, lokasi data, hapus semua data
- **Tentang**: versi, lisensi, tautan repositori

---

## 9. Komponen Antarmuka

Daftar untuk memperkirakan besar pekerjaan:

1. Jendela utama dan sidebar navigasi
2. Baris ibadah (tiga varian: centang, angka, status)
3. Kepala kelompok yang bisa dilipat
4. Panel detail ibadah
5. Kalender bulanan dengan penanda
6. Kartu statistik
7. Editor muhasabah
8. Formulir ibadah
9. Dialog konfirmasi (hapus, impor yang menimpa data)
10. Notifikasi singkat berisi tombol "Urungkan"
11. Halaman kosong dengan pesan ramah
12. Halaman pengenalan
13. `TrendLine` — garis tren tahunan (`src/ui/trend_line.py`), dengan alternatif teks dan navigasi keyboard

> **Catatan versi pustaka:** target pengembangan adalah libadwaita 1.10 (Fedora 45). Cek dokumentasi versi tersebut sebelum memakai suatu komponen, dan hindari komponen yang sudah ditandai usang.

---

## 10. Desain Visual

**Warna (usulan, sesuaikan selera):**

| Peran | Warna | Hex |
|---|---|---|
| Utama | Hijau tua | `#1F5C4A` |
| Aksen | Emas lembut | `#C9A24B` |
| Latar terang | Krem | `#FAF6EC` |
| Teks terang | Hijau kehitaman | `#14231E` |
| Latar gelap | Hijau sangat gelap | `#0E1A16` |
| Selesai | Hijau cerah | `#3E9B6E` |
| Belum | Abu hangat | `#B9B3A4` |

- Hindari merah untuk status belum karena memberi kesan bersalah.
- **Emas di atas krem berkontras rendah.** Pakai emas untuk ornamen dan ikon, bukan teks kecil.
- Sediakan mode terang dan gelap, dan hormati pengaturan sistem.

**Tipografi:**

- Teks umum: huruf sans-serif yang bersih
- Teks Arab: huruf Naskh dengan ukuran lebih besar dari teks Latin agar harakat terbaca
- Maksimal dua keluarga huruf

**Bentuk:** ikuti bahasa desain GNOME agar menyatu dengan sistem. Ornamen geometris islami hanya sebagai latar tipis, jangan mengganggu keterbacaan.

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
| Riwayat bulanan | Ctrl+2 |
| Riwayat tahunan | Ctrl+3 |
| Ibadah baru | Ctrl+N |
| Cari | Ctrl+F |
| Urungkan | Ctrl+Z |
| Pengaturan | Ctrl+, |
| Daftar pintasan | Ctrl+? |

Jangan menyembunyikan aksi penting hanya di balik hover. Sediakan jalur keyboard dan tombol yang selalu terlihat.

---

## 12. Pengingat

**Keputusan v1:** mulai dari opsi **Sederhana** (pengingat hanya muncul saat aplikasi terbuka). Opsi Lengkap ditunda.

Karena jadwal sholat tidak disediakan, pengingat memakai **jam yang dipilih pengguna**, bukan waktu sholat.

| Opsi | Keterangan |
|---|---|
| **Sederhana** | Pengingat hanya muncul saat aplikasi terbuka |
| **Lengkap** | Aplikasi berjalan di latar belakang dan mengirim notifikasi desktop |

Mulai dari opsi sederhana. Opsi lengkap menambah kerumitan (apakah aplikasi tetap hidup setelah jendela ditutup?) dan pada Flatpak ada aturan izin tersendiri. **Baca dokumentasi resmi sebelum merancang bagian ini.**

---

## 13. Ekspor, Impor, dan Cadangan

Fitur inti, bukan pelengkap, karena tidak ada server dan data hanya ada di satu komputer.

**Keputusan v1:** format ekspor = **JSON berversi** (`islamichabits-export`, `schema_version`, metadata, array per tabel). Cadangan otomatis **mingguan** ke folder pilihan pengguna, memakai format yang sama.

- **Ekspor** semua data ke satu berkas dengan struktur jelas dan berversi
- **Impor** dengan pilihan gabungkan atau timpa, disertai pratinjau jumlah catatan
- **Cadangan otomatis** berkala ke folder pilihan pengguna
- **Validasi** berkas impor agar berkas rusak tidak merusak data yang ada
- Beri tahu pengguna secara jelas bahwa tidak ada cadangan otomatis ke luar komputer kecuali ia mengaturnya

---

## 14. Aksesibilitas

- Seluruh fungsi bisa dioperasikan dengan keyboard
- Elemen punya label yang terbaca pembaca layar
- Kontras warna diuji, terutama emas di atas krem
- Status tidak bergantung warna saja (tambahkan ikon atau teks)
- Ukuran huruf mengikuti pengaturan sistem
- Area klik cukup besar dan tidak terlalu rapat

---

## 15. Pengujian

- **Logika** (statistik, hari aktif, ekspor dan impor) diuji tanpa antarmuka
- **Migrasi skema** diuji dengan data versi lama
- **Kasus tepi:**
  - Pergantian tengah malam saat aplikasi terbuka
  - Mengisi hari lampau dan hari depan
  - Menghapus ibadah yang punya riwayat
  - Impor berkas rusak atau berversi tidak dikenal
  - Jendela sangat kecil
  - Data kosong dan data sangat banyak
- **Uji manual** pada lingkungan target (Fedora 45, GNOME 51) dan, bila memungkinkan, distribusi atau versi GNOME lain bila aplikasi akan dibagikan

---

## 16. Pengemasan dan Distribusi

| Format | Kegunaan |
|---|---|
| **Instalasi dari sumber (Meson)** | Tahap awal dan pengembangan |
| **Flatpak** | Jalur utama yang disarankan untuk aplikasi GNOME; dapat dibagikan sebagai berkas bundle di GitHub Releases |
| **AppImage** | Opsional, satu berkas yang langsung dijalankan |

**Rencana rilis di GitHub:**

- Kode di repositori, paket di halaman Releases
- Penomoran versi dan catatan rilis pada tiap rilis
- README (dokumen ini) berisi cara instal untuk tiap format
- Lisensi dipilih sebelum rilis publik

Lisensi sudah ditetapkan: **GPL-3.0-or-later** (berkas `LICENSE`). Repositori juga sudah diinisialisasi dengan git; `.gitignore` menyembunyikan data pengguna dan berkas build. Metadata AppStream saat ini masih memberi satu peringatan karena URL repositori GitHub belum reachable; peringatan akan hilang setelah repositori publik dibuat.

Menerbitkan ke Flathub adalah langkah terpisah dengan aturannya sendiri dan tidak wajib karena distribusi lewat GitHub.

---

## 17. Rencana Pengerjaan

- [x] 1. Tetapkan nama (`IslamicHabits`), ID (`io.github.kurakura.IslamicHabits`), lisensi (GPL-3.0-or-later), format ekspor JSON, dan target v1 = Fedora 45
- [x] 2. Siapkan lingkungan pengembangan dan jendela kosong (`Adw.Application` + `Adw.StatusPage`), plus `meson.build`, desktop entry, metadata AppStream, dan ikon
- [x] 3. Bangun lapisan data dan skema, disertai pengujian
- [x] 4. Jendela utama dan navigasi
- [x] 5. Halaman **Hari Ini** dengan tiga jenis baris ibadah
- [x] 6. **Kelola Ibadah**
- [ ] 7. **Riwayat** dan kalender
- [ ] 8. **Muhasabah**
- [ ] 9. Statistik harian / bulanan / tahunan (garis tren) — logika dasar sudah ada di `src/logic/statistics.py`
- [ ] 10. **Ekspor, impor, dan cadangan**
- [ ] 11. Pengaturan, tema, pengingat sederhana
- [ ] 12. Pengenalan, aksesibilitas, pemolesan
- [ ] 13. Pengemasan dan rilis di GitHub

**Rekomendasi:** langkah 3–6 sudah selesai. Pakai aplikasi beberapa hari lebih dulu, lalu lanjutkan ke langkah 7.

Catatan: 30 pengujian logika/data lolos, pembuatan objek UI lolos secara headless, dan instalasi Meson berhasil. Uji visual di sesi GNOME 51 nyata masih perlu dilakukan sebelum melanjutkan halaman berikutnya.

---

## 18. Keputusan yang Masih Terbuka

- [x] Nama, ID, lisensi, format ekspor, dan target v1 sudah diputuskan (lihat bagian 3, 5, 12, 13, 17)
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
3. **Kehilangan data.** Tanpa server tidak ada cadangan otomatis. Ekspor dan cadangan wajib ada sejak versi pertama.
4. **Ruang lingkup.** Rencana ini cukup besar untuk satu pengembang. Disiplin pada urutan pengerjaan dan selesaikan inti sebelum menambah fitur.
5. **Kontras warna.** Kombinasi emas dan krem rawan sulit dibaca. Uji sebelum dipakai untuk teks.
6. **Akurasi isi keagamaan.** Teks bawaan seperti daftar ibadah, pertanyaan muhasabah, atau dzikir sebaiknya diverifikasi pada sumber yang dipercaya sebelum dipublikasikan.

---

## Lisensi

GPL-3.0-or-later. Teks lengkap ada di berkas [`LICENSE`](LICENSE).
