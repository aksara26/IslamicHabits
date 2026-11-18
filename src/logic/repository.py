"""Akses data IslamicHabits di atas SQLite.

Repository ini tidak mengimpor GTK/Adw. Objek yang dikembalikan bisa langsung
diberikan ke modul ``statistics`` lewat metode ``to_statistics()``.
"""

from __future__ import annotations

import math
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .database import default_photos_dir, get_meta, initialize, set_meta
from .statistics import Entry as StatisticsEntry
from .statistics import EntryKind, StatusValue
from .statistics import Worship as StatisticsWorship

__all__ = [
    "CategoryRecord",
    "WorshipRecord",
    "EntryRecord",
    "MuhasabahRecord",
    "DailyNoteRecord",
    "MemoPhotoRecord",
    "SearchHit",
    "Repository",
    "EntryValue",
    "neutral_value",
    "PHOTO_SUFFIXES",
]

EntryValue = bool | float | str | StatusValue | None
_UNSET = object()

PHOTO_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})
MAX_PHOTO_BYTES = 25 * 1024 * 1024


def _to_iso(value: date | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    return date.fromisoformat(value).isoformat()


def _from_iso(value: str | None) -> date | None:
    return None if value is None else date.fromisoformat(value)


def _weekday_mask(weekdays: frozenset[int] | set[int]) -> int:
    return sum(1 << day for day in weekdays if 0 <= day <= 6)


def _weekdays_from_mask(mask: int) -> frozenset[int]:
    return frozenset(day for day in range(7) if mask & (1 << day))


def neutral_value(kind: EntryKind) -> EntryValue:
    """Nilai netral saat sebuah baris perlu catatan tanpa pilihan pengguna."""

    if kind is EntryKind.CHECK:
        return False
    if kind is EntryKind.NUMBER:
        return 0.0
    return StatusValue.BELUM


@dataclass(frozen=True)
class CategoryRecord:
    id: int
    name: str
    order: int
    collapsed: bool


@dataclass(frozen=True)
class WorshipRecord:
    id: int
    name: str
    category_id: int | None
    category_name: str | None
    kind: EntryKind
    target: float | None
    unit: str
    active_weekdays: frozenset[int]
    active_from: date | None
    archived_on: date | None
    order: int

    def to_statistics(self) -> StatisticsWorship:
        return StatisticsWorship(
            id=self.id,
            name=self.name,
            kind=self.kind,
            target=self.target,
            active_from=self.active_from,
            archived_on=self.archived_on,
            active_weekdays=self.active_weekdays,
        )


@dataclass(frozen=True)
class EntryRecord:
    worship_id: int
    day: date
    value: EntryValue
    time: str | None
    note: str

    def to_statistics(self) -> StatisticsEntry:
        return StatisticsEntry(
            worship_id=self.worship_id,
            day=self.day,
            value=self.value,
        )


@dataclass(frozen=True)
class MuhasabahRecord:
    day: date
    text: str
    answers: str


@dataclass(frozen=True)
class DailyNoteRecord:
    """Catatan bebas untuk satu tanggal, berbeda dari catatan per ibadah."""

    day: date
    text: str
    photo_count: int = 0


@dataclass(frozen=True)
class MemoPhotoRecord:
    """Satu berkas foto yang dilampirkan pada memo tanggal tertentu."""

    id: int
    day: date
    file_name: str
    caption: str
    order: int


@dataclass(frozen=True)
class SearchHit:
    """Satu hasil pencarian lintas memo, muhasabah, catatan, dan ibadah.

    ``kind`` bernilai ``memo``, ``muhasabah``, ``entry``, atau ``worship``.
    Halaman yang membuka hasil menentukan sendiri judul dan ikon yang dipakai,
    sehingga repository tetap bebas dari GTK.
    """

    kind: str
    title: str
    snippet: str
    day: date | None = None
    worship_id: int | None = None


class Repository:
    """Operasi baca/tulis untuk semua tabel."""

    _WORSHIP_SELECT = """
        SELECT i.id, i.nama, i.kategori_id, k.nama AS kategori_nama, i.jenis,
               i.target, i.satuan, i.hari_aktif, i.aktif_mulai,
               i.diarsipkan_pada, i.urutan
        FROM ibadah i
        LEFT JOIN kategori k ON k.id = i.kategori_id
    """

    _ENTRY_SELECT = """
        SELECT e.ibadah_id, e.tanggal, e.nilai_bool, e.nilai_angka,
               e.nilai_status, e.jam, e.catatan, i.jenis
        FROM catatan e
        JOIN ibadah i ON i.id = e.ibadah_id
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        photos_dir: str | Path | None = None,
    ) -> None:
        self._db = connection
        self._photos_dir = (
            Path(photos_dir) if photos_dir is not None else default_photos_dir()
        )

    @property
    def connection(self) -> sqlite3.Connection:
        return self._db

    @property
    def photos_dir(self) -> Path:
        return self._photos_dir

    def close(self) -> None:
        self._db.close()

    # -- meta dan pengaturan --------------------------------------------

    def get_meta(self, key: str) -> str | None:
        return get_meta(self._db, key)

    def set_meta(self, key: str, value: str) -> None:
        set_meta(self._db, key, value)
        self._db.commit()

    def get_setting(self, key: str, default: str = "") -> str:
        value = self._db.execute(
            "SELECT nilai FROM pengaturan WHERE kunci = ?", (key,)
        ).fetchone()
        return default if value is None else str(value["nilai"])

    def set_setting(self, key: str, value: str) -> None:
        self._db.execute(
            """
            INSERT INTO pengaturan (kunci, nilai) VALUES (?, ?)
            ON CONFLICT(kunci) DO UPDATE SET nilai = excluded.nilai
            """,
            (key, value),
        )
        self._db.commit()

    # -- kategori --------------------------------------------------------

    def list_categories(self) -> tuple[CategoryRecord, ...]:
        rows = self._db.execute(
            "SELECT id, nama, urutan, lipat FROM kategori ORDER BY urutan, id"
        ).fetchall()
        return tuple(
            CategoryRecord(
                id=row["id"],
                name=row["nama"],
                order=row["urutan"],
                collapsed=bool(row["lipat"]),
            )
            for row in rows
        )

    def add_category(self, name: str) -> CategoryRecord:
        clean = name.strip()
        if not clean:
            raise ValueError("Nama kategori tidak boleh kosong")
        order = self._next_order("kategori")
        cursor = self._db.execute(
            "INSERT INTO kategori (nama, urutan) VALUES (?, ?)", (clean, order)
        )
        self._db.commit()
        return next(item for item in self.list_categories() if item.id == cursor.lastrowid)

    def rename_category(self, category_id: int, name: str) -> None:
        clean = name.strip()
        if not clean:
            raise ValueError("Nama kategori tidak boleh kosong")
        self._db.execute(
            "UPDATE kategori SET nama = ? WHERE id = ?", (clean, category_id)
        )
        self._db.commit()

    def set_category_collapsed(self, category_id: int, collapsed: bool) -> None:
        self._db.execute(
            "UPDATE kategori SET lipat = ? WHERE id = ?",
            (int(collapsed), category_id),
        )
        self._db.commit()

    def reorder_categories(self, ordered_ids: list[int]) -> None:
        self._reorder("kategori", ordered_ids)

    # -- ibadah ----------------------------------------------------------

    def list_worships(
        self,
        *,
        include_archived: bool = False,
        category_id: int | None = None,
    ) -> tuple[WorshipRecord, ...]:
        conditions: list[str] = []
        params: list[Any] = []
        if not include_archived:
            conditions.append("i.diarsipkan_pada IS NULL")
        if category_id is not None:
            conditions.append("i.kategori_id = ?")
            params.append(category_id)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        rows = self._db.execute(
            self._WORSHIP_SELECT + where + " ORDER BY i.urutan, i.id", params
        ).fetchall()
        return tuple(self._worship_from_row(row) for row in rows)

    def get_worship(self, worship_id: int) -> WorshipRecord:
        row = self._db.execute(
            self._WORSHIP_SELECT + " WHERE i.id = ?", (worship_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"Ibadah {worship_id} tidak ditemukan")
        return self._worship_from_row(row)

    def add_worship(
        self,
        *,
        name: str,
        category_id: int | None = None,
        kind: EntryKind = EntryKind.CHECK,
        target: float | None = None,
        unit: str = "",
        active_weekdays: frozenset[int] | set[int] | None = None,
        active_from: date | str | None = None,
    ) -> WorshipRecord:
        clean = name.strip()
        if not clean:
            raise ValueError("Nama ibadah tidak boleh kosong")
        if not isinstance(kind, EntryKind):
            raise ValueError("Jenis isian tidak dikenal")
        if category_id is not None:
            exists = self._db.execute(
                "SELECT 1 FROM kategori WHERE id = ?", (category_id,)
            ).fetchone()
            if exists is None:
                raise KeyError(f"Kategori {category_id} tidak ditemukan")
        weekdays = (
            frozenset(range(7))
            if active_weekdays is None
            else frozenset(active_weekdays)
        )
        cursor = self._db.execute(
            """
            INSERT INTO ibadah
                (nama, kategori_id, jenis, target, satuan, hari_aktif,
                 aktif_mulai, urutan)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                clean,
                category_id,
                kind.value,
                target,
                unit.strip(),
                _weekday_mask(weekdays),
                _to_iso(active_from) if active_from is not None else date.today().isoformat(),
                self._next_order("ibadah"),
            ),
        )
        self._db.commit()
        return self.get_worship(int(cursor.lastrowid))

    def update_worship(
        self,
        worship_id: int,
        *,
        name: object = _UNSET,
        category_id: object = _UNSET,
        kind: object = _UNSET,
        target: object = _UNSET,
        unit: object = _UNSET,
        active_weekdays: object = _UNSET,
        active_from: object = _UNSET,
    ) -> WorshipRecord:
        updates: dict[str, Any] = {}
        if name is not _UNSET:
            clean = str(name).strip()
            if not clean:
                raise ValueError("Nama ibadah tidak boleh kosong")
            updates["nama"] = clean
        if category_id is not _UNSET:
            if category_id is not None and not isinstance(category_id, int):
                raise ValueError("Kategori tidak valid")
            updates["kategori_id"] = category_id
        if kind is not _UNSET:
            if not isinstance(kind, EntryKind):
                raise ValueError("Jenis isian tidak dikenal")
            updates["jenis"] = kind.value
        if target is not _UNSET:
            updates["target"] = None if target is None else float(target)
        if unit is not _UNSET:
            updates["satuan"] = str(unit).strip()
        if active_weekdays is not _UNSET:
            updates["hari_aktif"] = _weekday_mask(frozenset(active_weekdays))  # type: ignore[arg-type]
        if active_from is not _UNSET:
            updates["aktif_mulai"] = _to_iso(active_from)  # type: ignore[arg-type]

        if updates:
            assignments = ", ".join(f"{column} = ?" for column in updates)
            self._db.execute(
                f"UPDATE ibadah SET {assignments} WHERE id = ?",
                (*updates.values(), worship_id),
            )
            self._db.commit()
        return self.get_worship(worship_id)

    def archive_worship(self, worship_id: int, day: date | str | None = None) -> None:
        self._db.execute(
            """
            UPDATE ibadah
            SET diarsipkan_pada = COALESCE(diarsipkan_pada, ?)
            WHERE id = ?
            """,
            (_to_iso(day) or date.today().isoformat(), worship_id),
        )
        self._db.commit()

    def restore_worship(self, worship_id: int) -> None:
        self._db.execute(
            "UPDATE ibadah SET diarsipkan_pada = NULL WHERE id = ?", (worship_id,)
        )
        self._db.commit()

    def delete_worship(self, worship_id: int) -> None:
        """Hapus permanen beserta riwayatnya; pakai konfirmasi tegas di UI."""

        self._db.execute("DELETE FROM ibadah WHERE id = ?", (worship_id,))
        self._db.commit()

    def reorder_worships(self, ordered_ids: list[int]) -> None:
        self._reorder("ibadah", ordered_ids)

    # -- catatan ---------------------------------------------------------

    def get_entry(self, worship_id: int, day: date | str) -> EntryRecord | None:
        row = self._db.execute(
            self._ENTRY_SELECT + " WHERE e.ibadah_id = ? AND e.tanggal = ?",
            (worship_id, _to_iso(day)),
        ).fetchone()
        return None if row is None else self._entry_from_row(row)

    def list_entries(
        self,
        *,
        start: date | str | None = None,
        end: date | str | None = None,
        worship_id: int | None = None,
    ) -> tuple[EntryRecord, ...]:
        conditions: list[str] = []
        params: list[Any] = []
        if start is not None:
            conditions.append("e.tanggal >= ?")
            params.append(_to_iso(start))
        if end is not None:
            conditions.append("e.tanggal <= ?")
            params.append(_to_iso(end))
        if worship_id is not None:
            conditions.append("e.ibadah_id = ?")
            params.append(worship_id)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        rows = self._db.execute(
            self._ENTRY_SELECT + where + " ORDER BY e.tanggal, e.ibadah_id", params
        ).fetchall()
        return tuple(self._entry_from_row(row) for row in rows)

    def set_entry(
        self,
        worship_id: int,
        day: date | str,
        *,
        value: EntryValue,
        time: str | None = None,
        note: str = "",
    ) -> EntryRecord:
        """Tulis satu catatan per ibadah per tanggal (upsert)."""

        kind = self._kind_of(worship_id)
        if value is None:
            raise ValueError("Gunakan delete_entry() untuk menghapus catatan")
        bool_value: int | None = None
        number_value: float | None = None
        status_value: str | None = None

        if kind is EntryKind.CHECK:
            bool_value = int(bool(value))
        elif kind is EntryKind.NUMBER:
            number_value = float(value)  # type: ignore[arg-type]
            if not math.isfinite(number_value):
                raise ValueError("Nilai angka harus berupa bilangan hingga")
        else:
            raw = value.value if isinstance(value, StatusValue) else str(value)
            status_value = StatusValue(raw.strip().lower()).value

        clean_time = _normalize_time(time)
        self._db.execute(
            """
            INSERT INTO catatan
                (ibadah_id, tanggal, nilai_bool, nilai_angka, nilai_status, jam, catatan)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ibadah_id, tanggal) DO UPDATE SET
                nilai_bool = excluded.nilai_bool,
                nilai_angka = excluded.nilai_angka,
                nilai_status = excluded.nilai_status,
                jam = excluded.jam,
                catatan = excluded.catatan
            """,
            (
                worship_id,
                _to_iso(day),
                bool_value,
                number_value,
                status_value,
                clean_time,
                note.strip(),
            ),
        )
        self._db.commit()
        entry = self.get_entry(worship_id, day)
        assert entry is not None
        return entry

    def delete_entry(self, worship_id: int, day: date | str) -> None:
        self._db.execute(
            "DELETE FROM catatan WHERE ibadah_id = ? AND tanggal = ?",
            (worship_id, _to_iso(day)),
        )
        self._db.commit()

    def statistics_inputs(
        self,
        *,
        start: date | str | None = None,
        end: date | str | None = None,
    ) -> tuple[tuple[StatisticsWorship, ...], tuple[StatisticsEntry, ...]]:
        """Data siap pakai untuk fungsi-fungsi di ``statistics``."""

        worships = tuple(
            item.to_statistics() for item in self.list_worships(include_archived=True)
        )
        entries = tuple(
            item.to_statistics() for item in self.list_entries(start=start, end=end)
        )
        return worships, entries

    # -- muhasabah -------------------------------------------------------

    def get_muhasabah(self, day: date | str) -> MuhasabahRecord:
        row = self._db.execute(
            "SELECT tanggal, teks, jawaban FROM muhasabah WHERE tanggal = ?",
            (_to_iso(day),),
        ).fetchone()
        if row is None:
            return MuhasabahRecord(day=date.fromisoformat(_to_iso(day)), text="", answers="")  # type: ignore[arg-type]
        return MuhasabahRecord(
            day=date.fromisoformat(row["tanggal"]),
            text=row["teks"],
            answers=row["jawaban"],
        )

    def list_muhasabah(self) -> tuple[MuhasabahRecord, ...]:
        rows = self._db.execute(
            "SELECT tanggal, teks, jawaban FROM muhasabah ORDER BY tanggal DESC"
        ).fetchall()
        return tuple(
            MuhasabahRecord(
                day=date.fromisoformat(row["tanggal"]),
                text=row["teks"],
                answers=row["jawaban"],
            )
            for row in rows
        )

    def save_muhasabah(self, day: date | str, text: str, answers: str = "") -> None:
        self._db.execute(
            """
            INSERT INTO muhasabah (tanggal, teks, jawaban) VALUES (?, ?, ?)
            ON CONFLICT(tanggal) DO UPDATE SET
                teks = excluded.teks, jawaban = excluded.jawaban
            """,
            (_to_iso(day), text, answers),
        )
        self._db.commit()

    def delete_muhasabah(self, day: date | str) -> None:
        """Hapus satu baris muhasabah yang sudah kosong."""

        self._db.execute(
            "DELETE FROM muhasabah WHERE tanggal = ?", (_to_iso(day),)
        )
        self._db.commit()

    # -- catatan harian ---------------------------------------------------

    def get_daily_note(self, day: date | str) -> DailyNoteRecord:
        iso = _to_iso(day)
        assert iso is not None
        row = self._db.execute(
            "SELECT teks FROM catatan_harian WHERE tanggal = ?", (iso,)
        ).fetchone()
        count = self._db.execute(
            "SELECT COUNT(*) AS n FROM memo_foto WHERE tanggal = ?", (iso,)
        ).fetchone()
        return DailyNoteRecord(
            day=date.fromisoformat(iso),
            text="" if row is None else row["teks"],
            photo_count=int(count["n"]),
        )

    def list_daily_notes(
        self,
        *,
        start: date | str | None = None,
        end: date | str | None = None,
    ) -> tuple[DailyNoteRecord, ...]:
        conditions: list[str] = []
        params: list[Any] = []
        if start is not None:
            conditions.append("d.tanggal >= ?")
            params.append(_to_iso(start))
        if end is not None:
            conditions.append("d.tanggal <= ?")
            params.append(_to_iso(end))
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        rows = self._db.execute(
            """
            SELECT d.tanggal AS tanggal, COALESCE(h.teks, '') AS teks,
                   (SELECT COUNT(*) FROM memo_foto f
                    WHERE f.tanggal = d.tanggal) AS foto
            FROM (
                SELECT tanggal FROM catatan_harian
                UNION
                SELECT tanggal FROM memo_foto
            ) AS d
            LEFT JOIN catatan_harian h ON h.tanggal = d.tanggal
            """
            + where
            + " ORDER BY d.tanggal DESC",
            params,
        ).fetchall()
        return tuple(
            DailyNoteRecord(
                day=date.fromisoformat(row["tanggal"]),
                text=row["teks"],
                photo_count=int(row["foto"]),
            )
            for row in rows
        )

    def save_daily_note(self, day: date | str, text: str) -> None:
        """Simpan catatan bebas satu tanggal; baris kosong dihapus.

        Foto memo tidak ikut terhapus karena disimpan di tabel terpisah.
        """

        clean = text.strip()
        if not clean:
            self.delete_daily_note(day)
            return
        self._db.execute(
            """
            INSERT INTO catatan_harian (tanggal, teks) VALUES (?, ?)
            ON CONFLICT(tanggal) DO UPDATE SET teks = excluded.teks
            """,
            (_to_iso(day), clean),
        )
        self._db.commit()

    def delete_daily_note(self, day: date | str) -> None:
        self._db.execute(
            "DELETE FROM catatan_harian WHERE tanggal = ?", (_to_iso(day),)
        )
        self._db.commit()

    # -- foto memo --------------------------------------------------------

    def list_memo_photos(self, day: date | str | None = None) -> tuple[MemoPhotoRecord, ...]:
        if day is None:
            rows = self._db.execute(
                "SELECT id, tanggal, berkas, keterangan, urutan FROM memo_foto "
                "ORDER BY tanggal DESC, urutan, id"
            ).fetchall()
        else:
            rows = self._db.execute(
                "SELECT id, tanggal, berkas, keterangan, urutan FROM memo_foto "
                "WHERE tanggal = ? ORDER BY urutan, id",
                (_to_iso(day),),
            ).fetchall()
        return tuple(self._memo_photo_from_row(row) for row in rows)

    def count_memo_photos(self, day: date | str) -> int:
        row = self._db.execute(
            "SELECT COUNT(*) AS n FROM memo_foto WHERE tanggal = ?", (_to_iso(day),)
        ).fetchone()
        return int(row["n"])

    def add_memo_photo(
        self,
        day: date | str,
        source: str | Path,
        *,
        caption: str = "",
    ) -> MemoPhotoRecord:
        """Salin satu berkas gambar ke folder data dan catat di basis data."""

        source_path = Path(source)
        if not source_path.is_file():
            raise ValueError("Berkas foto tidak ditemukan")
        suffix = source_path.suffix.lower()
        if suffix not in PHOTO_SUFFIXES:
            raise ValueError("Format foto harus JPG, PNG, WEBP, atau GIF")
        size = source_path.stat().st_size
        if size <= 0:
            raise ValueError("Berkas foto kosong")
        if size > MAX_PHOTO_BYTES:
            raise ValueError("Ukuran foto maksimal 25 MB")

        iso = _to_iso(day)
        assert iso is not None
        self._photos_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"{iso.replace('-', '')}-{uuid4().hex}{suffix}"
        target = self._photos_dir / file_name
        shutil.copyfile(source_path, target)

        order_row = self._db.execute(
            "SELECT COALESCE(MAX(urutan), -1) + 1 AS next FROM memo_foto "
            "WHERE tanggal = ?",
            (iso,),
        ).fetchone()
        try:
            cursor = self._db.execute(
                """
                INSERT INTO memo_foto
                    (tanggal, berkas, keterangan, urutan, dibuat_pada)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    iso,
                    file_name,
                    caption.strip(),
                    int(order_row["next"]),
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            self._db.commit()
        except sqlite3.Error:
            target.unlink(missing_ok=True)
            raise
        return self._get_memo_photo(int(cursor.lastrowid))

    def delete_memo_photo(self, photo_id: int) -> None:
        row = self._db.execute(
            "SELECT berkas FROM memo_foto WHERE id = ?", (photo_id,)
        ).fetchone()
        if row is None:
            return
        self._db.execute("DELETE FROM memo_foto WHERE id = ?", (photo_id,))
        self._db.commit()
        (self._photos_dir / row["berkas"]).unlink(missing_ok=True)

    def update_memo_caption(
        self, photo_id: int, caption: str
    ) -> MemoPhotoRecord | None:
        """Perbarui keterangan foto tanpa menyentuh berkas gambarnya."""

        self._db.execute(
            "UPDATE memo_foto SET keterangan = ? WHERE id = ?",
            (caption.strip(), photo_id),
        )
        self._db.commit()
        row = self._db.execute(
            "SELECT id, tanggal, berkas, keterangan, urutan "
            "FROM memo_foto WHERE id = ?",
            (photo_id,),
        ).fetchone()
        return None if row is None else self._memo_photo_from_row(row)

    def photo_path(self, photo: MemoPhotoRecord | str) -> Path:
        name = photo.file_name if isinstance(photo, MemoPhotoRecord) else photo
        return self._photos_dir / name

    # -- pencarian -------------------------------------------------------

    @staticmethod
    def _search_snippet(text: str, query: str, limit: int = 120) -> str:
        """Padatkan teks dan potong di sekitar kata yang dicari."""

        compact = " ".join(text.split())
        if len(compact) <= limit:
            return compact
        position = compact.casefold().find(query.casefold())
        start = max(0, position - 40) if position >= 0 else 0
        end = min(len(compact), start + limit)
        prefix = "…" if start > 0 else ""
        suffix = "…" if end < len(compact) else ""
        return f"{prefix}{compact[start:end].strip()}{suffix}"

    def search_all(self, query: str, *, limit: int = 20) -> tuple[SearchHit, ...]:
        """Cari memo, muhasabah, catatan ibadah, dan nama ibadah sekaligus.

        Hasil dikelompokkan sesuai urutan pencarian supaya halaman pemanggil
        bisa menampilkan judul bagian tanpa mengurutkan ulang. Query kurang
        dari dua karakter diabaikan agar pencarian tidak membebani basis data.
        """

        text = query.strip()
        if len(text) < 2:
            return ()
        pattern = f"%{text}%"
        hits: list[SearchHit] = []

        for row in self._db.execute(
            "SELECT tanggal, teks FROM catatan_harian WHERE teks LIKE ? "
            "ORDER BY tanggal DESC LIMIT ?",
            (pattern, limit),
        ).fetchall():
            hits.append(
                SearchHit(
                    kind="memo",
                    title="Memo harian",
                    snippet=self._search_snippet(row["teks"], text),
                    day=date.fromisoformat(row["tanggal"]),
                )
            )

        for row in self._db.execute(
            "SELECT tanggal, teks, jawaban FROM muhasabah "
            "WHERE teks LIKE ? OR jawaban LIKE ? "
            "ORDER BY tanggal DESC LIMIT ?",
            (pattern, pattern, limit),
        ).fetchall():
            answers = row["jawaban"] or ""
            source = (
                row["teks"]
                if text.casefold() in (row["teks"] or "").casefold()
                else (answers or row["teks"])
            )
            hits.append(
                SearchHit(
                    kind="muhasabah",
                    title="Muhasabah",
                    snippet=self._search_snippet(source, text),
                    day=date.fromisoformat(row["tanggal"]),
                )
            )

        for row in self._db.execute(
            "SELECT e.tanggal, e.catatan, i.id AS ibadah_id, i.nama "
            "FROM catatan e JOIN ibadah i ON i.id = e.ibadah_id "
            "WHERE e.catatan LIKE ? ORDER BY e.tanggal DESC LIMIT ?",
            (pattern, limit),
        ).fetchall():
            hits.append(
                SearchHit(
                    kind="entry",
                    title=row["nama"],
                    snippet=self._search_snippet(row["catatan"], text),
                    day=date.fromisoformat(row["tanggal"]),
                    worship_id=int(row["ibadah_id"]),
                )
            )

        for row in self._db.execute(
            "SELECT i.id, i.nama, k.nama AS kategori FROM ibadah i "
            "LEFT JOIN kategori k ON k.id = i.kategori_id "
            "WHERE i.nama LIKE ? ORDER BY i.nama LIMIT ?",
            (pattern, limit),
        ).fetchall():
            hits.append(
                SearchHit(
                    kind="worship",
                    title=row["nama"],
                    snippet=row["kategori"] or "Ibadah atau kebiasaan",
                    worship_id=int(row["id"]),
                )
            )

        return tuple(hits)

    def clear_all_data(self) -> None:
        """Hapus semua data pengguna, lalu kembalikan ibadah bawaan.

        Dipakai setelah konfirmasi tegas dari halaman Pengaturan. Skema dan
        data awal dibuat ulang supaya aplikasi tetap bisa dipakai. Berkas foto
        memo ikut dihapus agar tidak tertinggal sebagai sampah.
        """

        photo_rows = self._db.execute("SELECT berkas FROM memo_foto").fetchall()
        for table in (
            "memo_foto",
            "catatan",
            "muhasabah",
            "catatan_harian",
            "ibadah",
            "kategori",
            "pengaturan",
            "meta",
        ):
            self._db.execute(f"DELETE FROM {table}")
        self._db.commit()
        for row in photo_rows:
            (self._photos_dir / row["berkas"]).unlink(missing_ok=True)
        initialize(self._db, seed=True)

    # -- pembantu --------------------------------------------------------

    def _next_order(self, table: str) -> int:
        row = self._db.execute(f"SELECT COALESCE(MAX(urutan), -1) + 1 AS next FROM {table}").fetchone()
        return int(row["next"])

    def _reorder(self, table: str, ordered_ids: list[int]) -> None:
        remaining = [
            row["id"]
            for row in self._db.execute(f"SELECT id FROM {table} ORDER BY urutan, id")
            if row["id"] not in ordered_ids
        ]
        for order, item_id in enumerate([*ordered_ids, *remaining]):
            self._db.execute(
                f"UPDATE {table} SET urutan = ? WHERE id = ?", (order, item_id)
            )
        self._db.commit()

    def _kind_of(self, worship_id: int) -> EntryKind:
        row = self._db.execute(
            "SELECT jenis FROM ibadah WHERE id = ?", (worship_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"Ibadah {worship_id} tidak ditemukan")
        return EntryKind(row["jenis"])

    def _worship_from_row(self, row: sqlite3.Row) -> WorshipRecord:
        return WorshipRecord(
            id=row["id"],
            name=row["nama"],
            category_id=row["kategori_id"],
            category_name=row["kategori_nama"],
            kind=EntryKind(row["jenis"]),
            target=row["target"],
            unit=row["satuan"],
            active_weekdays=_weekdays_from_mask(int(row["hari_aktif"])),
            active_from=_from_iso(row["aktif_mulai"]),
            archived_on=_from_iso(row["diarsipkan_pada"]),
            order=row["urutan"],
        )

    def _entry_from_row(self, row: sqlite3.Row) -> EntryRecord:
        kind = EntryKind(row["jenis"])
        value: EntryValue
        if kind is EntryKind.CHECK:
            value = bool(row["nilai_bool"]) if row["nilai_bool"] is not None else None
        elif kind is EntryKind.NUMBER:
            value = row["nilai_angka"]
        else:
            value = row["nilai_status"]
        return EntryRecord(
            worship_id=row["ibadah_id"],
            day=date.fromisoformat(row["tanggal"]),
            value=value,
            time=row["jam"],
            note=row["catatan"],
        )

    def _get_memo_photo(self, photo_id: int) -> MemoPhotoRecord:
        row = self._db.execute(
            "SELECT id, tanggal, berkas, keterangan, urutan FROM memo_foto "
            "WHERE id = ?",
            (photo_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Foto memo {photo_id} tidak ditemukan")
        return self._memo_photo_from_row(row)

    @staticmethod
    def _memo_photo_from_row(row: sqlite3.Row) -> MemoPhotoRecord:
        return MemoPhotoRecord(
            id=row["id"],
            day=date.fromisoformat(row["tanggal"]),
            file_name=row["berkas"],
            caption=row["keterangan"],
            order=row["urutan"],
        )


def _normalize_time(value: str | None) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    if not clean:
        return None
    try:
        datetime.strptime(clean, "%H:%M")
    except ValueError as error:
        raise ValueError("Jam harus berformat HH:MM atau dikosongkan") from error
    return clean
