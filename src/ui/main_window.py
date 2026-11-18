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
    SETTING_REMINDER_PERMISSION,
    SETTING_REMINDER_POPUP,
    SETTING_REMINDER_TIME,
    SETTING_THEME,
)
from ..logic.defaults import HABIT_CATEGORY
from ..logic.repository import Repository
from ..logic.statistics import compute_daily
from .a11y import set_accessible_label
from .theme import THEME_KEYS, apply_theme, normalize_theme

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
        self._memo_page = self._make_memo_page()
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
            self._memo_page,
            "memo",
            "Memo",
            "insert-image-symbolic",
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

        from .search_popover import SearchPopover

        self._search_popover = SearchPopover(
            self._repo,
            on_open_memo=self._open_memo,
            on_open_muhasabah=self._open_muhasabah_day,
            on_open_day=self._open_day,
            on_open_worship=lambda worship_id: self.open_worship_dialog(worship_id),
        )
        search_button = Gtk.MenuButton()
        search_button.set_icon_name("system-search-symbolic")
        search_button.set_popover(self._search_popover)
        search_button.set_tooltip_text(
            "Cari memo, muhasabah, dan catatan ibadah (Ctrl+F)"
        )
        set_accessible_label(search_button, "Cari semua catatan")
        content_header.pack_end(search_button)
        self._search_button = search_button

        add_menu = Gio.Menu()
        add_menu.append("Ibadah baru", "win.new-worship")
        add_menu.append("Kebiasaan baru", "win.new-habit")
        add_button = Gtk.MenuButton(
            icon_name="list-add-symbolic",
            menu_model=add_menu,
            tooltip_text=(
                "Tambah ibadah (Ctrl+N) atau kebiasaan (Ctrl+Shift+N)"
            ),
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
            "go-memo": lambda *_: self.go_page("memo"),
            "go-muhasabah": lambda *_: self.go_page("muhasabah"),
            "go-manage": lambda *_: self.go_page("manage"),
            "go-settings": lambda *_: self.go_page("settings"),
            "prev-day": lambda *_: self._go_to_today(self._today_page.go_previous_day),
            "next-day": lambda *_: self._go_to_today(self._today_page.go_next_day),
            "today": lambda *_: self._go_to_today(self._today_page.go_today),
            "new-worship": lambda *_: self.open_worship_dialog(),
            "new-habit": lambda *_: self.open_habit_dialog(),
            "save-memo": lambda *_: self._save_memo(),
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
            on_open_memo=self._open_memo,
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
            on_open_memo=self._open_memo,
            on_open_settings=lambda: self.go_page("settings"),
            on_toast=self._toast,
        )

    def _make_memo_page(self):
        from .memo_page import MemoPage

        return MemoPage(
            self._repo,
            on_data_changed=self._on_memo_changed,
            on_toast=self._toast,
        )

    def _on_memo_changed(self) -> None:
        """Segarkan halaman lain tanpa memuat ulang editor Memo yang aktif."""

        self._today_page.refresh()
        self._history_page.refresh()
        self._calendar_page.refresh()

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

    def _open_memo(self, day: date) -> None:
        """Buka halaman Memo pada tanggal tertentu."""

        self.go_page("memo")
        self._memo_page.set_day(day)

    def _on_search(self) -> None:
        """Buka pencarian global tanpa berpindah halaman lebih dulu."""

        self._search_button.popup()
        GLib.idle_add(self._search_popover.focus)

    def _open_muhasabah_day(self, day: date) -> None:
        self.go_page("muhasabah")
        self._muhasabah_page.set_day(day)

    def _save_memo(self) -> None:
        """Simpan memo hanya saat halamannya aktif.

        Pintasan ``Ctrl+S`` terdaftar global, jadi tanpa penjagaan ini menekan
        Ctrl+S di halaman lain akan menulis memo tanggal terakhir yang dibuka
        dan menampilkan toast yang membingungkan.
        """

        if self._stack.get_visible_child_name() == "memo":
            self._memo_page.save_now()

    def refresh_history(self) -> None:
        self._history_page.refresh()
        self._calendar_page.refresh()
        self._memo_page.refresh()

    def refresh_today_and_history(self) -> None:
        self._today_page.refresh()
        self.refresh_history()

    def refresh_all(self) -> None:
        self.refresh_today_and_history()
        self._manage_page.refresh()
        self._muhasabah_page.refresh()
        self._settings_page.refresh()
        apply_theme(
            normalize_theme(
                self._repo.get_setting(SETTING_THEME, THEME_KEYS[0])
            )
        )

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

        self._search_button.set_tooltip_text(
            "Cari memo, muhasabah, dan catatan ibadah (Ctrl+F)"
        )
        set_accessible_label(self._search_button, "Cari semua catatan")

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
        self._check_daily_reminder()
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
            worships, entries = self._repo.statistics_inputs(
                start=now.date(), end=now.date()
            )
            summary = compute_daily(now.date(), worships, entries)
            note = self._repo.get_daily_note(now.date())
            complete = summary.expected > 0 and summary.completed >= summary.expected
            has_memo = bool(note.text.strip()) or note.photo_count > 0
            if complete and has_memo:
                return True
            popup = self._repo.get_setting(SETTING_REMINDER_POPUP, "1") == "1"
            if popup:
                self._send_notification(
                    "IslamicHabits",
                    "Waktunya mencatat ibadah dan menulis memo hari ini.",
                )
            self._toast(
                "Waktunya mencatat ibadah dan menulis memo hari ini.",
                "Buka Memo",
                lambda: self._open_memo(now.date()),
            )
        return True

    def _check_daily_reminder(self, now: datetime | None = None) -> bool:
        """Kirim pengingat tanggal hari ini sekali saat jamnya tiba.

        Pengingat per tanggal berbeda dari pengingat harian di Pengaturan.
        Yang diperiksa hanya pengingat hari ini; tanggal lampau dan mendatang
        tetap tersimpan sebagai catatan tanpa memicu notifikasi susulan.
        """

        moment = now or datetime.now()
        reminder = self._repo.get_reminder(moment.date())
        if reminder.sent or not reminder.text.strip() or not reminder.time:
            return True
        try:
            target = datetime.strptime(reminder.time, "%H:%M").strftime("%H:%M")
        except ValueError:
            return True
        if moment.strftime("%H:%M") < target:
            return True

        self._repo.mark_reminder_sent(moment.date())
        body = reminder.text.strip()
        if self._repo.get_setting(SETTING_REMINDER_POPUP, "1") == "1":
            self._send_notification(f"Pengingat {target}", body)
        self._toast(
            f"Pengingat {target}: {body}",
            "Buka Memo",
            lambda: self._open_memo(moment.date()),
        )
        return True

    def _send_notification(self, title: str, body: str) -> bool:
        """Kirim popup notifikasi desktop setelah izin pengguna diberikan."""

        if self._repo.get_setting(SETTING_REMINDER_PERMISSION, "0") != "1":
            return False
        application = self.get_application()
        if application is None:
            return False
        notification = Gio.Notification.new(title)
        notification.set_body(body)
        notification.set_priority(Gio.NotificationPriority.NORMAL)
        notification.set_default_action("app.open-memo")
        try:
            application.send_notification("islamichabits-reminder", notification)
        except Exception:
            # Notifikasi tidak boleh menghalangi pencatatan bila desktop
            # menolaknya atau belum memberikan izin.
            return False
        return True

    def _send_test_notification(self, *_args: object) -> None:
        sent = self._send_notification(
            "IslamicHabits", "Ini contoh popup pemberitahuan IslamicHabits."
        )
        if sent:
            self._toast("Notifikasi uji dikirim", None, None)
        else:
            self._toast(
                "Popup belum diizinkan. Aktifkan izin di Pengaturan.",
                "Buka Pengaturan",
                lambda: self.go_page("settings"),
            )

    def open_muhasabah_today(self) -> None:
        """Buka Muhasabah pada hari ini, dipakai toast dan notifikasi."""

        self._muhasabah_page.go_today()
        self.go_page("muhasabah")

    def open_memo_today(self) -> None:
        """Buka Memo pada hari ini, dipakai aksi notifikasi desktop."""

        self._open_memo(date.today())

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
                    ("Muhasabah", "<Ctrl>4"),
                    ("Memo", "<Ctrl>5"),
                ),
            ),
            (
                "Ibadah & catatan",
                (
                    ("Ibadah baru", "<Ctrl>N"),
                    ("Kebiasaan baru", "<Ctrl><Shift>N"),
                    ("Simpan memo", "<Ctrl>S"),
                    ("Urungkan", "<Ctrl>Z"),
                    ("Cari semua catatan", "<Ctrl>F"),
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
