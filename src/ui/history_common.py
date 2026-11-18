"""Helper tampilan bersama untuk Riwayat, Kalender, dan Histori Catatan.

Modul ini hanya berisi format teks, simbol status, dan utilitas kecil supaya
halaman-halaman tersebut tidak mengulang kode yang sama. Penanda status tetap
memakai simbol beserta teks, bukan warna saja.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk

from ..logic.repository import EntryRecord, WorshipRecord
from ..logic.statistics import DayState, StatusValue
from .trend_line import MONTH_NAMES

__all__ = [
    "HARI",
    "BULAN",
    "HARI_SINGKAT",
    "STATE_SYMBOL",
    "STATE_TEXT",
    "STATE_CLASS",
    "FilterKey",
    "ALL_FILTER",
    "OpenDayCallback",
    "ToastCallback",
    "format_day",
    "format_entry_detail",
    "last_day",
    "shift_month",
    "shift_year",
    "month_range",
    "apply_state_class",
    "clear_list",
    "clear_grid",
]

HARI = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")
BULAN = MONTH_NAMES
HARI_SINGKAT = ("Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min")

STATE_SYMBOL = {
    DayState.EMPTY: "○",
    DayState.PARTIAL: "◐",
    DayState.FULL: "●",
}
STATE_TEXT = {
    DayState.EMPTY: "Kosong",
    DayState.PARTIAL: "Sebagian",
    DayState.FULL: "Penuh",
}
STATE_CLASS = {
    DayState.EMPTY: "state-kosong",
    DayState.PARTIAL: "state-sebagian",
    DayState.FULL: "state-penuh",
}

FilterKey = tuple[str, int | None]
ALL_FILTER: FilterKey = ("all", None)

OpenDayCallback = Callable[[date], None]
ToastCallback = Callable[[str, str | None, Callable[[], None] | None], None]


def format_day(day: date) -> str:
    return f"{HARI[day.weekday()]}, {day.day} {BULAN[day.month - 1]} {day.year}"


def format_entry_detail(entry: EntryRecord, worship: WorshipRecord | None) -> str:
    """Ringkas nilai, jam, dan catatan per ibadah untuk tampilan riwayat."""

    parts: list[str] = []
    value = entry.value
    if value is True:
        parts.append("Selesai")
    elif value is False:
        parts.append("Belum")
    elif isinstance(value, (int, float)):
        amount = f"{value:g}"
        if worship is not None:
            if worship.unit:
                amount = f"{amount} {worship.unit}"
            if worship.target:
                amount = f"{amount} / target {worship.target:g}"
        parts.append(amount)
    elif isinstance(value, StatusValue):
        parts.append(value.value.replace("-", " ").capitalize())
    elif value is not None:
        parts.append(str(value))

    if entry.time:
        parts.append(f"jam {entry.time}")
    if entry.note:
        parts.append(entry.note)
    return " · ".join(parts) or "Tanpa keterangan tambahan"


def last_day(year: int, month: int) -> int:
    if month == 12:
        return (date(year + 1, 1, 1) - timedelta(days=1)).day
    return (date(year, month + 1, 1) - timedelta(days=1)).day


def shift_month(day: date, months: int) -> date:
    total = day.year * 12 + (day.month - 1) + months
    year, month_index = divmod(total, 12)
    month = month_index + 1
    return date(year, month, min(day.day, last_day(year, month)))


def shift_year(day: date, years: int) -> date:
    year = day.year + years
    return day.replace(year=year, day=min(day.day, last_day(year, day.month)))


def month_range(day: date) -> tuple[date, date]:
    """Rentang tanggal tertutup untuk bulan tempat ``day`` berada."""

    first = date(day.year, day.month, 1)
    return first, date(day.year, day.month, last_day(day.year, day.month))


def apply_state_class(widget: Gtk.Widget, state: DayState) -> None:
    for css_class in STATE_CLASS.values():
        widget.remove_css_class(css_class)
    widget.add_css_class(STATE_CLASS[state])


def clear_list(container: Gtk.Widget) -> None:
    child = container.get_first_child()
    while child is not None:
        following = child.get_next_sibling()
        container.remove(child)
        child = following


def clear_grid(container: Gtk.Widget) -> None:
    child = container.get_first_child()
    while child is not None:
        following = child.get_next_sibling()
        container.remove(child)
        child = following
