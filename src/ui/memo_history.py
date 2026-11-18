"""Dialog "Memo sebelumnya" untuk menjelajah memo lama tanpa berpindah halaman.

Daftar ini membaca ``catatan_harian`` dan ``memo_foto`` sekaligus, lalu
menampilkan tanggal, cuplikan teks, dan jumlah foto. Memilih satu baris
menutup dialog dan membuka tanggal itu di editor Memo.
"""

from __future__ import annotations

from datetime import date
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from ..logic.repository import DailyNoteRecord, Repository
from .a11y import set_accessible_label
from .history_common import clear_list, format_day

__all__ = ["MemoHistoryDialog"]

OpenDayCallback = Callable[[date], None]


class MemoHistoryDialog(Adw.Dialog):
    """Daftar memo lama dengan pencarian dan pratinjau satu baris."""

    def __init__(
        self,
        repository: Repository,
        *,
        current_day: date,
        on_open: OpenDayCallback,
    ) -> None:
        super().__init__()
        self._repo = repository
        self._current_day = current_day
        self._on_open = on_open
        self._visible: tuple[DailyNoteRecord, ...] = ()

        self.set_title("Memo sebelumnya")
        self.set_content_width(720)
        self.set_content_height(600)

        header = Adw.HeaderBar()
        close = Gtk.Button(label="Tutup")
        close.connect("clicked", lambda *_: self.close())
        header.pack_start(close)
        header.set_title_widget(Adw.WindowTitle(title="Memo sebelumnya"))

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        body.set_margin_top(12)
        body.set_margin_bottom(18)
        body.set_margin_start(18)
        body.set_margin_end(18)

        hint = Gtk.Label(
            label=(
                "Semua tanggal yang punya teks atau foto. Pilih satu baris "
                "untuk membuka memo itu di editor."
            )
        )
        hint.set_xalign(0)
        hint.set_wrap(True)
        hint.add_css_class("ih-hint")
        body.append(hint)

        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_placeholder_text("Cari isi memo atau tanggal…")
        self._search_entry.connect("notify::text", self._on_search_changed)
        body.append(self._search_entry)

        self._count_label = Gtk.Label(label="")
        self._count_label.set_xalign(0)
        self._count_label.add_css_class("ih-hint")
        body.append(self._count_label)

        self._list = Gtk.ListBox()
        self._list.add_css_class("boxed-list")
        self._list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list.connect("row-activated", self._on_row_activated)

        scrolled = Gtk.ScrolledWindow(vexpand=True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_child(self._list)

        self._empty = Adw.StatusPage(
            title="Belum ada memo sebelumnya",
            description=(
                "Memo yang kamu tulis akan muncul di sini, lengkap dengan "
                "jumlah fotonya."
            ),
            icon_name="document-open-recent-symbolic",
        )

        self._stack = Gtk.Stack()
        self._stack.set_vexpand(True)
        self._stack.add_named(scrolled, "list")
        self._stack.add_named(self._empty, "empty")
        body.append(self._stack)

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(header)
        toolbar.set_content(body)
        self.set_child(toolbar)

        self.refresh()

    # -- data ------------------------------------------------------------

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
        self._visible = notes

        clear_list(self._list)
        for note in notes:
            self._list.append(self._build_row(note))

        if notes:
            self._stack.set_visible_child_name("list")
            self._count_label.set_label(
                f"{len(notes)} memo" + (" sesuai pencarian" if query else "")
            )
        else:
            self._stack.set_visible_child_name("empty")
            self._count_label.set_label("Tidak ada memo")
            self._empty.set_description(
                "Tidak ada memo yang cocok dengan pencarian."
                if query
                else (
                    "Memo yang kamu tulis akan muncul di sini, lengkap dengan "
                    "jumlah fotonya."
                )
            )

    def _build_row(self, note: DailyNoteRecord) -> Adw.ActionRow:
        snippet = self._preview(note.text)
        details: list[str] = []
        if note.photo_count:
            details.append(f"{note.photo_count} foto")
        if note.day == self._current_day:
            details.append("sedang dibuka")
        subtitle = " · ".join([*details, snippet]) if snippet else " · ".join(details)
        row = Adw.ActionRow(
            title=format_day(note.day),
            subtitle=subtitle or "Belum ada teks memo",
        )
        row.add_prefix(Gtk.Image.new_from_icon_name("text-x-generic-symbolic"))
        row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
        set_accessible_label(
            row,
            f"{format_day(note.day)}: {subtitle or 'tanpa teks'}. "
            "Tekan Enter untuk membuka memo.",
        )
        row.note = note  # type: ignore[attr-defined]
        return row

    @staticmethod
    def _preview(text: str) -> str:
        first = next((line.strip() for line in text.splitlines() if line.strip()), "")
        return first if len(first) <= 100 else first[:97] + "…"

    # -- interaksi -------------------------------------------------------

    def _on_search_changed(self, *_args: object) -> None:
        self.refresh()

    def _on_row_activated(self, _list: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        note = getattr(row, "note", None)
        if note is None:
            return
        day = note.day
        self.close()
        self._on_open(day)
