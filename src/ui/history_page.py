"""Halaman Riwayat: tren harian, bulanan, dan tahunan.

Kalender bulanan tetap punya halaman tersendiri (``CalendarPage``). Klik bulan
pada garis tren tahunan membuka Kalender lewat callback. Mode Bulanan di sini
adalah statistik per hari dalam satu bulan, bukan pengganti Kalender.

Penanda hari memakai simbol dan teks, bukan warna saja. Setiap garis memakai
``TrendLine`` dengan alternatif teks agar tetap bisa dibaca pembaca layar.
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
    compute_day_series,
    compute_month_series,
    compute_yearly_series,
    describe_completion,
    describe_daily_completion,
)
from .a11y import set_accessible_label
from .history_common import (
    ALL_FILTER,
    BULAN,
    STATE_SYMBOL,
    STATE_TEXT,
    FilterKey,
    OpenDayCallback,
    ToastCallback,
    apply_state_class,
    clear_list,
    format_day,
    format_entry_detail,
    last_day,
    shift_month,
    shift_year,
)
from .trend_line import MONTH_NAMES, TrendLine

__all__ = ["HistoryPage"]

OpenCalendarCallback = Callable[[date], None]


class HistoryPage(Gtk.Box):
    """Riwayat dengan pengalih Harian/Bulanan/Tahunan."""

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
        self._anchor = date.today()  # dipakai Bulanan dan Tahunan
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
        for label, name in (
            ("Harian", "day"),
            ("Rincian bulan", "month"),
            ("Tahunan", "year"),
        ):
            group.add(Adw.Toggle(label=label, name=name))
        group.set_active_name("day")
        group.set_tooltip_text("Simbol: ○ kosong · ◐ sebagian · ● penuh")
        group.connect("notify::active-name", self._on_mode_changed)
        self._toggle = group

        toggle_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        toggle_row.set_halign(Gtk.Align.CENTER)
        toggle_row.set_margin_top(12)
        toggle_row.append(group)
        self.append(toggle_row)

        # Navigasi periode dan filter berbagi satu baris supaya halaman tidak
        # menumpuk empat baris kontrol sebelum grafik pertama.
        nav = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        nav.set_margin_start(12)
        nav.set_margin_end(12)
        nav.set_margin_top(6)
        nav.set_margin_bottom(6)

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
        self._period_button.add_css_class("ih-quick")
        self._period_button.connect("clicked", lambda *_: self.go_current())
        nav.append(self._period_button)

        self._filter_dropdown = Gtk.DropDown()
        self._filter_dropdown.set_hexpand(False)
        self._filter_dropdown.connect("notify::selected", self._on_filter_changed)
        nav.append(self._filter_dropdown)

        archive = Gtk.CheckButton(label="Arsip")
        archive.set_tooltip_text(
            "Sertakan ibadah dan kebiasaan yang sudah diarsipkan"
        )
        archive.connect("toggled", self._on_archive_toggled)
        nav.append(archive)

        self.append(nav)

    def _build_views(self) -> None:
        self._views = Gtk.Stack()
        self._views.set_hexpand(True)
        self._views.set_vexpand(True)
        self._views.add_named(self._scrollable(self._build_day_view()), "day")
        self._views.add_named(self._scrollable(self._build_month_view()), "month")
        self._views.add_named(self._scrollable(self._build_year_view()), "year")
        self._views.set_visible_child_name("day")
        self.append(self._views)

    @staticmethod
    def _scrollable(child: Gtk.Widget) -> Gtk.ScrolledWindow:
        """Beri gulir per halaman supaya tinggi tiap mode berdiri sendiri.

        Sebelumnya satu ScrolledWindow membungkus seluruh Gtk.Stack. Karena
        Stack memakai ukuran anak tertinggi, mode tahunan tetap bisa digulir
        ke ruang kosong sepanjang daftar pada mode harian.
        """

        scrolled = Gtk.ScrolledWindow(vexpand=True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_child(child)
        return scrolled

    def _trend_card(
        self, title: str, hint: str, trend: TrendLine
    ) -> Gtk.Box:
        """Bungkus garis tren dengan judul dan petunjuk yang konsisten."""

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.add_css_class("ih-card")
        card.set_vexpand(True)

        heading = Gtk.Label(label=title)
        heading.set_xalign(0)
        heading.add_css_class("ih-section-title")
        card.append(heading)

        trend.add_css_class("ih-tren")
        trend.set_vexpand(True)
        card.append(trend)

        note = Gtk.Label(label=hint)
        note.set_xalign(0)
        note.set_wrap(True)
        note.add_css_class("ih-hint")
        card.append(note)
        return card

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

        self._recent_trend = TrendLine()
        self._recent_trend.connect(
            "point-activated", self._on_recent_point_activated
        )
        box.append(
            self._trend_card(
                "Tren 30 hari terakhir",
                "Klik titik untuk membuka tanggal itu di Hari Ini.",
                self._recent_trend,
            )
        )

        self._day_detail = Gtk.ListBox()
        self._day_detail.add_css_class("boxed-list")
        self._day_detail.set_selection_mode(Gtk.SelectionMode.NONE)
        box.append(self._day_detail)

        note_title = Gtk.Label(label="Catatan harian")
        note_title.set_xalign(0)
        note_title.add_css_class("ih-section-title")
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

    def _build_month_view(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(18)
        box.set_margin_end(18)
        box.set_margin_top(6)
        box.set_margin_bottom(18)

        self._month_state = Gtk.Label(label="")
        self._month_state.set_xalign(0)
        self._month_state.add_css_class("dim-label")
        box.append(self._month_state)

        self._month_trend = TrendLine()
        self._month_trend.connect(
            "point-activated", self._on_month_point_activated
        )
        box.append(
            self._trend_card(
                "Tren harian dalam bulan ini",
                "Satu titik untuk setiap tanggal. Klik untuk membuka hari itu.",
                self._month_trend,
            )
        )

        detail_title = Gtk.Label(label="Rincian per hari")
        detail_title.set_xalign(0)
        detail_title.add_css_class("ih-section-title")
        box.append(detail_title)

        self._month_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._month_text.add_css_class("dim-label")
        box.append(self._month_text)
        return box

    def _build_year_view(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(18)
        box.set_margin_end(18)
        box.set_margin_top(6)
        box.set_margin_bottom(18)

        self._trend = TrendLine()
        box.append(
            self._trend_card(
                "Tren tahunan per bulan",
                "Satu titik untuk setiap bulan. Klik untuk membuka Kalender.",
                self._trend,
            )
        )

        detail_title = Gtk.Label(label="Rincian per bulan")
        detail_title.set_xalign(0)
        detail_title.add_css_class("ih-section-title")
        box.append(detail_title)

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
        labels = ["Semua ibadah & kebiasaan"]
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
        """Terima ``day``, ``month``, dan ``year``."""

        if mode not in {"day", "month", "year"}:
            return
        self._mode = mode
        self._toggle.set_active_name(mode)
        self._views.set_visible_child_name(mode)
        self._sync_period_button()
        self.refresh()

    def _on_mode_changed(self, *_args: object) -> None:
        mode = self._toggle.get_active_name()
        if mode not in {"day", "month", "year"}:
            return
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
            self._anchor = shift_month(self._anchor, direction)
            self._day = self._anchor
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

    def _on_recent_point_activated(
        self, _widget: TrendLine, index: int
    ) -> None:
        """Buka tanggal pada tren 30 hari di Hari Ini."""

        start = self._day - timedelta(days=29)
        if 0 <= index < 30:
            self._on_open_day(start + timedelta(days=index))

    def _on_month_point_activated(self, _widget: TrendLine, index: int) -> None:
        """Buka tanggal pada tren bulanan di Hari Ini."""

        last = last_day(self._anchor.year, self._anchor.month)
        if 0 <= index < last:
            day = date(self._anchor.year, self._anchor.month, index + 1)
            self._day = day
            self._on_open_day(day)

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
            + describe_daily_completion(summary.completed, summary.expected)
        )
        apply_state_class(self._day_state, summary.state)
        set_accessible_label(self._day_state, self._day_state.get_label())

        start = self._day - timedelta(days=29)
        points = compute_day_series(
            start, self._day, worships, self._entries(start, self._day)
        )
        labels: list[str] = []
        cursor = start
        while cursor <= self._day:
            labels.append(f"{cursor.day} {BULAN[cursor.month - 1][:3]}")
            cursor += timedelta(days=1)
        self._recent_trend.set_points(
            points,
            labels=labels,
            title=f"Tren 30 hari hingga {format_day(self._day)}",
        )

        note = self._repo.get_daily_note(self._day).text
        self._day_note_text.set_label(note or "Belum ada catatan harian.")
        set_accessible_label(self._day_note_text, self._day_note_text.get_label())

        clear_list(self._day_detail)
        if not summary.per_worship:
            row = Adw.ActionRow(title="Tidak ada kegiatan aktif")
            row.set_subtitle(
                "Tambahkan ibadah atau kebiasaan, atau ubah filter untuk melihat rekap."
            )
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

    def _refresh_month(self) -> None:
        year = self._anchor.year
        month = self._anchor.month
        first = date(year, month, 1)
        last = last_day(year, month)
        worships = self._worships()
        points = compute_month_series(
            year, month, worships, self._entries(first, date(year, month, last))
        )

        completed = sum(point.completed_days for point in points)
        expected = sum(point.expected_days for point in points)
        self._month_state.set_label(describe_completion(completed, expected))
        set_accessible_label(self._month_state, self._month_state.get_label())
        self._month_trend.set_points(
            points,
            labels=[str(day) for day in range(1, last + 1)],
            title=f"Tren harian {BULAN[month - 1]} {year}",
        )

        clear_list(self._month_text)
        for index, point in enumerate(points):
            detail = (
                describe_completion(point.completed_days, point.expected_days)
                if point.has_data
                else "tidak ada kegiatan aktif"
            )
            row = Gtk.Label(label=f"Hari {index + 1}: {detail}")
            row.set_xalign(0)
            self._month_text.append(row)

    def _refresh_year(self) -> None:
        clear_list(self._year_text)
        worships = self._worships()
        entries = self._entries(
            date(self._anchor.year, 1, 1), date(self._anchor.year, 12, 31)
        )
        points = compute_yearly_series(self._anchor.year, worships, entries)
        self._trend.set_points(
            points,
            labels=MONTH_NAMES,
            title=f"Tren tahunan {self._anchor.year}",
        )

        for point in points:
            label = MONTH_NAMES[point.month - 1]
            detail = (
                describe_completion(point.completed_days, point.expected_days)
                if point.has_data
                else "tidak ada kegiatan aktif"
            )
            row = Gtk.Label(label=f"{label}: {detail}")
            row.set_xalign(0)
            self._year_text.append(row)
