"""Halaman Kalender: tampilan bulanan dengan detail capaian dan catatan.

Halaman ini dipindahkan dari mode bulanan ``HistoryPage`` supaya Kalender
punya entri navbar sendiri. Ia memakai helper yang sama dengan Riwayat agar
simbol status, format tanggal, dan filter tidak diduplikasi.
"""

from __future__ import annotations

from datetime import date
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from ..logic.repository import Repository, WorshipRecord
from ..logic.statistics import (
    Worship,
    compute_daily,
    compute_range,
    describe_completion,
    describe_daily_completion,
)
from .a11y import set_accessible_label
from .history_common import (
    ALL_FILTER,
    BULAN,
    HARI_SINGKAT,
    STATE_SYMBOL,
    STATE_TEXT,
    FilterKey,
    OpenDayCallback,
    ToastCallback,
    apply_state_class,
    clear_grid,
    clear_list,
    format_day,
    format_entry_detail,
    month_range,
    shift_month,
)

__all__ = ["CalendarPage"]

GoToMonthCallback = Callable[[date], None]


class CalendarPage(Gtk.Box):
    """Kalender bulan dengan panel detail hari terpilih."""

    def __init__(
        self,
        repository: Repository,
        *,
        on_open_day: OpenDayCallback,
        on_toast: ToastCallback | None = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._repo = repository
        self._on_open_day = on_open_day
        self._on_toast = on_toast

        today = date.today()
        self._anchor = today
        self._calendar_selected = today
        self._filter_key: FilterKey = ALL_FILTER
        self._filter_keys: list[FilterKey] = [ALL_FILTER]
        self._show_archived = False
        self._syncing_filter = False

        self._build_controls()
        self._build_content()
        self.refresh()

    # -- konstruksi ------------------------------------------------------

    def _build_controls(self) -> None:
        nav = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        nav.set_margin_start(12)
        nav.set_margin_end(12)
        nav.set_margin_top(12)
        nav.set_margin_bottom(6)

        previous = Gtk.Button.new_from_icon_name("go-previous-symbolic")
        previous.set_tooltip_text("Bulan sebelumnya")
        previous.connect("clicked", lambda *_: self._shift(-1))
        nav.append(previous)

        self._title = Gtk.Label(label="")
        self._title.set_hexpand(True)
        self._title.set_xalign(0.5)
        self._title.add_css_class("dim-label")
        nav.append(self._title)

        next_button = Gtk.Button.new_from_icon_name("go-next-symbolic")
        next_button.set_tooltip_text("Bulan berikutnya")
        next_button.connect("clicked", lambda *_: self._shift(1))
        nav.append(next_button)

        current = Gtk.Button(label="Bulan ini")
        current.connect("clicked", lambda *_: self.go_current())
        nav.append(current)
        self.append(nav)

        filters = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        filters.set_margin_start(12)
        filters.set_margin_end(12)
        filters.set_margin_bottom(6)

        self._filter_dropdown = Gtk.DropDown()
        self._filter_dropdown.connect("notify::selected", self._on_filter_changed)
        filters.append(self._filter_dropdown)

        archive = Gtk.CheckButton(label="Tampilkan arsip")
        archive.set_tooltip_text("Sertakan ibadah yang sudah diarsipkan")
        archive.connect("toggled", self._on_archive_toggled)
        filters.append(archive)

        help_label = Gtk.Label(label="Simbol: ○ kosong · ◐ sebagian · ● penuh · ✎ ada catatan")
        help_label.set_hexpand(True)
        help_label.set_xalign(1)
        help_label.set_wrap(True)
        help_label.set_max_width_chars(28)
        help_label.add_css_class("ih-hint")
        filters.append(help_label)
        self.append(filters)

    def _build_content(self) -> None:
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
        self._month_grid.add_css_class("ih-calendar-grid")
        box.append(self._month_grid)

        detail_title = Gtk.Label(label="Detail hari terpilih")
        detail_title.set_xalign(0)
        detail_title.add_css_class("ih-section-title")
        box.append(detail_title)

        self._calendar_detail_state = Gtk.Label(label="")
        self._calendar_detail_state.set_xalign(0)
        self._calendar_detail_state.set_wrap(True)
        box.append(self._calendar_detail_state)

        self._calendar_detail_list = Gtk.ListBox()
        self._calendar_detail_list.add_css_class("boxed-list")
        self._calendar_detail_list.set_selection_mode(Gtk.SelectionMode.NONE)
        box.append(self._calendar_detail_list)

        self._calendar_detail_note = Gtk.Label(label="")
        self._calendar_detail_note.set_xalign(0)
        self._calendar_detail_note.set_wrap(True)
        self._calendar_detail_note.add_css_class("dim-label")
        box.append(self._calendar_detail_note)

        open_selected = Gtk.Button(label="Isi hari ini di Hari Ini")
        open_selected.set_halign(Gtk.Align.START)
        open_selected.connect(
            "clicked", lambda *_: self._on_open_day(self._calendar_selected)
        )
        box.append(open_selected)

        month_title = Gtk.Label(label="Ringkasan per kegiatan")
        month_title.set_xalign(0)
        month_title.add_css_class("ih-section-title")
        box.append(month_title)

        self._month_summary = Gtk.ListBox()
        self._month_summary.add_css_class("boxed-list")
        self._month_summary.set_selection_mode(Gtk.SelectionMode.NONE)
        box.append(self._month_summary)

        scrolled = Gtk.ScrolledWindow(vexpand=True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_child(box)
        self.append(scrolled)

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

    # -- navigasi --------------------------------------------------------

    def refresh(self) -> None:
        self._sync_filter_model()
        self._title.set_label(f"{BULAN[self._anchor.month - 1]} {self._anchor.year}")
        self._refresh_month()

    def go_current(self) -> None:
        self.go_to_day(date.today())

    def go_to_day(self, day: date) -> None:
        """Tampilkan bulan ``day`` dan pilih tanggal itu."""

        self._anchor = date(day.year, day.month, 1)
        self._calendar_selected = day
        self.refresh()

    def go_to_month(self, day: date) -> None:
        """Alias ``go_to_day`` untuk pintasan dari tren tahunan."""

        self.go_to_day(day)

    def _shift(self, direction: int) -> None:
        self._anchor = shift_month(self._anchor, direction)
        self.refresh()

    # -- penyegaran ------------------------------------------------------

    def _refresh_month(self) -> None:
        clear_grid(self._month_grid)
        clear_list(self._month_summary)
        clear_list(self._calendar_detail_list)

        first, last = month_range(self._anchor)
        days_in_month = last.day
        if (self._calendar_selected.year, self._calendar_selected.month) != (
            first.year,
            first.month,
        ):
            self._calendar_selected = first

        worships = self._worships()
        entries = self._entries(first, last)
        noted_days = {
            item.day for item in self._repo.list_daily_notes(start=first, end=last)
        }
        states = {
            day_number: compute_daily(
                date(first.year, first.month, day_number), worships, entries
            ).state
            for day_number in range(1, days_in_month + 1)
        }

        for column, label in enumerate(HARI_SINGKAT):
            header = Gtk.Label(label=label)
            header.add_css_class("dim-label")
            self._month_grid.attach(header, column, 0, 1, 1)

        for day_number in range(1, days_in_month + 1):
            index = first.weekday() + day_number - 1
            state = states[day_number]
            captured_day = date(first.year, first.month, day_number)
            has_note = captured_day in noted_days
            button = Gtk.Button()
            button.add_css_class("ih-calendar-day")
            if captured_day == self._calendar_selected:
                button.add_css_class("ih-selected")
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            number = Gtk.Label(label=str(day_number))
            mark = Gtk.Label(label=STATE_SYMBOL[state])
            apply_state_class(mark, state)
            note_mark = Gtk.Label(label="✎" if has_note else "")
            note_mark.add_css_class("dim-label")
            set_accessible_label(note_mark, "Ada catatan harian" if has_note else "")
            inner.append(number)
            inner.append(mark)
            inner.append(note_mark)
            button.set_child(inner)

            note_text = " · ada catatan harian" if has_note else ""
            label = f"{day_number} {BULAN[first.month - 1]}, {STATE_TEXT[state]}{note_text}"
            button.set_tooltip_text(label)
            set_accessible_label(button, label)
            button.connect("clicked", self._on_calendar_day, captured_day)
            self._month_grid.attach(button, index % 7, index // 7 + 1, 1, 1)

        summary = compute_range(first, last, worships, entries, "month")[0]
        for item in summary.per_worship:
            row = Adw.ActionRow(
                title=item.name,
                subtitle=describe_completion(item.completed, item.expected),
            )
            self._month_summary.append(row)
        if not summary.per_worship:
            self._month_summary.append(
                Adw.ActionRow(title="Tidak ada kegiatan aktif pada bulan ini")
            )

        self._refresh_calendar_detail(worships, entries)

    def _refresh_calendar_detail(
        self, worships: tuple[Worship, ...], entries: tuple
    ) -> None:
        """Tampilkan capaian dan catatan dari hari yang dipilih di kalender."""

        day = self._calendar_selected
        daily_entries = tuple(item for item in entries if item.day == day)
        daily = compute_daily(day, worships, daily_entries)
        self._calendar_detail_state.set_label(
            f"{format_day(day)} — {STATE_SYMBOL[daily.state]} "
            f"{STATE_TEXT[daily.state]} · "
            + describe_daily_completion(daily.completed, daily.expected)
        )
        apply_state_class(self._calendar_detail_state, daily.state)
        set_accessible_label(
            self._calendar_detail_state, self._calendar_detail_state.get_label()
        )

        records = {item.id: item for item in self._worship_records()}
        allowed = {item.id for item in worships}
        entry_map = {
            item.worship_id: item
            for item in self._repo.list_entries(start=day, end=day)
            if item.worship_id in allowed
        }
        for item in daily.per_worship:
            label = "Terlaksana" if item.completed else (
                "Sebagian" if item.partial else "Belum ada catatan"
            )
            entry = entry_map.get(item.worship_id)
            if entry is not None:
                label += f" — {format_entry_detail(entry, records.get(item.worship_id))}"
            self._calendar_detail_list.append(
                Adw.ActionRow(title=item.name, subtitle=label)
            )
        if not daily.per_worship:
            self._calendar_detail_list.append(
                Adw.ActionRow(title="Tidak ada kegiatan aktif pada hari ini")
            )

        note = self._repo.get_daily_note(day).text
        self._calendar_detail_note.set_label(
            f"Catatan harian: {note}" if note else "Catatan harian: belum ada."
        )
        set_accessible_label(
            self._calendar_detail_note, self._calendar_detail_note.get_label()
        )

    def _on_calendar_day(self, _button: Gtk.Button, day: date) -> None:
        self._calendar_selected = day
        self.refresh()
