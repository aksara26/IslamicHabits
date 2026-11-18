"""Aturan statistik harian, bulanan, dan tahunan IslamicHabits.

Modul ini sengaja murni Python: tidak mengimpor Gtk ataupun Adw, sehingga
bisa diuji tanpa membuka jendela. Semua angka dihitung ulang dari catatan,
bukan disimpan sebagai angka mati.

Keputusan yang sudah disepakati:

* Centang terlaksana bila bernilai ``True``.
* Angka terlaksana bila ``nilai >= target``. Bila target kosong/0, maka
  cukup ``nilai > 0``. Yang belum mencapai target tetap disebut "sebagian".
* Status terlaksana bila bukan ``belum`` (termasuk ``qadha``).
* Ibadah baru hanya dihitung sejak ``active_from``; ibadah arsip tidak
  dihitung pada atau sesudah ``archived_on``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from typing import Iterable, Iterator

__all__ = [
    "EntryKind",
    "StatusValue",
    "DayState",
    "Worship",
    "Entry",
    "WorshipProgress",
    "DailySummary",
    "PeriodSummary",
    "YearPoint",
    "is_active",
    "has_record",
    "is_completed",
    "classify_day",
    "compute_daily",
    "compute_range",
    "compute_yearly_series",
    "describe_completion",
]


class EntryKind(str, Enum):
    """Tipe isian yang didukung satu baris ibadah."""

    CHECK = "centang"
    NUMBER = "angka"
    STATUS = "status"


class StatusValue(str, Enum):
    """Pilihan status untuk ibadah bertipe status."""

    BELUM = "belum"
    TEPAT_WAKTU = "tepat waktu"
    TERLAMBAT = "terlambat"
    BERJAMAAH = "berjamaah"
    QADHA = "qadha"


class DayState(str, Enum):
    """Penanda hari. Tidak boleh bergantung pada warna saja."""

    EMPTY = "kosong"
    PARTIAL = "sebagian"
    FULL = "penuh"


@dataclass(frozen=True)
class Worship:
    """Definisi satu ibadah.

    ``active_weekdays`` memakai numbering Python: 0 = Senin, 6 = Minggu.
    """

    id: int
    name: str
    kind: EntryKind
    target: float | None = None
    active_from: date | None = None
    archived_on: date | None = None
    active_weekdays: frozenset[int] = frozenset(range(7))


@dataclass(frozen=True)
class Entry:
    """Satu catatan per ibadah per tanggal.

    ``value`` bertipe bool untuk centang, angka untuk angka, dan
    ``StatusValue``/str untuk status. ``None`` berarti belum ada catatan.
    """

    worship_id: int
    day: date
    value: bool | float | int | str | StatusValue | None = None


@dataclass(frozen=True)
class WorshipProgress:
    worship_id: int
    name: str
    completed: int
    partial: int
    expected: int


@dataclass(frozen=True)
class DailySummary:
    day: date
    state: DayState
    completed: int
    expected: int
    per_worship: tuple[WorshipProgress, ...]


@dataclass(frozen=True)
class PeriodSummary:
    key: str
    start: date
    end: date
    state: DayState
    completed_days: int
    partial_days: int
    expected_days: int
    per_worship: tuple[WorshipProgress, ...]


@dataclass(frozen=True)
class YearPoint:
    """Satu titik pada garis tren tahunan."""

    month: int
    completed_days: int
    expected_days: int

    @property
    def has_data(self) -> bool:
        """Bulan tanpa ibadah aktif tidak boleh digambar sebagai nol."""

        return self.expected_days > 0

    @property
    def ratio(self) -> float:
        if not self.has_data:
            return 0.0
        return self.completed_days / self.expected_days


def is_active(worship: Worship, day: date) -> bool:
    """Apakah ``worship`` diharapkan dicatat pada ``day``."""

    if worship.active_from is not None and day < worship.active_from:
        return False
    if worship.archived_on is not None and day >= worship.archived_on:
        return False
    return day.weekday() in worship.active_weekdays


def has_record(entry: Entry | None) -> bool:
    """Catatan yang sengaja dikosongkan (False / 'belum') tetap dihitung ada."""

    return entry is not None and entry.value is not None


def _as_status(value: object) -> StatusValue:
    if isinstance(value, StatusValue):
        return value
    return StatusValue(str(value).strip().lower())


def is_completed(worship: Worship, entry: Entry | None) -> bool:
    """Aturan "terlaksana" sesuai tipe isian."""

    if not has_record(entry):
        return False

    value = entry.value
    if worship.kind is EntryKind.CHECK:
        return bool(value)

    if worship.kind is EntryKind.NUMBER:
        try:
            amount = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return False
        target = float(worship.target) if worship.target is not None else 0.0
        return amount >= target if target > 0 else amount > 0

    if worship.kind is EntryKind.STATUS:
        return _as_status(value) is not StatusValue.BELUM

    raise ValueError(f"Tipe isian tidak dikenal: {worship.kind!r}")


def _index(entries: Iterable[Entry]) -> dict[tuple[int, date], Entry]:
    return {(entry.worship_id, entry.day): entry for entry in entries}


def compute_daily(
    day: date,
    worships: Iterable[Worship],
    entries: Iterable[Entry],
) -> DailySummary:
    """Rekap satu tanggal."""

    index = _index(entries)
    progress: list[WorshipProgress] = []

    for worship in worships:
        if not is_active(worship, day):
            continue
        entry = index.get((worship.id, day))
        completed = is_completed(worship, entry)
        partial = has_record(entry) and not completed
        progress.append(
            WorshipProgress(
                worship_id=worship.id,
                name=worship.name,
                completed=int(completed),
                partial=int(partial),
                expected=1,
            )
        )

    completed = sum(item.completed for item in progress)
    expected = len(progress)
    any_record = any(item.completed or item.partial for item in progress)

    if expected == 0 or not any_record:
        state = DayState.EMPTY
    elif completed == expected:
        state = DayState.FULL
    else:
        state = DayState.PARTIAL

    return DailySummary(
        day=day,
        state=state,
        completed=completed,
        expected=expected,
        per_worship=tuple(progress),
    )


def classify_day(
    day: date,
    worships: Iterable[Worship],
    entries: Iterable[Entry],
) -> DayState:
    """Kelompokkan hari menjadi kosong / sebagian / penuh."""

    return compute_daily(day, worships, entries).state


def _last_day(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - timedelta(days=1)


def _iter_days(start: date, end: date) -> Iterator[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _iter_periods(
    start: date,
    end: date,
    granularity: str,
) -> Iterator[tuple[str, date, date]]:
    if granularity == "day":
        for day in _iter_days(start, end):
            yield day.isoformat(), day, day
        return

    if granularity not in {"month", "year"}:
        raise ValueError("granularity harus 'day', 'month', atau 'year'")

    cursor = date(start.year, start.month, 1) if granularity == "month" else date(start.year, 1, 1)
    while cursor <= end:
        if granularity == "month":
            period_end = _last_day(cursor.year, cursor.month)
            key = f"{cursor.year:04d}-{cursor.month:02d}"
            next_cursor = date(cursor.year + 1, 1, 1) if cursor.month == 12 else date(cursor.year, cursor.month + 1, 1)
        else:
            period_end = date(cursor.year, 12, 31)
            key = f"{cursor.year:04d}"
            next_cursor = date(cursor.year + 1, 1, 1)

        yield key, max(start, cursor), min(end, period_end)
        cursor = next_cursor


def compute_range(
    start: date,
    end: date,
    worships: Iterable[Worship],
    entries: Iterable[Entry],
    granularity: str = "month",
) -> tuple[PeriodSummary, ...]:
    """Hitung ringkasan per hari, bulan, atau tahun dalam rentang tertutup.

    ``completed_days`` menghitung hari yang **penuh** (semua ibadah aktif
    terlaksana). ``partial_days`` menghitung hari yang ada catatannya tetapi
    belum lengkap. Ibadah arsip sudah difilter lewat ``is_active``.
    """

    if end < start:
        raise ValueError("end tidak boleh lebih awal dari start")

    # Materikan sekali supaya generator bisa dipakai berulang kali.
    worship_list = tuple(worships)
    entry_list = tuple(entries)
    results: list[PeriodSummary] = []

    for key, period_start, period_end in _iter_periods(start, end, granularity):
        totals: dict[int, WorshipProgress] = {
            worship.id: WorshipProgress(
                worship_id=worship.id,
                name=worship.name,
                completed=0,
                partial=0,
                expected=0,
            )
            for worship in worship_list
        }
        completed_days = 0
        partial_days = 0
        expected_days = 0

        for day in _iter_days(period_start, period_end):
            daily = compute_daily(day, worship_list, entry_list)
            if daily.expected == 0:
                continue
            expected_days += 1
            if daily.state is DayState.FULL:
                completed_days += 1
            elif daily.state is DayState.PARTIAL:
                partial_days += 1

            for item in daily.per_worship:
                previous = totals[item.worship_id]
                totals[item.worship_id] = WorshipProgress(
                    worship_id=item.worship_id,
                    name=item.name,
                    completed=previous.completed + item.completed,
                    partial=previous.partial + item.partial,
                    expected=previous.expected + item.expected,
                )

        if expected_days == 0:
            state = DayState.EMPTY
        elif completed_days == expected_days:
            state = DayState.FULL
        else:
            state = DayState.PARTIAL

        results.append(
            PeriodSummary(
                key=key,
                start=period_start,
                end=period_end,
                state=state,
                completed_days=completed_days,
                partial_days=partial_days,
                expected_days=expected_days,
                per_worship=tuple(
                    item for item in totals.values() if item.expected > 0
                ),
            )
        )

    return tuple(results)


def compute_yearly_series(
    year: int,
    worships: Iterable[Worship],
    entries: Iterable[Entry],
) -> tuple[YearPoint, ...]:
    """Data 12 titik untuk garis tren tahunan."""

    points: list[YearPoint] = []
    for month in range(1, 13):
        summary = compute_range(
            date(year, month, 1),
            _last_day(year, month),
            worships,
            entries,
            granularity="month",
        )[0]
        points.append(
            YearPoint(
                month=month,
                completed_days=summary.completed_days,
                expected_days=summary.expected_days,
            )
        )
    return tuple(points)


def describe_completion(completed: int, expected: int) -> str:
    """Kalimat netral; sengaja tidak memakai 'gagal' atau persentase."""

    if expected <= 0:
        return "Tidak ada ibadah aktif pada rentang ini"
    return f"Terlaksana {completed} dari {expected} hari"
