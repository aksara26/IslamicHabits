"""Halaman Hari Ini: menjawab apa yang sudah dan belum hari ini."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk, Pango

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
from .date_navigator import DateNavigator

__all__ = ["TodayPage"]

AddWorshipCallback = Callable[[], None]
DataChangedCallback = Callable[[], None]
OpenMemoCallback = Callable[[date], None]


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
        on_open_memo: OpenMemoCallback,
        on_add_habit: AddWorshipCallback | None = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._repo = repository
        self._on_add_worship = on_add_worship
        self._on_add_habit = on_add_habit or on_add_worship
        self._on_data_changed = on_data_changed
        self._on_open_memo = on_open_memo
        self.day = date.today()
        self._known_today = date.today()
        self._rows: dict[int, "WorshipRow"] = {}

        self._build_navigation()
        self._build_day_change_notice()

        self._summary_label = Gtk.Label(label="")
        self._summary_label.set_xalign(0)
        self._summary_label.add_css_class("ih-hint")
        self._progress = Gtk.ProgressBar()
        self._progress.set_show_text(False)
        self._progress.add_css_class("ih-progress")

        summary_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        summary_box.add_css_class("ih-card")
        summary_box.set_margin_start(18)
        summary_box.set_margin_end(18)
        summary_box.set_margin_top(6)
        summary_box.set_margin_bottom(6)

        summary_title = Gtk.Label(label="Ringkasan hari ini")
        summary_title.set_xalign(0)
        summary_title.set_hexpand(True)
        summary_title.add_css_class("ih-section-title")
        self._summary_label.set_valign(Gtk.Align.CENTER)
        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_row.append(summary_title)
        title_row.append(self._summary_label)
        summary_box.append(title_row)
        summary_box.append(self._progress)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        add_worship = Gtk.Button(label="Tambah ibadah")
        add_worship.add_css_class("ih-quick")
        add_worship.connect("clicked", lambda *_: self._on_add_worship())
        add_habit = Gtk.Button(label="Tambah kebiasaan")
        add_habit.add_css_class("ih-quick")
        add_habit.connect("clicked", lambda *_: self._on_add_habit())
        actions.append(add_worship)
        actions.append(add_habit)
        summary_box.append(actions)
        self.append(summary_box)

        self._content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        # Memo adalah konteks hari, jadi kartunya tampil sebelum daftar
        # kegiatan agar tidak tenggelam di bagian paling bawah halaman.
        self._content_box.append(self._build_daily_note_card())

        list_title = Gtk.Label(label="Ibadah & kebiasaan")
        list_title.set_xalign(0)
        list_title.set_margin_start(18)
        list_title.set_margin_top(6)
        list_title.add_css_class("ih-section-title")
        self._content_box.append(list_title)

        self._list_holder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._content_box.append(self._list_holder)

        self._scrolled = Gtk.ScrolledWindow(vexpand=True)
        self._scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._scrolled.set_child(self._content_box)
        self.append(self._scrolled)

        self._load_note()
        self.refresh()
        GLib.timeout_add_seconds(30, self._check_day_change)

    # -- konstruksi ------------------------------------------------------

    def _build_navigation(self) -> None:
        self._nav = DateNavigator(
            on_previous=self.go_previous_day,
            on_next=self.go_next_day,
            on_today=self.go_today,
            on_pick=self.set_day,
        )
        self.append(self._nav)

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
        card.set_margin_top(6)
        card.set_margin_bottom(6)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title = Gtk.Label(label="Memo harian")
        title.set_xalign(0)
        title.set_hexpand(True)
        title.add_css_class("ih-section-title")
        open_button = Gtk.Button(label="Buka Memo")
        open_button.add_css_class("ih-quick")
        open_button.set_tooltip_text("Tulis memo dan lampirkan foto")
        open_button.connect("clicked", lambda *_: self._on_open_memo(self.day))
        header.append(title)
        header.append(open_button)

        self._note_preview = Gtk.Label(label="")
        self._note_preview.set_xalign(0)
        self._note_preview.set_wrap(True)
        self._note_preview.set_lines(2)
        self._note_preview.set_ellipsize(Pango.EllipsizeMode.END)

        self._note_meta = Gtk.Label(label="")
        self._note_meta.set_xalign(0)
        self._note_meta.add_css_class("ih-hint")

        card.append(header)
        card.append(self._note_preview)
        card.append(self._note_meta)
        return card

    # -- catatan harian ---------------------------------------------------

    def _load_note(self) -> None:
        record = self._repo.get_daily_note(self.day)
        text = record.text.strip()
        if text:
            first = next(
                (line.strip() for line in text.splitlines() if line.strip()), text
            )
            preview = first if len(first) <= 160 else first[:157] + "…"
        else:
            preview = "Belum ada memo untuk tanggal ini."
        self._note_preview.set_label(preview)
        parts = [f"{record.photo_count} foto"] if record.photo_count else []
        parts.append("Tersimpan" if text else "Kosong")
        self._note_meta.set_label(" · ".join(parts))

    # -- navigasi tanggal ------------------------------------------------

    def go_previous_day(self) -> None:
        self.day -= timedelta(days=1)
        self.refresh()

    def go_next_day(self) -> None:
        self.day += timedelta(days=1)
        self.refresh()

    def go_today(self) -> None:
        self.set_day(date.today())

    def set_day(self, day: date) -> None:
        """Tampilkan tanggal tertentu, misalnya dari Kalender atau Histori Catatan."""

        self.day = day
        self._day_change_revealer.set_reveal_child(False)
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

    @staticmethod
    def _context_for(day: date) -> str:
        if day > date.today():
            return "Hari depan — pencatatan dibatasi"
        if day < date.today():
            return "Mengisi hari lampau"
        return ""

    def _refresh_summary(self) -> None:
        """Perbarui ringkasan saja tanpa membangun ulang daftar kegiatan."""

        worships, entries = self._repo.statistics_inputs(start=self.day, end=self.day)
        summary = compute_daily(self.day, worships, entries)
        self._summary_label.set_label(
            describe_daily_completion(summary.completed, summary.expected)
        )
        self._progress.set_fraction(
            summary.completed / summary.expected if summary.expected else 0.0
        )

    def refresh(self) -> None:
        focused_id = self._focused_worship_id()
        self._load_note()
        self._nav.set_day(self.day, context=self._context_for(self.day))
        self._refresh_summary()

        entry_map = {
            item.worship_id: item
            for item in self._repo.list_entries(start=self.day, end=self.day)
        }
        active = [
            worship
            for worship in self._repo.list_worships()
            if is_active(worship, self.day)
        ]

        self._rows.clear()
        self._clear_container(self._list_holder)
        if not active:
            empty = Adw.StatusPage(
                title="Belum ada ibadah atau kebiasaan",
                description=(
                    "Tambahkan ibadah atau kebiasaan untuk mulai mencatat hari ini."
                ),
                icon_name="view-list-symbolic",
            )
            actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            actions.set_halign(Gtk.Align.CENTER)
            add_worship = Gtk.Button(label="Tambah ibadah")
            add_worship.add_css_class("suggested-action")
            add_worship.connect("clicked", lambda *_: self._on_add_worship())
            add_habit = Gtk.Button(label="Tambah kebiasaan")
            add_habit.add_css_class("ih-quick")
            add_habit.connect("clicked", lambda *_: self._on_add_habit())
            actions.append(add_worship)
            actions.append(add_habit)
            empty.set_child(actions)
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
        previous = self._repo.get_entry(worship_id, self.day)
        if value is None:
            self._repo.delete_entry(worship_id, self.day)
            entry = None
        else:
            # Pertahankan jam dan catatan yang sudah diisi lewat dialog detail;
            # sebelumnya mengubah nilai akan menghapus keduanya.
            entry = self._repo.set_entry(
                worship_id,
                self.day,
                value=value,
                time=None if previous is None else previous.time,
                note="" if previous is None else previous.note,
            )
        row = self._rows.get(worship_id)
        if row is not None:
            row.refresh(entry)
        self._refresh_summary()
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
            on_changed=lambda: self._on_entry_details_changed(worship.id),
        )
        dialog.present(self)

    def _on_entry_details_changed(self, worship_id: int) -> None:
        row = self._rows.get(worship_id)
        if row is not None:
            row.refresh(self._repo.get_entry(worship_id, self.day))
        self._refresh_summary()
        self._on_data_changed()
