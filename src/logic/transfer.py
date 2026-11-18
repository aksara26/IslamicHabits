"""Ekspor, impor, dan cadangan JSON berversi.

Format mengikuti keputusan README: satu objek JSON dengan penanda format,
nomor versi, metadata, dan array untuk tiap tabel. Modul ini murni Python
sehingga bisa diuji tanpa GTK.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .constants import (
    APP_VERSION,
    BACKUP_INTERVAL_DAYS,
    EXPORT_FORMAT,
    EXPORT_VERSION,
    META_LAST_BACKUP,
    SCHEMA_VERSION,
    SETTING_BACKUP_FOLDER,
)
from .database import default_data_dir
from .repository import Repository
from .statistics import StatusValue

__all__ = [
    "TransferError",
    "ImportPreview",
    "ImportSummary",
    "TABLES",
    "create_export",
    "write_export",
    "parse_export",
    "validate_payload",
    "describe_import",
    "import_payload",
    "create_backup",
    "backup_due",
    "maybe_backup",
]

TABLES = ("kategori", "ibadah", "catatan", "muhasabah", "pengaturan", "meta")

COLUMNS: dict[str, tuple[str, ...]] = {
    "kategori": ("id", "nama", "urutan", "lipat"),
    "ibadah": (
        "id",
        "nama",
        "kategori_id",
        "jenis",
        "target",
        "satuan",
        "hari_aktif",
        "aktif_mulai",
        "diarsipkan_pada",
        "urutan",
    ),
    "catatan": (
        "ibadah_id",
        "tanggal",
        "nilai_bool",
        "nilai_angka",
        "nilai_status",
        "jam",
        "catatan",
    ),
    "muhasabah": ("tanggal", "teks", "jawaban"),
    "pengaturan": ("kunci", "nilai"),
    "meta": ("kunci", "nilai"),
}

PRIMARY_KEYS: dict[str, tuple[str, ...]] = {
    "kategori": ("id",),
    "ibadah": ("id",),
    "catatan": ("ibadah_id", "tanggal"),
    "muhasabah": ("tanggal",),
    "pengaturan": ("kunci",),
    "meta": ("kunci",),
}

# Urutan insert harus menghormati foreign key.
INSERT_ORDER = ("kategori", "ibadah", "catatan", "muhasabah", "pengaturan", "meta")
DELETE_ORDER = tuple(reversed(INSERT_ORDER))


class TransferError(ValueError):
    """Berkas ekspor tidak dikenal, rusak, atau tidak konsisten."""


@dataclass(frozen=True)
class ImportPreview:
    counts: dict[str, int]
    new: dict[str, int]
    conflicts: dict[str, int]

    @property
    def total_new(self) -> int:
        return sum(self.new.values())

    @property
    def total_conflicts(self) -> int:
        return sum(self.conflicts.values())


@dataclass(frozen=True)
class ImportSummary:
    inserted: dict[str, int]
    skipped: dict[str, int]
    deleted: dict[str, int] = field(default_factory=dict)

    @property
    def total_inserted(self) -> int:
        return sum(self.inserted.values())


def _rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(f"SELECT * FROM {table}")]


def create_export(repository: Repository) -> dict[str, Any]:
    """Bangun objek JSON dari seluruh isi basis data."""

    data = {table: _rows(repository.connection, table) for table in TABLES}
    return {
        "format": EXPORT_FORMAT,
        "schema_version": SCHEMA_VERSION,
        "export_version": EXPORT_VERSION,
        "app_version": APP_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data": data,
    }


def write_export(repository: Repository, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(create_export(repository), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target


def _read_export_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise TransferError(f"Tidak bisa membaca berkas: {error}") from error


def parse_export(source: str | Path) -> dict[str, Any]:
    """Baca JSON dari path atau string, lalu validasi isinya."""

    if isinstance(source, Path):
        text = _read_export_file(source)
    else:
        # String JSON biasanya diawali '{' atau '['; selain itu coba sebagai path.
        path = Path(source) if "\n" not in source else None
        text = (
            _read_export_file(path)
            if path is not None and path.is_file()
            else source
        )
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise TransferError("Berkas bukan JSON yang valid") from error
    validate_payload(payload)
    return payload


def _check_date(value: Any, field: str, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    if not isinstance(value, str):
        raise TransferError(f"{field} harus berupa tanggal ISO")
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise TransferError(f"{field} bukan tanggal ISO yang valid") from error


def _check_int(value: Any, field: str, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    if not isinstance(value, int) or isinstance(value, bool):
        raise TransferError(f"{field} harus berupa bilangan bulat")


def _check_number(value: Any, field: str, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TransferError(f"{field} harus berupa angka")
    if value < 0:
        raise TransferError(f"{field} tidak boleh negatif")


def _check_text(value: Any, field: str, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    if not isinstance(value, str):
        raise TransferError(f"{field} harus berupa teks")


def validate_payload(payload: Any) -> None:
    """Validasi struktural sebelum data apa pun disentuh."""

    if not isinstance(payload, dict):
        raise TransferError("Isi berkas bukan objek JSON")
    if payload.get("format") != EXPORT_FORMAT:
        raise TransferError("Format berkas tidak dikenal")
    for key in ("schema_version", "export_version"):
        value = payload.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise TransferError(f"{key} tidak valid")
    if payload["schema_version"] > SCHEMA_VERSION:
        raise TransferError("Berkas memakai versi skema yang lebih baru")
    if payload["export_version"] > EXPORT_VERSION:
        raise TransferError("Berkas memakai versi ekspor yang lebih baru")

    data = payload.get("data")
    if not isinstance(data, dict):
        raise TransferError("Bagian data tidak ditemukan")

    seen: dict[str, set[tuple[Any, ...]]] = {}
    for table in TABLES:
        rows = data.get(table, [])
        if not isinstance(rows, list):
            raise TransferError(f"Tabel {table} bukan array")
        seen[table] = set()
        for row in rows:
            if not isinstance(row, dict):
                raise TransferError(f"Baris {table} bukan objek")
            missing = set(COLUMNS[table]) - set(row)
            if missing:
                raise TransferError(f"Baris {table} kehilangan kolom: {', '.join(sorted(missing))}")
            for column in PRIMARY_KEYS[table]:
                if column in {"kunci", "tanggal"}:
                    _check_text(row[column], f"{table}.{column}")
                else:
                    _check_int(row[column], f"{table}.{column}")
            key = tuple(row[column] for column in PRIMARY_KEYS[table])
            if key in seen[table]:
                raise TransferError(f"Kunci ganda pada tabel {table}: {key}")
            seen[table].add(key)

    for row in data["kategori"]:
        _check_text(row["nama"], "kategori.nama")
        _check_int(row["urutan"], "kategori.urutan")
        _check_int(row["lipat"], "kategori.lipat")

    for row in data["ibadah"]:
        _check_text(row["nama"], "ibadah.nama")
        _check_int(row["urutan"], "ibadah.urutan")
        _check_int(row["kategori_id"], "ibadah.kategori_id", optional=True)
        _check_number(row["target"], "ibadah.target", optional=True)
        _check_text(row["satuan"], "ibadah.satuan")

    for row in data["ibadah"]:
        if row["jenis"] not in {"centang", "angka", "status"}:
            raise TransferError("Jenis ibadah tidak dikenal")
        _check_date(row["aktif_mulai"], "aktif_mulai", optional=True)
        _check_date(row["diarsipkan_pada"], "diarsipkan_pada", optional=True)
        if row["kategori_id"] is not None and row["kategori_id"] not in {
            item["id"] for item in data["kategori"]
        }:
            raise TransferError("Ibadah merujuk ke kategori yang tidak ada")
        mask = row["hari_aktif"]
        if not isinstance(mask, int) or isinstance(mask, bool) or not 0 <= mask <= 127:
            raise TransferError("hari_aktif harus berupa bitmask 0–127")

    worship_ids = {item["id"] for item in data["ibadah"]}
    for row in data["catatan"]:
        _check_date(row["tanggal"], "tanggal")
        _check_int(row["nilai_bool"], "catatan.nilai_bool", optional=True)
        _check_number(row["nilai_angka"], "catatan.nilai_angka", optional=True)
        _check_text(row["nilai_status"], "catatan.nilai_status", optional=True)
        _check_text(row["jam"], "catatan.jam", optional=True)
        _check_text(row["catatan"], "catatan.catatan", optional=True)
        if row["ibadah_id"] not in worship_ids:
            raise TransferError("Catatan merujuk ke ibadah yang tidak ada")
        if row["nilai_status"] is not None and row["nilai_status"] not in {
            status.value for status in StatusValue
        }:
            raise TransferError("Nilai status tidak dikenal")

    for row in data["muhasabah"]:
        _check_date(row["tanggal"], "tanggal")
        _check_text(row["teks"], "muhasabah.teks")
        _check_text(row["jawaban"], "muhasabah.jawaban")

    for table in ("pengaturan", "meta"):
        for row in data[table]:
            _check_text(row["nilai"], f"{table}.nilai")


def _key_of(table: str, row: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(row[column] for column in PRIMARY_KEYS[table])


def describe_import(repository: Repository, payload: dict[str, Any]) -> ImportPreview:
    """Hitung jumlah baris baru dan konflik untuk pratinjau dialog."""

    validate_payload(payload)
    counts: dict[str, int] = {}
    new: dict[str, int] = {}
    conflicts: dict[str, int] = {}
    for table in TABLES:
        rows = payload["data"][table]
        counts[table] = len(rows)
        existing = {
            tuple(row[column] for column in PRIMARY_KEYS[table])
            for row in repository.connection.execute(
                f"SELECT {', '.join(PRIMARY_KEYS[table])} FROM {table}"
            )
        }
        keys = [_key_of(table, row) for row in rows]
        conflicts[table] = sum(1 for key in keys if key in existing)
        new[table] = len(keys) - conflicts[table]
    return ImportPreview(counts=counts, new=new, conflicts=conflicts)


def import_payload(
    repository: Repository,
    payload: dict[str, Any],
    *,
    mode: str = "merge",
) -> ImportSummary:
    """Impor dengan mode ``merge`` atau ``replace``."""

    if mode not in {"merge", "replace"}:
        raise ValueError("Mode impor harus 'merge' atau 'replace'")
    validate_payload(payload)
    connection = repository.connection
    inserted = {table: 0 for table in TABLES}
    skipped = {table: 0 for table in TABLES}
    deleted = {table: 0 for table in TABLES}

    try:
        connection.execute("BEGIN")
        if mode == "replace":
            for table in DELETE_ORDER:
                cursor = connection.execute(f"DELETE FROM {table}")
                deleted[table] = cursor.rowcount

        for table in INSERT_ORDER:
            rows = payload["data"][table]
            columns = COLUMNS[table]
            placeholders = ", ".join("?" for _ in columns)
            sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
            for row in rows:
                values = [row[column] for column in columns]
                if mode == "merge":
                    conditions = " AND ".join(
                        f"{column} IS ?" for column in PRIMARY_KEYS[table]
                    )
                    key = _key_of(table, row)
                    exists = connection.execute(
                        f"SELECT 1 FROM {table} WHERE {conditions}", key
                    ).fetchone()
                    if exists is not None:
                        skipped[table] += 1
                        continue
                if table == "meta" and row["kunci"] == "schema_version":
                    skipped[table] += 1
                    continue
                connection.execute(sql, values)
                inserted[table] += 1

        if mode == "replace":
            connection.execute(
                """
                INSERT INTO meta (kunci, nilai) VALUES ('schema_version', ?)
                ON CONFLICT(kunci) DO UPDATE SET nilai = excluded.nilai
                """,
                (str(SCHEMA_VERSION),),
            )
            connection.execute(
                """
                INSERT INTO meta (kunci, nilai) VALUES ('defaults_seeded', '1')
                ON CONFLICT(kunci) DO NOTHING
                """
            )
        connection.commit()
    except sqlite3.Error as error:
        connection.rollback()
        raise TransferError(f"Gagal mengimpor data: {error}") from error

    return ImportSummary(inserted=inserted, skipped=skipped, deleted=deleted)


def backup_folder(repository: Repository) -> Path:
    configured = repository.get_setting(SETTING_BACKUP_FOLDER)
    return Path(configured) if configured else default_data_dir() / "backups"


def create_backup(repository: Repository, folder: str | Path | None = None) -> Path:
    target_folder = Path(folder) if folder is not None else backup_folder(repository)
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    path = target_folder / f"islamichabits-{timestamp}.json"
    write_export(repository, path)
    repository.set_meta(META_LAST_BACKUP, date.today().isoformat())
    return path


def backup_due(repository: Repository, today: date | None = None) -> bool:
    last = repository.get_meta(META_LAST_BACKUP)
    if last is None:
        return True
    try:
        previous = date.fromisoformat(last)
    except ValueError:
        return True
    return (today or date.today()) - previous >= timedelta(days=BACKUP_INTERVAL_DAYS)


def maybe_backup(repository: Repository, folder: str | Path | None = None) -> Path | None:
    if not backup_due(repository):
        return None
    return create_backup(repository, folder)
