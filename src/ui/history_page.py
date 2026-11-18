"""Halaman Riwayat: tampilan harian, bulanan, dan tahunan.

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

from ..logic.repository import Repository
from ..logic.statistics import (
    DayState,
    Worship,
    compute_daily,
    compute_range,
    compute_yearly_series,
    describe_completion,
)
from .a11y import set_accessible_label
from .trend_line import MONTH_NAMES, TrendLine

__all__ = ["HistoryPage"]

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

OpenDayCallback = Callable[[date], None]
ToastCallback = Callable[[str, str | None, Callable[[], None] | None], None]

FilterKey = tuple[str, int | None]

_ALL_FILTER: FilterKey = ("all", None)


def _format_day(day: date) -> str:
    return f"{HARI[day.weekday()]}, {day.day} {BULAN[day.month - 1]} {day.year}"


def _shift_month(day: date, months: int) -> date:
    total = day.year * 12 + (day.month - 1) + months
    year, month_index = divmod(total, 12)
    month = month_index + 1
    last = (date(year + 1, 1, 1) - timedelta(days=1)) if month == 12 else date(year, month + 1, 1) - timedelta(days=1)
    return date(year, month, min(day.day, last.day))


class HistoryPage(Gtk.Box):
    """Riwayat dengan pengalih Harian/Bulanan/Tahunan."""

    def __init__(
        self,
        repository: Repository,
        *,
        on_open_day: OpenDayCallback,
        on_toast: ToastCallback,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._repo = repository
        self._on_open_day = on_open_day
        self._on_toast = on_toast

        self._mode = "day"
        self._day = date.today()
        self._anchor = date.today()  # dipakai Bulanan & Tahunan
        self._filter_key: FilterKey = _ALL_FILTER
        self._filter_keys: list[FilterKey] = [_ALL_FILTER]
        self._show_archived = False
        self._syncing_filter = False

        self._build_controls()
        self._build_views()
        self.refresh()

    # -- konstruksi ------------------------------------------------------

    def _build_controls(self) -> None:
        group = Adw.ToggleGroup()
        for label, name in (
            ("Harian", "day"),
            ("Bulanan", "month"),
            ("Tahunan", "year"),
        ):
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

        help_label = Gtk.Label(label="")
        help_label.set_hexpand(True)
        help_label.set_xalign(1)
        help_label.add_css_class("dim-label")
        help_label.set_label("Simbol: ○ kosong · ◐ sebagian · ● penuh")
        filters.append(help_label)
        self.append(filters)

    def _build_views(self) -> None:
        self._views = Gtk.Stack()
        self._views.set_hexpand(True)
        self._views.set_vexpand(True)
        self._views.add_named(self._build_day_view(), "day")
        self._views.add_named(self._build_month_view(), "month")
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

        open_button = Gtk.Button(label="Lihat dan isi di Hari Ini")
        open_button.set_halign(Gtk.Align.START)
        open_button.connect("clicked", lambda *_: self._on_open_day(self._day))
        box.append(open_button)
        return box

    def _build_month_view(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(18)
        box.set_margin_end(18)
        box.set_margin_top(6)
        box.set_margin_bottom(18)

        self._month_grid = Gtk.Grid()
        self._month_grid.set_column_spacing(4)
        self._month_grid.set_row_spacing(4)
        self._month_grid.set_column_homogeneous(True)
        self._month_grid.set_halign(Gtk.Align.FILL)
        box.append(self._month_grid)

        month_title = Gtk.Label(label="Ringkasan per ibadah")
        month_title.set_xalign(0)
        month_title.add_css_class("dim-label")
        box.append(month_title)

        self._month_summary = Gtk.ListBox()
        self._month_summary.add_css_class("boxed-list")
        self._month_summary.set_selection_mode(Gtk.SelectionMode.NONE)
        box.append(self._month_summary)
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

    def _worships(self) -> tuple[Worship, ...]:
        records = self._repo.list_worships(include_archived=self._show_archived)
        kind, value = self._filter_key
        if kind == "category":
            records = tuple(item for item in records if item.category_id == value)
        elif kind == "worship":
            records = tuple(item for item in records if item.id == value)
        return tuple(item.to_statistics() for item in records)

    def _entries(self, start: date, end: date):
        allowed = {item.id for item in self._worships()}
        return tuple(
            item.to_statistics()
            for item in self._repo.list_entries(start=start, end=end)
            if item.worship_id in allowed
        )

    def _sync_filter_model(self) -> None:
        keys: list[FilterKey] = [_ALL_FILTER]
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
                self._filter_key = _ALL_FILTER
                index = 0
            self._filter_dropdown.set_selected(index)
        finally:
            self._syncing_filter = False

    # -- mode & navigasi -------------------------------------------------

    def set_mode(self, mode: str) -> None:
        if mode not in {"day", "month", "year"}:
            return
        self._mode = mode
        self._toggle.set_active_name(mode)
        self._views.set_visible_child_name(mode)
        self._sync_period_button()
        self.refresh()

    def _on_mode_changed(self, *_args: object) -> None:
        mode = self._toggle.get_active_name()
        self._mode = mode
        self._views.set_visible_child_name(mode)
        self._sync_period_button()
        self.refresh()

    def _sync_period_button(self) -> None:
        labels = {"day": "Hari ini", "month": "Bulan ini", "year": "Tahun ini"}
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
        elif self._mode == "month":
            self._anchor = _shift_month(self._anchor, direction)
            self._day = self._anchor
        else:
            self._anchor = self._anchor.replace(year=self._anchor.year + direction)
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
        self._anchor = date(self._anchor.year, month, 1)
        self._day = self._anchor
        self.set_mode("month")

    # -- penyegaran ------------------------------------------------------

    def refresh(self) -> None:
        self._sync_filter_model()
        titles = {
            "day": _format_day(self._day),
            "month": f"{BULAN[self._anchor.month - 1]} {self._anchor.year}",
            "year": str(self._anchor.year),
        }
        self._title.set_label(titles[self._mode])
        if self._mode == "day":
            self._refresh_day()
        elif self._mode == "month":
            self._refresh_month()
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
        self._apply_state_class(self._day_state, summary.state)
        set_accessible_label(self._day_state, self._day_state.get_label())

        self._clear_list(self._day_detail)
        if not summary.per_worship:
            row = Adw.ActionRow(title="Tidak ada ibadah aktif")
            row.set_subtitle("Tambahkan ibadah atau ubah filter untuk melihat rekap.")
            self._day_detail.append(row)
            return
        for item in summary.per_worship:
            label = "Terlaksana" if item.completed else (
                "Sebagian" if item.partial else "Belum ada catatan"
            )
            row = Adw.ActionRow(title=item.name, subtitle=label)
            state = DayState.FULL if item.completed else (
                DayState.PARTIAL if item.partial else DayState.EMPTY
            )
            mark = Gtk.Label(label=STATE_SYMBOL[state])
            self._apply_state_class(mark, state)
            row.add_suffix(mark)
            self._day_detail.append(row)

    @staticmethod
    def _apply_state_class(widget: Gtk.Widget, state: DayState) -> None:
        for css_class in STATE_CLASS.values():
            widget.remove_css_class(css_class)
        widget.add_css_class(STATE_CLASS[state])

    @staticmethod
    def _clear_list(container: Gtk.ListBox) -> None:
        child = container.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            container.remove(child)
            child = following

    @staticmethod
    def _clear_grid(container: Gtk.Grid) -> None:
        child = container.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            container.remove(child)
            child = following

    def _refresh_month(self) -> None:
        self._clear_grid(self._month_grid)
        self._clear_list(self._month_summary)

        year, month = self._anchor.year, self._anchor.month
        first = date(year, month, 1)
        days_in_month = (
            (date(year + 1, 1, 1) - timedelta(days=1))
            if month == 12
            else date(year, month + 1, 1) - timedelta(days=1)
        ).day
        worships = self._worships()
        entries = self._entries(first, date(year, month, days_in_month))
        states: dict[int, DayState] = {}
        for day_number in range(1, days_in_month + 1):
            states[day_number] = compute_daily(
                date(year, month, day_number), worships, entries
            ).state

        for column, label in enumerate(HARI_SINGKAT):
            header = Gtk.Label(label=label)
            header.add_css_class("dim-label")
            self._month_grid.attach(header, column, 0, 1, 1)

        start_column = first.weekday()
        for day_number in range(1, days_in_month + 1):
            index = start_column + day_number - 1
            state = states[day_number]
            button = Gtk.Button()
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            number = Gtk.Label(label=str(day_number))
            mark = Gtk.Label(label=STATE_SYMBOL[state])
            self._apply_state_class(mark, state)
            inner.append(number)
            inner.append(mark)
            button.set_child(inner)
            button.set_tooltip_text(
                f"{day_number} {BULAN[month - 1]}: {STATE_TEXT[state]}"
            )
            set_accessible_label(
                button, f"{day_number} {BULAN[month - 1]}, {STATE_TEXT[state]}"
            )
            captured_day = date(year, month, day_number)
            button.connect("clicked", self._on_calendar_day, captured_day)
            self._month_grid.attach(button, index % 7, index // 7 + 1, 1, 1)

        summary = compute_range(
            first, date(year, month, days_in_month), worships, entries, "month"
        )[0]
        for item in summary.per_worship:
            row = Adw.ActionRow(
                title=item.name,
                subtitle=describe_completion(item.completed, item.expected),
            )
            self._month_summary.append(row)
        if not summary.per_worship:
            row = Adw.ActionRow(title="Tidak ada ibadah aktif pada bulan ini")
            self._month_summary.append(row)

    def _on_calendar_day(self, _button: Gtk.Button, day: date) -> None:
        self.go_to_day(day)
        self.set_mode("day")

    def _refresh_year(self) -> None:
        child = self._year_text.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            self._year_text.remove(child)
            child = following
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
