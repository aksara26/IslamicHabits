"""Halaman Riwayat: tampilan harian dan tahunan.

Kalender bulanan sudah dipindah ke halaman tersendiri (``CalendarPage``).
Klik bulan pada garis tren tahunan membuka Kalender lewat callback, bukan
lagi mengganti mode di halaman ini.

Penanda hari memakai simbol dan teks, bukan warna saja. Garis tahunan memakai
``TrendLine`` yang sudah ada, dengan alternatif teks 12 bulan di bawahnya.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from ..logic.repository import Repository, WorshipRecord
from ..logic.statistics import (
    DayState,
    Worship,
    compute_daily,
    compute_yearly_series,
    describe_completion,
)
from .a11y import set_accessible_label
from .history_common import (
    ALL_FILTER,
    STATE_SYMBOL,
    STATE_TEXT,
    FilterKey,
    OpenDayCallback,
    ToastCallback,
    apply_state_class,
    clear_list,
    format_day,
    format_entry_detail,
    shift_year,
)
from .trend_line import MONTH_NAMES, TrendLine

__all__ = ["HistoryPage"]

OpenCalendarCallback = Callable[[date], None]


class HistoryPage(Gtk.Box):
    """Riwayat dengan pengalih Harian/Tahunan."""

    def __init__(
        self,
        repository: Repository,
        *,
        on_open_day: OpenDayCallback,
        on_open_calendar: OpenCalendarCallback | None = None,
        on_toast: ToastCallback | None = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._repo = repository
        self._on_open_day = on_open_day
        self._on_open_calendar = on_open_calendar or (lambda _day: None)
        self._on_toast = on_toast

        self._mode = "day"
        self._day = date.today()
        self._anchor = date.today()  # dipakai Tahunan
        self._filter_key: FilterKey = ALL_FILTER
        self._filter_keys: list[FilterKey] = [ALL_FILTER]
        self._show_archived = False
        self._syncing_filter = False

        self._build_controls()
        self._build_views()
        self.refresh()

    # -- konstruksi ------------------------------------------------------

    def _build_controls(self) -> None:
        group = Adw.ToggleGroup()
        for label, name in (("Harian", "day"), ("Tahunan", "year")):
            group.add(Adw.Toggle(label=label, name=name))
        group.set_active_name("day")
        group.connect("notify::active-name", self._on_mode_changed)
        self._toggle = group

        toggle_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        toggle_row.set_halign(Gtk.Align.CENTER)
        toggle_row.set_margin_top(12)
        toggle_row.append(group)
        self.append(toggle_row)

        nav = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        nav.set_margin_start(12)
        nav.set_margin_end(12)
        nav.set_margin_top(6)

        self._previous = Gtk.Button.new_from_icon_name("go-previous-symbolic")
        self._previous.set_tooltip_text("Periode sebelumnya")
        self._previous.connect("clicked", lambda *_: self._shift(-1))
        nav.append(self._previous)

        self._title = Gtk.Label(label="")
        self._title.set_hexpand(True)
        self._title.set_xalign(0.5)
        self._title.add_css_class("dim-label")
        nav.append(self._title)

        self._next = Gtk.Button.new_from_icon_name("go-next-symbolic")
        self._next.set_tooltip_text("Periode berikutnya")
        self._next.connect("clicked", lambda *_: self._shift(1))
        nav.append(self._next)

        self._period_button = Gtk.Button(label="Hari ini")
        self._period_button.connect("clicked", lambda *_: self.go_current())
        nav.append(self._period_button)
        self.append(nav)

        filters = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        filters.set_margin_start(12)
        filters.set_margin_end(12)
        filters.set_margin_top(6)
        filters.set_margin_bottom(6)

        self._filter_dropdown = Gtk.DropDown()
        self._filter_dropdown.connect("notify::selected", self._on_filter_changed)
        filters.append(self._filter_dropdown)

        archive = Gtk.CheckButton(label="Tampilkan arsip")
        archive.set_tooltip_text("Sertakan ibadah yang sudah diarsipkan")
        archive.connect("toggled", self._on_archive_toggled)
        filters.append(archive)

        help_label = Gtk.Label(label="Simbol: ○ kosong · ◐ sebagian · ● penuh")
        help_label.set_hexpand(True)
        help_label.set_xalign(1)
        help_label.add_css_class("dim-label")
        filters.append(help_label)
        self.append(filters)

    def _build_views(self) -> None:
        self._views = Gtk.Stack()
        self._views.set_hexpand(True)
        self._views.set_vexpand(True)
        self._views.add_named(self._build_day_view(), "day")
        self._views.add_named(self._build_year_view(), "year")
        self._views.set_visible_child_name("day")

        scrolled = Gtk.ScrolledWindow(vexpand=True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_child(self._views)
        self.append(scrolled)

    def _build_day_view(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(18)
        box.set_margin_end(18)
        box.set_margin_top(6)
        box.set_margin_bottom(18)

        self._day_state = Gtk.Label(label="")
        self._day_state.set_xalign(0)
        self._day_state.add_css_class("dim-label")
        box.append(self._day_state)

        self._day_detail = Gtk.ListBox()
        self._day_detail.add_css_class("boxed-list")
        self._day_detail.set_selection_mode(Gtk.SelectionMode.NONE)
        box.append(self._day_detail)

        note_title = Gtk.Label(label="Catatan harian")
        note_title.set_xalign(0)
        note_title.add_css_class("dim-label")
        box.append(note_title)
        self._day_note_text = Gtk.Label(label="")
        self._day_note_text.set_xalign(0)
        self._day_note_text.set_wrap(True)
        self._day_note_text.add_css_class("dim-label")
        box.append(self._day_note_text)

        open_button = Gtk.Button(label="Lihat dan isi di Hari Ini")
        open_button.set_halign(Gtk.Align.START)
        open_button.connect("clicked", lambda *_: self._on_open_day(self._day))
        box.append(open_button)
        return box

    def _build_year_view(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(18)
        box.set_margin_end(18)
        box.set_margin_top(6)
        box.set_margin_bottom(18)

        self._trend = TrendLine()
        self._trend.connect("month-activated", self._on_month_activated)
        box.append(self._trend)

        self._year_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._year_text.add_css_class("dim-label")
        box.append(self._year_text)
        return box

    # -- data ------------------------------------------------------------

    def _worship_records(self) -> tuple[WorshipRecord, ...]:
        records = self._repo.list_worships(include_archived=self._show_archived)
        kind, value = self._filter_key
        if kind == "category":
            records = tuple(item for item in records if item.category_id == value)
        elif kind == "worship":
            records = tuple(item for item in records if item.id == value)
        return records

    def _worships(self) -> tuple[Worship, ...]:
        return tuple(item.to_statistics() for item in self._worship_records())

    def _entries(self, start: date, end: date):
        allowed = {item.id for item in self._worships()}
        return tuple(
            item.to_statistics()
            for item in self._repo.list_entries(start=start, end=end)
            if item.worship_id in allowed
        )

    def _sync_filter_model(self) -> None:
        keys: list[FilterKey] = [ALL_FILTER]
        labels = ["Semua ibadah"]
        for category in self._repo.list_categories():
            keys.append(("category", category.id))
            labels.append(f"Kategori: {category.name}")
        for worship in self._repo.list_worships(include_archived=True):
            keys.append(("worship", worship.id))
            labels.append(worship.name)

        self._filter_keys = keys
        self._syncing_filter = True
        try:
            self._filter_dropdown.set_model(Gtk.StringList.new(labels))
            try:
                index = keys.index(self._filter_key)
            except ValueError:
                self._filter_key = ALL_FILTER
                index = 0
            self._filter_dropdown.set_selected(index)
        finally:
            self._syncing_filter = False

    # -- mode & navigasi -------------------------------------------------

    def set_mode(self, mode: str) -> None:
        """Terima hanya ``day`` dan ``year``; Kalender punya halaman sendiri."""

        if mode not in {"day", "year"}:
            return
        self._mode = mode
        self._toggle.set_active_name(mode)
        self._views.set_visible_child_name(mode)
        self._sync_period_button()
        self.refresh()

    def _on_mode_changed(self, *_args: object) -> None:
        mode = self._toggle.get_active_name()
        if mode not in {"day", "year"}:
            return
        self._mode = mode
        self._views.set_visible_child_name(mode)
        self._sync_period_button()
        self.refresh()

    def _sync_period_button(self) -> None:
        labels = {"day": "Hari ini", "year": "Tahun ini"}
        self._period_button.set_label(labels[self._mode])

    def go_current(self) -> None:
        today = date.today()
        self._day = today
        self._anchor = today
        self.refresh()

    def go_to_day(self, day: date) -> None:
        self._day = day
        self._anchor = day
        self.refresh()

    def _shift(self, direction: int) -> None:
        if self._mode == "day":
            self._day += timedelta(days=direction)
            self._anchor = self._day
        else:
            self._anchor = shift_year(self._anchor, direction)
        self.refresh()

    def _on_filter_changed(self, *_args: object) -> None:
        if self._syncing_filter:
            return
        index = self._filter_dropdown.get_selected()
        if 0 <= index < len(self._filter_keys):
            self._filter_key = self._filter_keys[index]
            self.refresh()

    def _on_archive_toggled(self, button: Gtk.CheckButton) -> None:
        self._show_archived = button.get_active()
        self._sync_filter_model()
        self.refresh()

    def _on_month_activated(self, _widget: TrendLine, month: int) -> None:
        """Buka Kalender pada bulan yang dipilih dari tren tahunan."""

        self._anchor = date(self._anchor.year, month, 1)
        self._day = self._anchor
        self._on_open_calendar(self._anchor)

    # -- penyegaran ------------------------------------------------------

    def refresh(self) -> None:
        self._sync_filter_model()
        titles = {
            "day": format_day(self._day),
            "year": str(self._anchor.year),
        }
        self._title.set_label(titles[self._mode])
        if self._mode == "day":
            self._refresh_day()
        else:
            self._refresh_year()

    def _refresh_day(self) -> None:
        worships = self._worships()
        entries = self._entries(self._day, self._day)
        summary = compute_daily(self._day, worships, entries)
        symbol = STATE_SYMBOL[summary.state]
        self._day_state.set_label(
            f"{symbol} {STATE_TEXT[summary.state]} — "
            f"Terlaksana {summary.completed} dari {summary.expected} ibadah"
        )
        apply_state_class(self._day_state, summary.state)
        set_accessible_label(self._day_state, self._day_state.get_label())

        note = self._repo.get_daily_note(self._day).text
        self._day_note_text.set_label(note or "Belum ada catatan harian.")
        set_accessible_label(self._day_note_text, self._day_note_text.get_label())

        clear_list(self._day_detail)
        if not summary.per_worship:
            row = Adw.ActionRow(title="Tidak ada ibadah aktif")
            row.set_subtitle("Tambahkan ibadah atau ubah filter untuk melihat rekap.")
            self._day_detail.append(row)
            return

        records = {item.id: item for item in self._worship_records()}
        entry_map = {
            item.worship_id: item
            for item in self._repo.list_entries(start=self._day, end=self._day)
        }
        for item in summary.per_worship:
            label = "Terlaksana" if item.completed else (
                "Sebagian" if item.partial else "Belum ada catatan"
            )
            entry = entry_map.get(item.worship_id)
            if entry is not None:
                label += f" — {format_entry_detail(entry, records.get(item.worship_id))}"
            row = Adw.ActionRow(title=item.name, subtitle=label)
            state = DayState.FULL if item.completed else (
                DayState.PARTIAL if item.partial else DayState.EMPTY
            )
            mark = Gtk.Label(label=STATE_SYMBOL[state])
            apply_state_class(mark, state)
            row.add_suffix(mark)
            self._day_detail.append(row)

    def _refresh_year(self) -> None:
        clear_list(self._year_text)
        worships = self._worships()
        entries = self._entries(
            date(self._anchor.year, 1, 1), date(self._anchor.year, 12, 31)
        )
        points = compute_yearly_series(self._anchor.year, worships, entries)
        self._trend.set_points(points)

        for point in points:
            label = MONTH_NAMES[point.month - 1]
            detail = (
                describe_completion(point.completed_days, point.expected_days)
                if point.has_data
                else "tidak ada ibadah aktif"
            )
            row = Gtk.Label(label=f"{label}: {detail}")
            row.set_xalign(0)
            self._year_text.append(row)
