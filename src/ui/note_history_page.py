"""Histori Catatan: kumpulan catatan harian bebas per tanggal.

Halaman ini sengaja hanya menampilkan isi tabel ``catatan_harian``. Catatan
per ibadah tetap ada di Riwayat/Kalender, sedangkan muhasabah punya halaman
sendiri, supaya ketiganya tidak tercampur.
"""

from __future__ import annotations

from datetime import date

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from ..logic.repository import DailyNoteRecord, Repository
from .a11y import set_accessible_label
from .history_common import ToastCallback, clear_list, format_day, OpenDayCallback

__all__ = ["NoteHistoryPage"]


class NoteHistoryPage(Gtk.Box):
    """Daftar dan pencarian catatan harian, dengan aksi buka tanggal."""

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
        self._visible_notes: tuple[DailyNoteRecord, ...] = ()
        self._selected: DailyNoteRecord | None = None

        self._build_controls()
        self._build_content()
        self.refresh()

    # -- konstruksi ------------------------------------------------------

    def _build_controls(self) -> None:
        controls = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        controls.set_margin_start(12)
        controls.set_margin_end(12)
        controls.set_margin_top(12)
        controls.set_margin_bottom(6)

        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_placeholder_text("Cari catatan harian…")
        self._search_entry.connect("notify::text", self._on_search_changed)
        controls.append(self._search_entry)

        self._count_label = Gtk.Label(label="")
        self._count_label.set_xalign(0)
        self._count_label.add_css_class("ih-hint")
        controls.append(self._count_label)
        self.append(controls)

    def _build_content(self) -> None:
        self._stack = Gtk.Stack()

        self._notes_list = Gtk.ListBox()
        self._notes_list.add_css_class("boxed-list")
        self._notes_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._notes_list.connect("row-selected", self._on_row_selected)
        self._notes_list.connect("row-activated", self._on_row_activated)

        scrolled = Gtk.ScrolledWindow(vexpand=True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_child(self._notes_list)
        self._stack.add_named(scrolled, "list")

        self._empty = Adw.StatusPage(
            title="Belum ada catatan harian",
            description=(
                "Tulis catatan bebas di halaman Hari Ini. Catatan itu akan "
                "muncul di sini, terpisah dari catatan kegiatan dan muhasabah."
            ),
            icon_name="text-x-generic-symbolic",
        )
        self._stack.add_named(self._empty, "empty")
        self._stack.set_visible_child_name("empty")
        self.append(self._stack)

        preview = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        preview.set_margin_start(18)
        preview.set_margin_end(18)
        preview.set_margin_top(6)
        preview.set_margin_bottom(18)

        title = Gtk.Label(label="Pratinjau catatan")
        title.set_xalign(0)
        title.add_css_class("ih-section-title")
        preview.append(title)

        self._preview_text = Gtk.Label(label="Pilih satu catatan untuk membacanya.")
        self._preview_text.set_xalign(0)
        self._preview_text.set_wrap(True)
        self._preview_text.add_css_class("dim-label")
        preview.append(self._preview_text)

        open_button = Gtk.Button(label="Buka tanggal di Hari Ini")
        open_button.set_halign(Gtk.Align.START)
        open_button.connect("clicked", lambda *_: self._open_selected())
        open_button.set_sensitive(False)
        self._open_button = open_button
        preview.append(open_button)
        self.append(preview)

    # -- data ------------------------------------------------------------

    def _on_search_changed(self, *_args: object) -> None:
        self.refresh()

    def refresh(self) -> None:
        query = self._search_entry.get_text().strip().casefold()
        notes = self._repo.list_daily_notes()
        if query:
            notes = tuple(
                item
                for item in notes
                if query in item.text.casefold()
                or query in format_day(item.day).casefold()
            )
        self._visible_notes = notes

        if self._selected is not None and self._selected not in notes:
            self._selected = None

        clear_list(self._notes_list)
        for note in notes:
            row = Adw.ActionRow(
                title=format_day(note.day),
                subtitle=self._short_preview(note.text),
            )
            row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
            set_accessible_label(
                row, f"{format_day(note.day)}: {note.text}. Tekan Enter untuk membuka."
            )
            self._notes_list.append(row)

        if notes:
            self._stack.set_visible_child_name("list")
            self._count_label.set_label(
                f"{len(notes)} catatan" + (" sesuai pencarian" if query else "")
            )
            if self._selected is None:
                self._notes_list.select_row(self._notes_list.get_row_at_index(0))
        else:
            self._stack.set_visible_child_name("empty")
            self._empty.set_description(
                "Tidak ada catatan harian yang cocok."
                if query
                else (
                    "Tulis catatan bebas di halaman Hari Ini. Catatan itu akan "
                    "muncul di sini, terpisah dari catatan kegiatan dan muhasabah."
                )
            )
            self._count_label.set_label("Tidak ada catatan")
        self._update_preview()

    @staticmethod
    def _short_preview(text: str) -> str:
        first = next((line.strip() for line in text.splitlines() if line.strip()), "")
        return first if len(first) <= 88 else first[:85] + "…"

    def _update_preview(self) -> None:
        if self._selected is None:
            self._preview_text.set_label("Pilih satu catatan untuk membacanya.")
            self._open_button.set_sensitive(False)
            return
        self._preview_text.set_label(
            f"{format_day(self._selected.day)}\n\n{self._selected.text}"
        )
        set_accessible_label(self._preview_text, self._preview_text.get_label())
        self._open_button.set_sensitive(True)

    # -- interaksi -------------------------------------------------------

    def _note_at_row(self, row: Gtk.ListBoxRow) -> DailyNoteRecord | None:
        sibling = self._notes_list.get_first_child()
        index = 0
        while sibling is not None:
            if sibling is row or sibling == row:
                if 0 <= index < len(self._visible_notes):
                    return self._visible_notes[index]
                return None
            sibling = sibling.get_next_sibling()
            index += 1
        return None

    def _on_row_selected(self, _list: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        self._selected = None if row is None else self._note_at_row(row)
        self._update_preview()

    def _on_row_activated(self, _list: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        note = self._note_at_row(row)
        if note is not None:
            self._on_open_day(note.day)

    def _open_selected(self) -> None:
        if self._selected is not None:
            self._on_open_day(self._selected.day)

    def focus_search(self) -> None:
        self._search_entry.grab_focus()

    def go_today(self) -> None:
        """Tampilkan catatan hari ini bila ada, tanpa mengubah data."""

        self._search_entry.set_text("")
        self.refresh()
        day = date.today()
        for note in self._visible_notes:
            if note.day == day:
                row = self._notes_list.get_row_at_index(
                    self._visible_notes.index(note)
                )
                if row is not None:
                    self._notes_list.select_row(row)
                break
