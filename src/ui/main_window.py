"""Jendela utama IslamicHabits dengan navigasi adaptif."""

from __future__ import annotations

from datetime import date, datetime
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk

from ..logic.constants import (
    APP_NAME,
    META_ONBOARDING_DONE,
    SETTING_REMINDER_ENABLED,
    SETTING_REMINDER_POPUP,
    SETTING_REMINDER_TIME,
    SETTING_THEME,
)
from ..logic.defaults import HABIT_CATEGORY
from ..logic.repository import Repository
from .a11y import set_accessible_label
from .theme import apply_theme

__all__ = ["MainWindow"]

ToastCallback = Callable[[str, str | None, Callable[[], None] | None], None]


class MainWindow(Adw.ApplicationWindow):
    """Satu jendela: sidebar, area konten, dan panel ringkasan opsional."""

    def __init__(self, *, repository: Repository, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._repo = repository
        self._undo_callback: Callable[[], None] | None = None
        self._reminder_day: date | None = None

        self.set_title(APP_NAME)
        self.set_default_size(940, 660)
        self.set_size_request(420, 320)

        self._stack = Adw.ViewStack()
        self._today_page = self._make_today_page()
        self._history_page = self._make_history_page()
        self._calendar_page = self._make_calendar_page()
        self._note_history_page = self._make_note_history_page()
        self._muhasabah_page = self._make_muhasabah_page()
        self._manage_page = self._make_manage_page()
        self._settings_page = self._make_settings_page()

        self._stack.add_titled_with_icon(self._today_page, "today", "Hari Ini", "go-today-symbolic")
        self._stack.add_titled_with_icon(
            self._history_page, "history", "Riwayat", "view-list-ordered-symbolic"
        )
        self._stack.add_titled_with_icon(
            self._calendar_page,
            "calendar",
            "Kalender",
            "office-calendar-symbolic",
        )
        self._stack.add_titled_with_icon(
            self._note_history_page,
            "note-history",
            "Histori Catatan",
            "text-x-generic-symbolic",
        )
        self._stack.add_titled_with_icon(
            self._muhasabah_page,
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
            self._settings_page,
            "settings",
            "Pengaturan",
            "preferences-system-symbolic",
        )
        self._stack.set_visible_child_name("today")

        self._build_window()
        self._build_actions()
        self._stack.connect("notify::visible-child-name", self._on_page_changed)
        self._on_page_changed()

        GLib.idle_add(self._show_onboarding_if_needed)
        self._check_reminder()
        GLib.timeout_add_seconds(60, self._check_reminder)

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
        set_accessible_label(toggle, "Lipat atau buka sidebar")
        toggle.connect("clicked", self._on_toggle_sidebar)
        content_header.pack_start(toggle)

        search_button = Gtk.Button.new_from_icon_name("system-search-symbolic")
        search_button.set_tooltip_text("Cari catatan (Ctrl+F)")
        set_accessible_label(search_button, "Cari catatan")
        search_button.connect("clicked", lambda *_: self._on_search())
        content_header.pack_end(search_button)
        self._search_button = search_button

        add_menu = Gio.Menu()
        add_menu.append("Ibadah baru", "win.new-worship")
        add_menu.append("Kebiasaan baru", "win.new-habit")
        add_button = Gtk.MenuButton(
            icon_name="list-add-symbolic",
            menu_model=add_menu,
            tooltip_text="Tambah ibadah atau kebiasaan (Ctrl+N)",
        )
        set_accessible_label(add_button, "Tambah ibadah atau kebiasaan")
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
            "history-day": lambda *_: self._go_history("day"),
            # Alias lama tetap diterima, sekarang membuka halaman Kalender.
            "history-month": lambda *_: self._go_calendar(),
            "history-year": lambda *_: self._go_history("year"),
            "go-calendar": lambda *_: self._go_calendar(),
            "go-note-history": lambda *_: self.go_page("note-history"),
            "go-muhasabah": lambda *_: self.go_page("muhasabah"),
            "go-manage": lambda *_: self.go_page("manage"),
            "go-settings": lambda *_: self.go_page("settings"),
            "prev-day": lambda *_: self._go_to_today(self._today_page.go_previous_day),
            "next-day": lambda *_: self._go_to_today(self._today_page.go_next_day),
            "today": lambda *_: self._go_to_today(self._today_page.go_today),
            "new-worship": lambda *_: self.open_worship_dialog(),
            "new-habit": lambda *_: self.open_habit_dialog(),
            "undo": lambda *_: self.undo(),
            "shortcuts": lambda *_: self._show_shortcuts(),
            "search": lambda *_: self._on_search(),
        }
        for name, callback in actions.items():
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

    def _make_today_page(self):
        from .today_page import TodayPage

        return TodayPage(
            self._repo,
            on_add_worship=lambda: self.open_worship_dialog(),
            on_add_habit=lambda: self.open_habit_dialog(),
            on_data_changed=self.refresh_history,
        )

    def _make_history_page(self):
        from .history_page import HistoryPage

        return HistoryPage(
            self._repo,
            on_open_day=self._open_day,
            on_open_calendar=self._go_calendar,
            on_toast=self._toast,
        )

    def _make_calendar_page(self):
        from .calendar_page import CalendarPage

        return CalendarPage(
            self._repo,
            on_open_day=self._open_day,
            on_toast=self._toast,
        )

    def _make_note_history_page(self):
        from .note_history_page import NoteHistoryPage

        return NoteHistoryPage(
            self._repo,
            on_open_day=self._open_day,
            on_toast=self._toast,
        )

    def _make_muhasabah_page(self):
        from .muhasabah_page import MuhasabahPage

        return MuhasabahPage(self._repo, on_toast=self._toast)

    def _make_manage_page(self):
        from .manage_page import ManagePage

        return ManagePage(
            self._repo,
            on_add_worship=self.open_worship_dialog,
            on_add_habit=self.open_habit_dialog,
            on_toast=self._toast,
            on_data_changed=self.refresh_today_and_history,
        )

    def _make_settings_page(self):
        from .settings_page import SettingsPage

        return SettingsPage(
            self._repo,
            on_theme_changed=apply_theme,
            on_toast=self._toast,
            on_data_changed=self.refresh_all,
            on_test_notification=self._send_test_notification,
        )

    # -- navigasi --------------------------------------------------------

    def go_page(self, name: str) -> None:
        self._stack.set_visible_child_name(name)
        self._hide_sidebar_when_collapsed()

    def _go_history(self, mode: str) -> None:
        self.go_page("history")
        self._history_page.set_mode(mode)

    def _go_calendar(self, day: date | None = None) -> None:
        """Buka Kalender; bila ``day`` diberikan, arahkan ke bulan itu."""

        self.go_page("calendar")
        if day is None:
            self._calendar_page.refresh()
        else:
            self._calendar_page.go_to_month(day)

    def _open_day(self, day: date) -> None:
        self.go_page("today")
        self._today_page.set_day(day)

    def _on_search(self) -> None:
        if self._stack.get_visible_child_name() == "note-history":
            self._note_history_page.focus_search()
            return
        self.go_page("muhasabah")
        self._muhasabah_page.focus_search()

    def refresh_history(self) -> None:
        self._history_page.refresh()
        self._calendar_page.refresh()
        self._note_history_page.refresh()

    def refresh_today_and_history(self) -> None:
        self._today_page.refresh()
        self.refresh_history()

    def refresh_all(self) -> None:
        self.refresh_today_and_history()
        self._manage_page.refresh()
        self._muhasabah_page.refresh()
        self._settings_page.refresh()
        apply_theme(self._repo.get_setting(SETTING_THEME, "sistem"))

    def _hide_sidebar_when_collapsed(self) -> None:
        if self._split.get_collapsed():
            self._split.set_show_content(True)

    def _on_toggle_sidebar(self, _button: Gtk.Button) -> None:
        if self._split.get_collapsed():
            self._split.set_show_content(not self._split.get_show_content())
        else:
            self._split.set_show_sidebar(not self._split.get_show_sidebar())

    def _on_page_changed(self, *_args: object) -> None:
        name = self._stack.get_visible_child_name() or "today"
        title = name
        page = self._stack.get_page(self._stack.get_visible_child())
        if page is not None:
            title = page.get_title() or title
        self._window_title.set_title(title)
        self._content_page.set_title(title)

        hints = {
            "note-history": ("Cari catatan harian (Ctrl+F)", "Cari catatan harian"),
            "muhasabah": ("Cari muhasabah (Ctrl+F)", "Cari muhasabah"),
        }
        tooltip, label = hints.get(name, ("Cari catatan (Ctrl+F)", "Cari catatan"))
        self._search_button.set_tooltip_text(tooltip)
        set_accessible_label(self._search_button, label)

    def _go_to_today(self, action: Callable[[], None]) -> None:
        self.go_page("today")
        action()

    # -- dialog dan notifikasi -------------------------------------------

    def open_worship_dialog(
        self, worship_id: int | None = None, *, habit: bool = False
    ) -> None:
        from .worship_dialog import WorshipDialog

        worship = None if worship_id is None else self._repo.get_worship(worship_id)
        is_habit = habit or (
            worship is not None and worship.category_name == HABIT_CATEGORY
        )
        dialog = WorshipDialog(
            self._repo,
            self._repo.list_categories(),
            worship=worship,
            habit=is_habit,
            on_saved=(
                lambda item_id: self._on_worship_saved(item_id, habit=is_habit)
            ),
        )
        dialog.present(self)

    def open_habit_dialog(self, worship_id: int | None = None) -> None:
        """Buka dialog dengan preset dan kategori Kebiasaan."""

        self.open_worship_dialog(worship_id, habit=True)

    def _on_worship_saved(self, _worship_id: int, *, habit: bool = False) -> None:
        self.refresh_all()
        self._toast(
            "Kebiasaan tersimpan" if habit else "Ibadah tersimpan", None, None
        )

    def _toast(
        self,
        message: str,
        button_label: str | None,
        callback: Callable[[], None] | None,
    ) -> None:
        toast = Adw.Toast.new(message)
        if button_label and callback is not None:
            if button_label == "Urungkan":
                self._undo_callback = callback

                def on_dismissed(*_args: object) -> None:
                    if self._undo_callback is callback:
                        self._undo_callback = None

                toast.connect("dismissed", on_dismissed)

            def on_button_clicked(*_args: object) -> None:
                callback()
                self._undo_callback = None

            toast.set_button_label(button_label)
            toast.connect("button-clicked", on_button_clicked)
        self._toast_overlay.add_toast(toast)

    def show_startup_notice(self, message: str) -> None:
        """Tampilkan catatan dari startup setelah jendela tersedia."""

        self._toast(message, None, None)

    # -- pengenalan dan pengingat -----------------------------------------

    def _show_onboarding_if_needed(self) -> bool:
        if self._repo.get_meta(META_ONBOARDING_DONE) == "1":
            return False
        dialog = Adw.AlertDialog(
            heading="Selamat datang di IslamicHabits",
            body=(
                "Catat ibadah dan kebiasaan sendiri, tanpa pengawas. Data tetap di "
                "komputer ini, tanpa akun dan tanpa server. Ibadah serta kebiasaan "
                "bawaan seperti belajar dan olahraga sudah disiapkan.\n\n"
                "Satu kegiatan cukup satu catatan per hari. Arsip menyimpan riwayat, "
                "dan tren harian, bulanan, serta tahunan dihitung sejak kegiatan "
                "mulai aktif."
            ),
        )
        dialog.add_response("start", "Mulai mencatat")
        dialog.set_default_response("start")
        dialog.connect("response", self._on_onboarding_response)
        dialog.present(self)
        return False

    def _on_onboarding_response(self, _dialog: Adw.AlertDialog, response: str) -> None:
        if response != "start":
            return
        self._repo.set_meta(META_ONBOARDING_DONE, "1")

    def _check_reminder(self) -> bool:
        if self._repo.get_setting(SETTING_REMINDER_ENABLED, "0") != "1":
            return True
        target = self._repo.get_setting(SETTING_REMINDER_TIME, "20:00")
        try:
            target = datetime.strptime(target, "%H:%M").strftime("%H:%M")
        except ValueError:
            return True

        now = datetime.now()
        if now.strftime("%H:%M") >= target and self._reminder_day != now.date():
            self._reminder_day = now.date()
            if self._repo.get_setting(SETTING_REMINDER_POPUP, "1") == "1":
                self._send_notification(
                    "IslamicHabits",
                    "Waktunya mencatat ibadah dan menulis catatan hari ini.",
                )
            self._toast(
                "Waktunya mencatat ibadah dan menulis muhasabah.",
                "Buka Muhasabah",
                self.open_muhasabah_today,
            )
        return True

    def _send_notification(self, title: str, body: str) -> None:
        """Kirim popup notifikasi desktop; aman bila aplikasi belum terdaftar."""

        application = self.get_application()
        if application is None:
            return
        notification = Gio.Notification.new(title)
        notification.set_body(body)
        notification.set_priority(Gio.NotificationPriority.NORMAL)
        notification.set_default_action("app.open-muhasabah")
        try:
            application.send_notification("islamichabits-reminder", notification)
        except Exception:
            # Notifikasi tidak boleh menghalangi pencatatan bila desktop
            # menolaknya atau belum memberikan izin.
            pass

    def _send_test_notification(self, *_args: object) -> None:
        self._send_notification(
            "IslamicHabits", "Ini contoh popup pemberitahuan IslamicHabits."
        )
        self._toast("Notifikasi uji dikirim", None, None)

    def open_muhasabah_today(self) -> None:
        """Buka Muhasabah pada hari ini, dipakai toast dan notifikasi."""

        self._muhasabah_page.go_today()
        self.go_page("muhasabah")

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
                    ("Kalender", "<Ctrl>2"),
                    ("Riwayat (tahunan)", "<Ctrl>3"),
                    ("Histori Catatan", "<Ctrl>4"),
                ),
            ),
            (
                "Ibadah & kebiasaan",
                (
                    ("Ibadah baru", "<Ctrl>N"),
                    ("Kebiasaan baru", "<Ctrl><Shift>N"),
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
