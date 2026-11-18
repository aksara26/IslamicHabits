# Catatan pengemasan rilis

Semua perintah dijalankan dari folder proyek. Untuk cara memasang paket oleh
pengguna, lihat [`INSTALL.md`](../INSTALL.md).

## 1. Pastikan versi sudah tepat

Ubah `APP_VERSION` di `src/logic/constants.py`, `version` di `meson.build`, dan
atribut `version` pada elemen `<release>` di
`data/io.github.kurakura.IslamicHabits.metainfo.xml` dengan nomor yang sama.
Jalankan tes sebelum melanjutkan:

```bash
python3 -m unittest discover -s tests -q
meson setup builddir
meson test -C builddir
```

Rilis **v0.3.0** menaikkan skema dan format ekspor ke **v3**. Tabel baru
`memo_foto` menyimpan metadata foto memo, sedangkan berkas gambarnya berada di
folder `memo/` dalam folder data. Migrasi v2 → v3 berjalan otomatis saat
aplikasi dibuka, dan impor tetap menerima berkas ekspor v1/v2. Catatan rilis
v0.3.0 harus menyebutkan:

- halaman **Memo** (`Ctrl+5`) dengan editor autosave dan galeri foto; kartu Memo harian di Hari Ini, Kalender, dan Histori Catatan menautkan ke halaman ini;
- foto memo disimpan sebagai berkas di `memo/`, diekspor sebagai base64 di kunci `photos`, dan ikut dibersihkan oleh **Hapus semua data**;
- izin popup disimpan di `pengingat_izin` dan diminta lewat dialog dalam aplikasi sebelum `Gio.Notification` dikirim; aksi popup membuka Memo hari ini;
- baris daftar dipadatkan (±37 px tanpa subtitle, ±49 px dengan subtitle) dan subtitle hanya menampilkan target, jam, atau catatan;
- navbar menjadi delapan menu: **Hari Ini**, **Riwayat**, **Kalender**, **Histori Catatan**, **Memo**, **Muhasabah**, **Kelola Ibadah**, dan **Pengaturan**.

Sertakan pula catatan bahwa popup pengingat memerlukan izin notifikasi sistem,
sementara toast dalam aplikasi tetap menjadi cadangan. Workflow mengunggah
`install.sh`, `SHA256SUMS`, dan ikon SVG supaya pengguna bisa memasang atau
memperbarui hanya dengan satu perintah `curl ... | bash` tanpa `sudo`.

Rilis **v0.4.0** adalah rilis minor audit antarmuka; skema dan format ekspor
tetap **v3**, jadi tidak ada migrasi basis data. Catatan rilis v0.4.0 harus
menyebutkan:

- navbar menjadi **tujuh menu**: Hari Ini, Riwayat, Kalender, Memo, Muhasabah,
  Kelola Ibadah, dan Pengaturan. Histori Catatan tidak lagi menjadi halaman
  navbar, tetapi kelas `NoteHistoryPage` dipertahankan agar kompatibel;
- **Memo sebelumnya** menjadi dialog berikon `document-open-recent-symbolic`
  dari halaman Memo, lengkap dengan pencarian, cuplikan teks, dan jumlah foto;
- **pencarian global** (`Ctrl+F`) di bilah judul mencari memo, muhasabah,
  catatan ibadah, dan nama ibadah, lalu membuka halaman yang tepat;
- navigasi tanggal bersama dengan kalender popover dipakai Hari Ini, Memo, dan
  Muhasabah; `Ctrl+4` kini membuka Muhasabah dan `Ctrl+S` menyimpan memo;
- Kalender memakai dua panel, Kelola Ibadah memakai menu `⋮` dan mode
  **Urutkan**, Riwayat memadatkan kontrolnya, dan **Hapus semua data** meminta
  konfirmasi dengan mengetik `HAPUS` serta menawarkan ekspor lebih dulu.

Rilis **v0.5.0** menaikkan skema dan format ekspor ke **v4**. Tabel baru
`pengingat_harian` menyimpan teks, jam `HH:MM`, dan status terkirim untuk satu
pengingat per tanggal. Migrasi v3 → v4 berjalan otomatis, dan impor tetap
menerima berkas ekspor v1/v2/v3. Catatan rilis v0.5.0 harus menyebutkan:

- tombol **Kalender** di halaman Memo membuka dialog **Kalender Memo** dengan
  grid bulan, penanda `✎` memo dan `◷` pengingat, ringkasan checklist,
  pratinjau memo, dan tombol **Buka memo tanggal ini**;
- **pengingat per tanggal** terpisah dari memo, punya jam sendiri, dan boleh
  dibuat untuk tanggal lampau, hari ini, atau masa depan;
- pengingat hari ini memicu toast dan popup desktop saat jamnya tiba bila
  popup diizinkan; status `terkirim` mencegah pengulangan, dan menyimpan ulang
  teks/jam mengaktifkannya kembali;
- teks pengingat ikut **pencarian global** dan hasilnya membuka halaman Memo
  pada tanggal tersebut;
- ekspor/impor mencakup `pengingat_harian`, sementara berkas lama tanpa tabel
  itu tetap diterima.

### Riwayat rilis

- **v0.5.0**: dialog Kalender Memo dan pengingat per tanggal berjam; skema serta ekspor v4.
- **v0.4.0**: audit UX menyeluruh; navbar tujuh menu, pencarian global, dialog Memo sebelumnya, navigasi tanggal bersama, Kalender dua panel, menu aksi Kelola Ibadah, dan konfirmasi hapus dua langkah.
- **v0.3.1**: perbaikan pemuatan tiga tema (Hijau, Putih, Hitam) pada instalasi `--user`, tata letak Memo yang lebih rapi dengan area tulisan berbeda, dan launcher desktop berjalur absolut.
- **v0.2.0**: ibadah dan kebiasaan umum memakai satu tabel dan satu statistik; preset kebiasaan; tren garis harian, bulanan, dan tahunan; navbar tujuh menu.
- **v0.1.0**: versi pertama dengan pencatatan harian, kelola ibadah, riwayat, kalender, histori catatan, muhasabah, pengaturan, serta ekspor/impor/cadangan.

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

1. Buat tag `v0.5.0` (sesuaikan nomor versi) dan push ke GitHub.
2. Workflow `.github/workflows/build.yml` menjalankan tes (termasuk `bash -n
   packaging/install.sh`), membangun AppImage, lalu melampirkan AppImage,
   `install.sh`, `SHA256SUMS`, dan ikon SVG ke rilis tag.
3. Unggah pula `IslamicHabits.flatpak` bila sudah dibangun.
4. Tulis catatan rilis singkat: fitur, perbaikan, perintah pemasangan satu baris,
   dan tautan ke [`INSTALL.md`](../INSTALL.md) untuk cara instalasi.

Menerbitkan ke Flathub adalah langkah terpisah dan tidak wajib.
