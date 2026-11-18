"""Halaman Hari Ini: menjawab apa yang sudah dan belum hari ini."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk

from ..logic.repository import (
    EntryRecord,
    Repository,
    WorshipRecord,
    neutral_value,
)
from ..logic.statistics import (
    compute_daily,
    describe_daily_completion,
    is_active,
)
from .a11y import set_accessible_label

__all__ = ["TodayPage"]

HARI = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")
BULAN = (
    "Januari",
    "Februari",
    "Maret",
    "April",
    "Mei",
    "Juni",
    "Juli",
    "Agustus",
    "September",
    "Oktober",
    "November",
    "Desember",
)
AddWorshipCallback = Callable[[], None]
DataChangedCallback = Callable[[], None]


def _format_day(day: date) -> str:
    return f"{HARI[day.weekday()]}, {day.day} {BULAN[day.month - 1]} {day.year}"


class _EntryDialog(Adw.Dialog):
    """Panel kecil untuk jam pelaksanaan dan catatan sebuah ibadah."""

    def __init__(
        self,
        repository: Repository,
        worship: WorshipRecord,
        day: date,
        entry: EntryRecord | None,
        *,
        on_changed: Callable[[], None],
    ) -> None:
        super().__init__()
        self._repo = repository
        self._worship = worship
        self._day = day
        self._entry = entry
        self._on_changed = on_changed
        self.set_title(f"Detail — {worship.name}")
        self.set_content_width(420)

        group = Adw.PreferencesGroup()
        group.set_title("Catatan hari ini")

        self._time_row = Adw.EntryRow(title="Jam (opsional)")
        self._time_row.set_text("" if entry is None else (entry.time or ""))
        group.add(self._time_row)

        self._note_row = Adw.EntryRow(title="Catatan")
        self._note_row.set_text("" if entry is None else entry.note)
        group.add(self._note_row)

        self._error = Gtk.Label(label="")
        self._error.add_css_class("dim-label")
        self._error.set_wrap(True)
        self._error.set_xalign(0)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.append(group)
        content.append(self._error)

        if entry is not None:
            remove = Gtk.Button(label="Hapus catatan")
            remove.connect("clicked", self._on_remove)
            content.append(remove)

        header = Adw.HeaderBar()
        cancel = Gtk.Button(label="Tutup")
        cancel.connect("clicked", lambda *_: self.close())
        header.pack_start(cancel)
        save = Gtk.Button(label="Simpan")
        save.add_css_class("suggested-action")
        save.connect("clicked", self._on_save)
        header.pack_end(save)

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(header)
        toolbar.set_content(content)
        self.set_child(toolbar)
        self.set_default_widget(save)

    def _on_save(self, _button: Gtk.Button) -> None:
        value = None if self._entry is None else self._entry.value
        if value is None:
            value = neutral_value(self._worship.kind)
        try:
            self._repo.set_entry(
                self._worship.id,
                self._day,
                value=value,
                time=self._time_row.get_text(),
                note=self._note_row.get_text(),
            )
        except ValueError as error:
            self._error.set_label(str(error))
            return
        self._on_changed()
        self.close()

    def _on_remove(self, _button: Gtk.Button) -> None:
        self._repo.delete_entry(self._worship.id, self._day)
        self._on_changed()
        self.close()


class TodayPage(Gtk.Box):
    """Daftar ibadah untuk satu tanggal, dengan ringkasan netral."""

    def __init__(
        self,
        repository: Repository,
        *,
        on_add_worship: AddWorshipCallback,
        on_data_changed: DataChangedCallback,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._repo = repository
        self._on_add_worship = on_add_worship
        self._on_data_changed = on_data_changed
        self.day = date.today()
        self._known_today = date.today()
        self._rows: dict[int, "WorshipRow"] = {}
        self._note_source: int | None = None
        self._note_loading = False

        self._build_navigation()
        self._build_day_change_notice()

        self._summary_label = Gtk.Label(label="")
        self._summary_label.set_xalign(0)
        self._summary_label.add_css_class("dim-label")
        self._progress = Gtk.ProgressBar()
        self._progress.set_show_text(False)

        summary_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        summary_box.set_margin_start(18)
        summary_box.set_margin_end(18)
        summary_box.set_margin_top(6)
        summary_box.set_margin_bottom(6)
        summary_box.append(self._summary_label)
        summary_box.append(self._progress)
        self.append(summary_box)

        self._content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._list_holder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._content_box.append(self._list_holder)
        self._content_box.append(self._build_daily_note_card())

        self._scrolled = Gtk.ScrolledWindow(vexpand=True)
        self._scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._scrolled.set_child(self._content_box)
        self.append(self._scrolled)

        self._load_note()
        self.refresh()
        GLib.timeout_add_seconds(30, self._check_day_change)

    # -- konstruksi ------------------------------------------------------

    def _build_navigation(self) -> None:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(12)

        previous = Gtk.Button.new_from_icon_name("go-previous-symbolic")
        previous.set_tooltip_text("Hari sebelumnya (Ctrl+←)")
        set_accessible_label(previous, "Hari sebelumnya")
        previous.connect("clicked", lambda *_: self.go_previous_day())
        box.append(previous)

        self._date_label = Gtk.Label(label="")
        self._date_label.set_hexpand(True)
        self._date_label.set_xalign(0.5)
        box.append(self._date_label)

        today = Gtk.Button(label="Hari ini")
        today.set_tooltip_text("Kembali ke hari ini (Ctrl+T)")
        set_accessible_label(today, "Kembali ke hari ini")
        today.connect("clicked", lambda *_: self.go_today())
        box.append(today)

        following = Gtk.Button.new_from_icon_name("go-next-symbolic")
        following.set_tooltip_text("Hari berikutnya (Ctrl+→)")
        set_accessible_label(following, "Hari berikutnya")
        following.connect("clicked", lambda *_: self.go_next_day())
        box.append(following)

        self._context_label = Gtk.Label(label="")
        self._context_label.set_xalign(0.5)
        self._context_label.add_css_class("dim-label")

        wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        wrapper.append(box)
        wrapper.append(self._context_label)
        self.append(wrapper)

    def _build_day_change_notice(self) -> None:
        notice = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        notice.set_margin_start(12)
        notice.set_margin_end(12)
        notice.set_margin_top(6)
        label = Gtk.Label(label="Hari sudah berganti.")
        label.set_hexpand(True)
        label.set_xalign(0)
        notice.append(label)
        switch = Gtk.Button(label="Beralih ke hari ini")
        set_accessible_label(switch, "Beralih ke hari ini")
        switch.connect("clicked", self._on_switch_to_new_day)
        notice.append(switch)
        self._day_change_revealer = Gtk.Revealer()
        self._day_change_revealer.set_child(notice)
        self.append(self._day_change_revealer)

    def _build_daily_note_card(self) -> Gtk.Box:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.add_css_class("ih-card")
        card.set_margin_start(18)
        card.set_margin_end(18)
        card.set_margin_top(12)
        card.set_margin_bottom(18)

        title = Gtk.Label(label="Catatan harian")
        title.set_xalign(0)
        title.add_css_class("dim-label")
        hint = Gtk.Label(label="Tulis hal singkat tentang hari ini; tersimpan otomatis.")
        hint.set_xalign(0)
        hint.add_css_class("dim-label")
        hint.set_wrap(True)

        self._note_view = Gtk.TextView()
        self._note_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self._note_view.set_accepts_tab(False)
        self._note_view.get_buffer().connect("changed", self._on_note_changed)
        set_accessible_label(self._note_view, "Catatan harian")
        note_scroll = Gtk.ScrolledWindow()
        note_scroll.set_min_content_height(90)
        note_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        note_scroll.set_child(self._note_view)

        self._note_status = Gtk.Label(label="Tersimpan otomatis")
        self._note_status.set_xalign(0)
        self._note_status.add_css_class("dim-label")

        card.append(title)
        card.append(hint)
        card.append(note_scroll)
        card.append(self._note_status)
        return card

    # -- catatan harian ---------------------------------------------------

    def _note_text(self) -> str:
        buffer = self._note_view.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)

    def _load_note(self) -> None:
        self._note_loading = True
        try:
            record = self._repo.get_daily_note(self.day)
            self._note_view.get_buffer().set_text(record.text)
            self._note_status.set_label("Tersimpan otomatis")
        finally:
            self._note_loading = False

    def _on_note_changed(self, *_args: object) -> None:
        if self._note_loading:
            return
        self._note_status.set_label("Menunggu penyimpanan…")
        if self._note_source is not None:
            GLib.source_remove(self._note_source)
        self._note_source = GLib.timeout_add_seconds(1, self._autosave_note)

    def _autosave_note(self) -> bool:
        self._note_source = None
        self._save_note_now()
        return False

    def _save_note_now(self, *, notify: bool = True) -> None:
        self._repo.save_daily_note(self.day, self._note_text())
        self._note_status.set_label("Tersimpan otomatis")
        if notify:
            self._on_data_changed()

    def _flush_note(self, *, notify: bool = True) -> None:
        if self._note_source is not None:
            GLib.source_remove(self._note_source)
            self._note_source = None
            self._save_note_now(notify=notify)

    # -- navigasi tanggal ------------------------------------------------

    def go_previous_day(self) -> None:
        self._flush_note()
        self.day -= timedelta(days=1)
        self._load_note()
        self.refresh()

    def go_next_day(self) -> None:
        self._flush_note()
        self.day += timedelta(days=1)
        self._load_note()
        self.refresh()

    def go_today(self) -> None:
        self.set_day(date.today())

    def set_day(self, day: date) -> None:
        """Tampilkan tanggal tertentu, misalnya dari kalender Riwayat."""

        self._flush_note()
        self.day = day
        self._day_change_revealer.set_reveal_child(False)
        self._load_note()
        self.refresh()

    def _check_day_change(self) -> bool:
        today = date.today()
        if today != self._known_today:
            self._known_today = today
            self._day_change_revealer.set_reveal_child(True)
        return True

    def _on_switch_to_new_day(self, _button: Gtk.Button) -> None:
        self.go_today()
        self._day_change_revealer.set_reveal_child(False)

    # -- penyegaran ------------------------------------------------------

    def _focused_worship_id(self) -> int | None:
        widget = self
        while widget is not None:
            if hasattr(widget, "worship"):
                return int(widget.worship.id)
            child = widget.get_focus_child()
            if child is None:
                return None
            widget = child
        return None

    def refresh(self) -> None:
        focused_id = self._focused_worship_id()
        self._date_label.set_label(_format_day(self.day))
        if self.day > date.today():
            self._context_label.set_label("Hari depan — pencatatan dibatasi")
        elif self.day < date.today():
            self._context_label.set_label("Mengisi hari lampau")
        else:
            self._context_label.set_label("")

        worships, entries = self._repo.statistics_inputs(start=self.day, end=self.day)
        summary = compute_daily(self.day, worships, entries)
        self._summary_label.set_label(
            describe_daily_completion(summary.completed, summary.expected)
        )
        self._progress.set_fraction(
            summary.completed / summary.expected if summary.expected else 0.0
        )

        entry_map = {item.worship_id: item for item in self._repo.list_entries(start=self.day, end=self.day)}
        active = [
            worship
            for worship in self._repo.list_worships()
            if is_active(worship, self.day)
        ]

        self._rows.clear()
        self._clear_container(self._list_holder)
        if not active:
            empty = Adw.StatusPage(
                title="Belum ada ibadah",
                description="Tambahkan ibadah untuk mulai mencatat hari ini.",
                icon_name="view-list-symbolic",
            )
            button = Gtk.Button(label="Tambah ibadah")
            button.add_css_class("suggested-action")
            button.connect("clicked", lambda *_: self._on_add_worship())
            empty.set_child(button)
            self._list_holder.append(empty)
            return

        group = Gtk.ListBox()
        group.set_selection_mode(Gtk.SelectionMode.NONE)
        group.add_css_class("boxed-list")
        categories = {category.id: category for category in self._repo.list_categories()}
        grouped: dict[int | None, list[WorshipRecord]] = {}
        for worship in active:
            grouped.setdefault(worship.category_id, []).append(worship)

        ordered_categories = [category.id for category in categories.values()]
        for category_id in [None, *ordered_categories]:
            items = grouped.get(category_id)
            if not items:
                continue
            title = "Lainnya" if category_id is None else categories[category_id].name
            expander = Adw.ExpanderRow(title=title)
            category = categories.get(category_id)
            if category is not None:
                expander.set_expanded(not category.collapsed)
                expander.connect(
                    "notify::expanded",
                    lambda row, _param, cid=category_id: self._repo.set_category_collapsed(
                        cid, not row.get_expanded()
                    ),
                )
            expander.set_sensitive(self.day <= date.today())
            for worship in items:
                row = self._create_row(worship, entry_map.get(worship.id))
                expander.add_row(row)
            group.append(expander)

        self._list_holder.append(group)
        if focused_id is not None and focused_id in self._rows:
            GLib.idle_add(self._rows[focused_id].focus_value)

    @staticmethod
    def _clear_container(container: Gtk.Box) -> None:
        child = container.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            container.remove(child)
            child = following

    def _create_row(self, worship: WorshipRecord, entry: EntryRecord | None):
        from .worship_row import WorshipRow

        row = WorshipRow(
            worship,
            entry,
            on_value_changed=self._on_value_changed,
            on_details=self._on_details,
        )
        row.set_sensitive(self.day <= date.today())
        self._rows[worship.id] = row
        return row

    def _on_value_changed(self, worship_id: int, value) -> None:
        if self.day > date.today():
            return
        if value is None:
            self._repo.delete_entry(worship_id, self.day)
        else:
            self._repo.set_entry(worship_id, self.day, value=value)
        self.refresh()
        self._on_data_changed()

    def _on_details(self, worship: WorshipRecord) -> None:
        if self.day > date.today():
            return
        entry = self._repo.get_entry(worship.id, self.day)
        dialog = _EntryDialog(
            self._repo,
            worship,
            self.day,
            entry,
            on_changed=self._on_entry_details_changed,
        )
        dialog.present(self)

    def _on_entry_details_changed(self) -> None:
        self.refresh()
        self._on_data_changed()

    def do_dispose(self) -> None:
        # Saat jendela ditutup, simpan tulisan yang belum sempat masuk timer.
        # Jangan memicu penyegaran UI dari widget yang sedang dibongkar.
        self._flush_note(notify=False)
        Gtk.Box.do_dispose(self)
