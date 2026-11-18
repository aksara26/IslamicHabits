"""Koneksi, skema, dan migrasi basis data SQLite IslamicHabits.

Modul ini sengaja murni Python (sqlite3 + pathlib), tanpa GTK maupun Adw,
supaya bisa diuji tanpa jendela. Lokasi data diambil dari ``XDG_DATA_HOME``
atau ``~/.local/share``; di Flatpak, runtime mengarahkan XDG_DATA_HOME ke
``~/.var/app/<id>/data`` sehingga kode ini tetap bekerja tanpa jalur tetap.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date
from pathlib import Path

from .constants import APP_ID, SCHEMA_VERSION
from .defaults import DEFAULT_CATEGORIES, DEFAULT_WORSHIPS

__all__ = [
    "default_data_dir",
    "default_database_path",
    "connect",
    "initialize",
    "get_meta",
    "set_meta",
]

# ``hari_aktif`` adalah bitmask: bit 0 = Senin ... bit 6 = Minggu.
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meta (
    kunci TEXT PRIMARY KEY,
    nilai TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kategori (
    id INTEGER PRIMARY KEY,
    nama TEXT NOT NULL,
    urutan INTEGER NOT NULL DEFAULT 0,
    lipat INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ibadah (
    id INTEGER PRIMARY KEY,
    nama TEXT NOT NULL,
    kategori_id INTEGER REFERENCES kategori(id) ON DELETE SET NULL,
    jenis TEXT NOT NULL CHECK (jenis IN ('centang', 'angka', 'status')),
    target REAL,
    satuan TEXT NOT NULL DEFAULT '',
    hari_aktif INTEGER NOT NULL DEFAULT 127,
    aktif_mulai TEXT,
    diarsipkan_pada TEXT,
    urutan INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS catatan (
    ibadah_id INTEGER NOT NULL REFERENCES ibadah(id) ON DELETE CASCADE,
    tanggal TEXT NOT NULL,
    nilai_bool INTEGER,
    nilai_angka REAL,
    nilai_status TEXT,
    jam TEXT,
    catatan TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (ibadah_id, tanggal)
);

CREATE TABLE IF NOT EXISTS muhasabah (
    tanggal TEXT PRIMARY KEY,
    teks TEXT NOT NULL DEFAULT '',
    jawaban TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS catatan_harian (
    tanggal TEXT PRIMARY KEY,
    teks TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS pengaturan (
    kunci TEXT PRIMARY KEY,
    nilai TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_catatan_tanggal ON catatan(tanggal);
CREATE INDEX IF NOT EXISTS idx_ibadah_kategori ON ibadah(kategori_id, urutan);
"""

# Ditambah satu entri per versi skema baru. Versi 1 dibuat oleh skema awal;
# versi 2 menambahkan catatan harian.
MIGRATIONS: dict[int, str] = {
    2: """
    CREATE TABLE IF NOT EXISTS catatan_harian (
        tanggal TEXT PRIMARY KEY,
        teks TEXT NOT NULL DEFAULT ''
    );
    """,
}


def default_data_dir() -> Path:
    """Folder data pengguna sesuai XDG (atau ~/.local/share)."""

    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg_data_home) if xdg_data_home else Path.home() / ".local" / "share"
    return base / APP_ID


def default_database_path() -> Path:
    """Berkas SQLite utama aplikasi."""

    return default_data_dir() / "islamichabits.sqlite3"


def get_meta(connection: sqlite3.Connection, key: str) -> str | None:
    row = connection.execute("SELECT nilai FROM meta WHERE kunci = ?", (key,)).fetchone()
    return None if row is None else str(row["nilai"])


def set_meta(connection: sqlite3.Connection, key: str, value: str) -> None:
    connection.execute(
        """
        INSERT INTO meta (kunci, nilai) VALUES (?, ?)
        ON CONFLICT(kunci) DO UPDATE SET nilai = excluded.nilai
        """,
        (key, value),
    )


def _schema_version(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'meta'"
    ).fetchone()
    if row is None:
        return 0
    value = get_meta(connection, "schema_version")
    if value is None:
        return 0
    try:
        return int(value)
    except ValueError as error:
        raise RuntimeError(f"Versi skema tidak valid: {value!r}") from error


def _seed_defaults(connection: sqlite3.Connection) -> None:
    if get_meta(connection, "defaults_seeded") == "1":
        return

    if connection.execute("SELECT 1 FROM kategori LIMIT 1").fetchone() is None:
        for order, name in enumerate(DEFAULT_CATEGORIES):
            connection.execute(
                "INSERT INTO kategori (nama, urutan) VALUES (?, ?)",
                (name, order),
            )

    if connection.execute("SELECT 1 FROM ibadah LIMIT 1").fetchone() is None:
        category_ids = {
            row["nama"]: row["id"]
            for row in connection.execute("SELECT id, nama FROM kategori")
        }
        today = date.today().isoformat()
        order_by_category: dict[str, int] = {}
        for item in DEFAULT_WORSHIPS:
            order = order_by_category.get(item.category, 0)
            order_by_category[item.category] = order + 1
            mask = sum(1 << day for day in item.weekdays)
            connection.execute(
                """
                INSERT INTO ibadah
                    (nama, kategori_id, jenis, target, satuan, hari_aktif,
                     aktif_mulai, urutan)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.name,
                    category_ids.get(item.category),
                    item.kind.value,
                    item.target,
                    item.unit,
                    mask,
                    today,
                    order,
                ),
            )

    set_meta(connection, "defaults_seeded", "1")


def initialize(connection: sqlite3.Connection, *, seed: bool = True) -> None:
    """Buat atau migrasi skema. Aman dipanggil berulang kali."""

    version = _schema_version(connection)
    if version == 0:
        connection.executescript(SCHEMA_SQL)
        set_meta(connection, "schema_version", str(SCHEMA_VERSION))
    elif version < SCHEMA_VERSION:
        for target in range(version + 1, SCHEMA_VERSION + 1):
            migration = MIGRATIONS.get(target)
            if migration is None:
                raise RuntimeError(f"Migrasi ke skema versi {target} belum tersedia")
            connection.executescript(migration)
        set_meta(connection, "schema_version", str(SCHEMA_VERSION))
    elif version > SCHEMA_VERSION:
        raise RuntimeError(
            f"Basis data memakai skema versi {version}, aplikasi hanya mendukung {SCHEMA_VERSION}"
        )

    if seed:
        _seed_defaults(connection)
    connection.commit()


def connect(path: str | Path | None = None, *, seed: bool = True) -> sqlite3.Connection:
    """Buka basis data, pastikan skema valid, lalu kembalikan koneksinya."""

    db_path = Path(path) if path is not None else default_database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    if str(db_path) != ":memory:":
        connection.execute("PRAGMA journal_mode = WAL")
    initialize(connection, seed=seed)
    return connection
