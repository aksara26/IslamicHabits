"""Jendela utama IslamicHabits dengan navigasi adaptif."""

from __future__ import annotations

from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, Gtk

from ..logic.constants import APP_NAME
from ..logic.repository import Repository

__all__ = ["MainWindow"]

ToastCallback = Callable[[str, str | None, Callable[[], None] | None], None]


class MainWindow(Adw.ApplicationWindow):
    """Satu jendela: sidebar, area konten, dan panel ringkasan opsional."""

    def __init__(self, *, repository: Repository, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._repo = repository
        self._undo_callback: Callable[[], None] | None = None

        self.set_title(APP_NAME)
        self.set_default_size(940, 660)
        self.set_size_request(420, 320)

        self._stack = Adw.ViewStack()
        self._today_page = self._make_today_page()
        self._manage_page = self._make_manage_page()
        self._stack.add_titled_with_icon(self._today_page, "today", "Hari Ini", "go-today-symbolic")
        self._stack.add_titled_with_icon(
            self._make_placeholder(
                "Riwayat",
                "Kalender dan garis tren akan tampil di sini.",
                "calendar-symbolic",
            ),
            "history",
            "Riwayat",
            "calendar-symbolic",
        )
        self._stack.add_titled_with_icon(
            self._make_placeholder(
                "Muhasabah",
                "Catatan refleksi harian akan ditulis di sini.",
                "document-edit-symbolic",
            ),
            "muhasabah",
            "Muhasabah",
            "document-edit-symbolic",
        )
        self._stack.add_titled_with_icon(
            self._manage_page,
            "manage",
            "Kelola Ibadah",
            "view-list-symbolic",
        )
        self._stack.add_titled_with_icon(
            self._make_placeholder(
                "Pengaturan",
                "Tema, pengingat, dan cadangan data akan diatur di sini.",
                "preferences-system-symbolic",
            ),
            "settings",
            "Pengaturan",
            "preferences-system-symbolic",
        )
        self._stack.set_visible_child_name("today")

        self._build_window()
        self._build_actions()
        self._stack.connect("notify::visible-child-name", self._on_page_changed)
        self._on_page_changed()

    # -- konstruksi ------------------------------------------------------

    def _build_window(self) -> None:
        switcher = Adw.ViewSwitcherSidebar(stack=self._stack)
        switcher.connect("activated", lambda *_: self._hide_sidebar_when_collapsed())

        sidebar_header = Adw.HeaderBar()
        sidebar_toolbar = Adw.ToolbarView()
        sidebar_toolbar.add_top_bar(sidebar_header)
        sidebar_toolbar.set_content(switcher)
        sidebar_page = Adw.NavigationPage(title=APP_NAME, child=sidebar_toolbar)

        self._window_title = Adw.WindowTitle(title="Hari Ini", subtitle=APP_NAME)
        content_header = Adw.HeaderBar()
        content_header.set_title_widget(self._window_title)

        toggle = Gtk.Button.new_from_icon_name("sidebar-show-symbolic")
        toggle.set_tooltip_text("Lipat atau buka sidebar")
        toggle.connect("clicked", self._on_toggle_sidebar)
        content_header.pack_start(toggle)

        add_button = Gtk.Button.new_from_icon_name("list-add-symbolic")
        add_button.set_tooltip_text("Ibadah baru (Ctrl+N)")
        add_button.connect("clicked", lambda *_: self.open_worship_dialog())
        content_header.pack_end(add_button)

        self._toast_overlay = Adw.ToastOverlay()
        self._toast_overlay.set_child(self._stack)

        content_toolbar = Adw.ToolbarView()
        content_toolbar.add_top_bar(content_header)
        content_toolbar.set_content(self._toast_overlay)
        self._content_page = Adw.NavigationPage(title="Hari Ini", child=content_toolbar)

        self._split = Adw.NavigationSplitView()
        self._split.set_sidebar(sidebar_page)
        self._split.set_content(self._content_page)

        breakpoint = Adw.Breakpoint(
            condition=Adw.BreakpointCondition.parse("max-width: 680sp")
        )
        breakpoint.add_setter(self._split, "collapsed", True)
        self.add_breakpoint(breakpoint)
        self.set_content(self._split)

    def _build_actions(self) -> None:
        actions = {
            "go-today": lambda *_: self.go_page("today"),
            "go-history": lambda *_: self.go_page("history"),
            "go-muhasabah": lambda *_: self.go_page("muhasabah"),
            "go-manage": lambda *_: self.go_page("manage"),
            "go-settings": lambda *_: self.go_page("settings"),
            "prev-day": lambda *_: self._go_to_today(self._today_page.go_previous_day),
            "next-day": lambda *_: self._go_to_today(self._today_page.go_next_day),
            "today": lambda *_: self._go_to_today(self._today_page.go_today),
            "new-worship": lambda *_: self.open_worship_dialog(),
            "undo": lambda *_: self.undo(),
            "shortcuts": lambda *_: self._show_shortcuts(),
            "search": lambda *_: self._toast(
                "Pencarian akan hadir bersama halaman terkait.", None, None
            ),
        }
        for name, callback in actions.items():
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

    @staticmethod
    def _make_placeholder(title: str, description: str, icon: str) -> Adw.StatusPage:
        return Adw.StatusPage(title=title, description=description, icon_name=icon)

    def _make_today_page(self):
        from .today_page import TodayPage

        return TodayPage(self._repo, on_add_worship=lambda: self.open_worship_dialog())

    def _make_manage_page(self):
        from .manage_page import ManagePage

        return ManagePage(
            self._repo,
            on_add_worship=self.open_worship_dialog,
            on_toast=self._toast,
        )

    # -- navigasi --------------------------------------------------------

    def go_page(self, name: str) -> None:
        self._stack.set_visible_child_name(name)
        self._hide_sidebar_when_collapsed()

    def _hide_sidebar_when_collapsed(self) -> None:
        if self._split.get_collapsed():
            self._split.set_show_content(True)

    def _on_toggle_sidebar(self, _button: Gtk.Button) -> None:
        if self._split.get_collapsed():
            self._split.set_show_content(not self._split.get_show_content())
        else:
            self._split.set_show_sidebar(not self._split.get_show_sidebar())

    def _on_page_changed(self, *_args: object) -> None:
        title = self._stack.get_visible_child_name() or "Hari Ini"
        page = self._stack.get_page(self._stack.get_visible_child())
        if page is not None:
            title = page.get_title() or title
        self._window_title.set_title(title)
        self._content_page.set_title(title)

    def _go_to_today(self, action: Callable[[], None]) -> None:
        self.go_page("today")
        action()

    # -- dialog dan notifikasi -------------------------------------------

    def open_worship_dialog(self, worship_id: int | None = None) -> None:
        from .worship_dialog import WorshipDialog

        worship = None if worship_id is None else self._repo.get_worship(worship_id)
        dialog = WorshipDialog(
            self._repo,
            self._repo.list_categories(),
            worship=worship,
            on_saved=self._on_worship_saved,
        )
        dialog.present(self)

    def _on_worship_saved(self, _worship_id: int) -> None:
        self._today_page.refresh()
        self._manage_page.refresh()
        self._toast("Ibadah tersimpan", None, None)

    def _toast(
        self,
        message: str,
        button_label: str | None,
        callback: Callable[[], None] | None,
    ) -> None:
        toast = Adw.Toast.new(message)
        self._undo_callback = callback if button_label else None
        if button_label and callback is not None:

            def on_button_clicked(*_args: object) -> None:
                callback()
                self._undo_callback = None

            toast.set_button_label(button_label)
            toast.connect("button-clicked", on_button_clicked)
        self._toast_overlay.add_toast(toast)

    def _show_shortcuts(self) -> None:
        dialog = Adw.ShortcutsDialog()
        sections = (
            (
                "Navigasi",
                (
                    ("Hari sebelumnya", "<Ctrl>Left"),
                    ("Hari berikutnya", "<Ctrl>Right"),
                    ("Kembali ke hari ini", "<Ctrl>T"),
                    ("Riwayat (harian)", "<Ctrl>1"),
                    ("Riwayat (bulanan)", "<Ctrl>2"),
                    ("Riwayat (tahunan)", "<Ctrl>3"),
                ),
            ),
            (
                "Ibadah",
                (
                    ("Ibadah baru", "<Ctrl>N"),
                    ("Urungkan", "<Ctrl>Z"),
                    ("Cari", "<Ctrl>F"),
                ),
            ),
            (
                "Aplikasi",
                (
                    ("Pengaturan", "<Ctrl>comma"),
                    ("Daftar pintasan", "<Ctrl>question"),
                    ("Keluar", "<Ctrl>Q"),
                ),
            ),
        )
        for title, items in sections:
            section = Adw.ShortcutsSection(title=title)
            for item_title, accelerator in items:
                section.add(
                    Adw.ShortcutsItem(title=item_title, accelerator=accelerator)
                )
            dialog.add(section)
        dialog.present(self)

    def undo(self) -> None:
        if self._undo_callback is None:
            self._toast("Tidak ada perubahan untuk diurungkan", None, None)
            return
        callback = self._undo_callback
        self._undo_callback = None
        callback()
