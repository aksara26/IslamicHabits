"""Halaman Muhasabah: catatan refleksi harian dengan simpan otomatis.

Dua kolom: daftar catatan lama di kiri dan editor di kanan. Pertanyaan
pemantik bisa diubah pengguna dan disimpan sebagai pengaturan.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk

from ..logic.constants import SETTING_MUHASABAH_PROMPTS
from ..logic.repository import MuhasabahRecord, Repository
from .a11y import set_accessible_label

__all__ = ["MuhasabahPage", "DEFAULT_PROMPTS"]

DEFAULT_PROMPTS: tuple[str, ...] = (
    "Apa yang berjalan lancar hari ini?",
    "Apa yang bisa diperbaiki esok hari?",
    "Apa yang saya syukuri hari ini?",
)

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

ToastCallback = Callable[[str, str | None, Callable[[], None] | None], None]


def _format_day(day: date) -> str:
    return f"{HARI[day.weekday()]}, {day.day} {BULAN[day.month - 1]} {day.year}"


class MuhasabahPage(Gtk.Box):
    """Daftar catatan + editor dengan autosave yang dibatasi waktunya."""

    def __init__(self, repository: Repository, *, on_toast: ToastCallback) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._repo = repository
        self._on_toast = on_toast
        self._day = date.today()
        self._search = ""
        self._loading = False
        self._save_source: int | None = None
        self._prompts = self._load_prompts()

        self._build_list_column()
        self._build_editor_column()

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_resize_start_child(True)
        paned.set_resize_end_child(True)
        paned.set_shrink_start_child(True)
        paned.set_shrink_end_child(True)
        paned.set_position(320)
        paned.set_start_child(self._list_column)
        paned.set_end_child(self._editor_column)
        self.append(paned)

        self._load_day()
        self.refresh_list()

    # -- konstruksi ------------------------------------------------------

    def _build_list_column(self) -> None:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_size_request(240, -1)

        title = Gtk.Label(label="Catatan lalu")
        title.set_xalign(0)
        title.add_css_class("ih-section-title")
        box.append(title)

        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_placeholder_text("Cari catatan…")
        self._search_entry.connect("search-changed", self._on_search_changed)
        box.append(self._search_entry)

        self._notes_list = Gtk.ListBox()
        self._notes_list.add_css_class("boxed-list")
        self._notes_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._notes_list.connect("row-activated", self._on_note_activated)
        scrolled = Gtk.ScrolledWindow(vexpand=True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_child(self._notes_list)
        box.append(scrolled)

        self._list_column = box

    def _build_editor_column(self) -> None:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_hexpand(True)

        nav = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        previous = Gtk.Button.new_from_icon_name("go-previous-symbolic")
        previous.set_tooltip_text("Hari sebelumnya")
        previous.connect("clicked", lambda *_: self._shift_day(-1))
        nav.append(previous)

        self._date_label = Gtk.Label(label="")
        self._date_label.set_hexpand(True)
        self._date_label.set_xalign(0.5)
        nav.append(self._date_label)

        following = Gtk.Button.new_from_icon_name("go-next-symbolic")
        following.set_tooltip_text("Hari berikutnya")
        following.connect("clicked", lambda *_: self._shift_day(1))
        nav.append(following)

        today_button = Gtk.Button(label="Hari ini")
        today_button.connect("clicked", lambda *_: self.go_today())
        nav.append(today_button)
        box.append(nav)

        self._save_status = Gtk.Label(label="Tersimpan otomatis")
        self._save_status.set_xalign(0)
        self._save_status.add_css_class("ih-hint")
        box.append(self._save_status)

        text_title = Gtk.Label(label="Renungan")
        text_title.set_xalign(0)
        text_title.add_css_class("ih-section-title")
        box.append(text_title)

        self._text_view = Gtk.TextView()
        self._text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self._text_view.set_accepts_tab(False)
        self._text_view.get_buffer().connect("changed", self._on_text_changed)
        self._text_scroll = Gtk.ScrolledWindow()
        self._text_scroll.set_min_content_height(140)
        self._text_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._text_scroll.set_child(self._text_view)
        box.append(self._text_scroll)

        editor = Adw.ExpanderRow(title="Pertanyaan pemantik", subtitle="Bisa diubah sendiri")
        self._prompt_rows: list[Adw.EntryRow] = []
        self._prompt_group = editor
        self._build_prompt_rows()
        add_prompt = Gtk.Button(label="Tambah pertanyaan")
        add_prompt.set_halign(Gtk.Align.START)
        add_prompt.connect("clicked", lambda *_: self._add_prompt())
        editor.add_row(Adw.ActionRow(child=add_prompt))  # type: ignore[arg-type]
        prompt_list = Gtk.ListBox()
        prompt_list.set_selection_mode(Gtk.SelectionMode.NONE)
        prompt_list.add_css_class("boxed-list")
        prompt_list.append(editor)
        box.append(prompt_list)

        answers_title = Gtk.Label(label="Jawaban")
        answers_title.set_xalign(0)
        answers_title.add_css_class("ih-section-title")
        box.append(answers_title)

        self._answers_view = Gtk.TextView()
        self._answers_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self._answers_view.set_accepts_tab(False)
        self._answers_view.get_buffer().connect("changed", self._on_text_changed)
        answers_scroll = Gtk.ScrolledWindow()
        answers_scroll.set_min_content_height(100)
        answers_scroll.set_vexpand(True)
        answers_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        answers_scroll.set_child(self._answers_view)
        box.append(answers_scroll)

        self._editor_column = box

    def _build_prompt_rows(self) -> None:
        for row in list(self._prompt_rows):
            self._prompt_group.remove(row)
        self._prompt_rows = []
        for prompt in self._prompts:
            entry = Adw.EntryRow(title="Pertanyaan")
            entry.set_text(prompt)
            entry.connect("changed", self._on_prompt_changed)
            self._prompt_group.add_row(entry)
            self._prompt_rows.append(entry)

    # -- pengaturan prompt -----------------------------------------------

    def _load_prompts(self) -> tuple[str, ...]:
        raw = self._repo.get_setting(SETTING_MUHASABAH_PROMPTS)
        if raw:
            try:
                values = json.loads(raw)
                if isinstance(values, list) and all(isinstance(v, str) for v in values):
                    return tuple(values)
            except json.JSONDecodeError:
                pass
        return DEFAULT_PROMPTS

    def _on_prompt_changed(self, *_args: object) -> None:
        prompts = tuple(row.get_text().strip() for row in self._prompt_rows)
        self._prompts = tuple(prompt for prompt in prompts if prompt)
        self._repo.set_setting(
            SETTING_MUHASABAH_PROMPTS, json.dumps(self._prompts, ensure_ascii=False)
        )

    def _add_prompt(self) -> None:
        entry = Adw.EntryRow(title="Pertanyaan baru")
        entry.connect("changed", self._on_prompt_changed)
        self._prompt_group.add_row(entry)
        self._prompt_rows.append(entry)
        entry.grab_focus()

    # -- daftar catatan --------------------------------------------------

    def _on_search_changed(self, *_args: object) -> None:
        self._search = self._search_entry.get_text().strip().lower()
        self.refresh_list()

    def refresh_list(self) -> None:
        child = self._notes_list.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            self._notes_list.remove(child)
            child = following

        records = [
            record
            for record in self._repo.list_muhasabah()
            if not self._search
            or self._search in record.text.lower()
            or self._search in record.answers.lower()
        ]
        for record in records:
            snippet = record.text.replace("\n", " ").strip() or "(belum ada tulisan)"
            if len(snippet) > 48:
                snippet = snippet[:48] + "…"
            row = Adw.ActionRow(title=_format_day(record.day), subtitle=snippet)
            row.set_name(record.day.isoformat())
            self._notes_list.append(row)

        if not records:
            empty = Adw.ActionRow(
                title="Belum ada catatan",
                subtitle="Tulis renungan di kolom kanan; tersimpan otomatis.",
            )
            self._notes_list.append(empty)

    def _on_note_activated(self, _list: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        try:
            day = date.fromisoformat(row.get_name())
        except ValueError:
            return
        self._day = day
        self._load_day()

    # -- editor ----------------------------------------------------------

    def _shift_day(self, direction: int) -> None:
        self._flush_save()
        self._day += timedelta(days=direction)
        self._load_day()

    def go_today(self) -> None:
        self.set_day(date.today())

    def set_day(self, day: date) -> None:
        """Buka editor untuk tanggal tertentu."""

        self._flush_save()
        self._day = day
        self._load_day()

    def refresh(self) -> None:
        """Muat ulang daftar dan isian tanggal aktif setelah data berubah."""

        self._flush_save()
        self._load_day()
        self.refresh_list()

    def focus_search(self) -> None:
        self._search_entry.grab_focus()

    def _load_day(self) -> None:
        self._loading = True
        record = self._repo.get_muhasabah(self._day)
        self._date_label.set_label(_format_day(self._day))
        self._text_view.get_buffer().set_text(record.text)
        self._answers_view.get_buffer().set_text(record.answers)
        self._save_status.set_label("Tersimpan otomatis")
        set_accessible_label(self._text_view, f"Renungan {_format_day(self._day)}")
        self._loading = False

    def _on_text_changed(self, *_args: object) -> None:
        if self._loading:
            return
        self._save_status.set_label("Menunggu penyimpanan…")
        if self._save_source is not None:
            GLib.source_remove(self._save_source)
        self._save_source = GLib.timeout_add_seconds(1, self._autosave)

    def _autosave(self) -> bool:
        self._save_source = None
        self._save_now()
        return False

    @staticmethod
    def _buffer_text(view: Gtk.TextView) -> str:
        buffer = view.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)

    def _save_now(self) -> None:
        text = self._buffer_text(self._text_view)
        answers = self._buffer_text(self._answers_view)
        if not text.strip() and not answers.strip():
            # Hapus baris kosong supaya daftar tidak penuh entri kosong.
            self._repo.delete_muhasabah(self._day)
        else:
            self._repo.save_muhasabah(self._day, text, answers)
        self._save_status.set_label("Tersimpan otomatis")
        self.refresh_list()

    def _flush_save(self) -> None:
        if self._save_source is not None:
            GLib.source_remove(self._save_source)
            self._save_source = None
            self._save_now()

    def do_dispose(self) -> None:
        self._flush_save()
        Gtk.Box.do_dispose(self)
