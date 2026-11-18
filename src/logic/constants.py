"""Identitas dan konstanta bersama IslamicHabits."""

APP_NAME = "IslamicHabits"
APP_ID = "io.github.kurakura.IslamicHabits"
LICENSE = "GPL-3.0-or-later"

# Format berkas ekspor berversi. Diimpor/dievaluasi oleh lapisan data nanti.
EXPORT_FORMAT = "islamichabits-export"
SCHEMA_VERSION = 4
EXPORT_VERSION = 4

# Cadangan otomatis: mingguan, ke folder yang dipilih pengguna.
BACKUP_INTERVAL_DAYS = 7

# Kunci pengaturan dan meta. Disimpan sebagai teks di tabel masing-masing.
SETTING_THEME = "tema"
SETTING_REMINDER_ENABLED = "pengingat_aktif"
SETTING_REMINDER_TIME = "pengingat_jam"
SETTING_REMINDER_POPUP = "pengingat_popup"
SETTING_REMINDER_PERMISSION = "pengingat_izin"
SETTING_BACKUP_FOLDER = "folder_cadangan"
SETTING_MUHASABAH_PROMPTS = "pertanyaan_muhasabah"
META_ONBOARDING_DONE = "pengenalan_selesai"
META_LAST_BACKUP = "cadangan_terakhir"

APP_VERSION = "0.5.0"
REPOSITORY_URL = "https://github.com/aksara26/IslamicHabits"
