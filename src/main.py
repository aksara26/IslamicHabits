"""Titik masuk aplikasi IslamicHabits."""

from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio

from .logic.constants import APP_ID, SETTING_THEME
from .logic.database import connect
from .logic.repository import Repository
from .logic.transfer import maybe_backup
from .ui.main_window import MainWindow
from .ui.theme import apply_theme, load_stylesheet


class IslamicHabitsApplication(Adw.Application):
    """Aplikasi GNOME satu jendela."""

    repository: Repository
    startup_notice: str | None

    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.startup_notice = None

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)

        self.repository = Repository(connect())

        apply_theme(self.repository.get_setting(SETTING_THEME, "sistem"))
        load_stylesheet()
        try:
            maybe_backup(self.repository)
        except OSError as error:
            # Cadangan bukan syarat aplikasi dibuka. Catatan ini ditampilkan
            # sekali setelah jendela tersedia.
            self.startup_notice = (
                f"Cadangan otomatis tidak tersimpan: {error}. "
                "Pilih folder cadangan di Pengaturan bila perlu."
            )

        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_action: self.quit())
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<Ctrl>Q"])

        open_muhasabah = Gio.SimpleAction.new("open-muhasabah", None)
        open_muhasabah.connect("activate", self._on_open_muhasabah)
        self.add_action(open_muhasabah)

        self.set_accels_for_action("win.prev-day", ["<Ctrl>Left"])
        self.set_accels_for_action("win.next-day", ["<Ctrl>Right"])
        self.set_accels_for_action("win.today", ["<Ctrl>T"])
        self.set_accels_for_action("win.history-day", ["<Ctrl>1"])
        self.set_accels_for_action("win.go-calendar", ["<Ctrl>2"])
        self.set_accels_for_action("win.history-year", ["<Ctrl>3"])
        self.set_accels_for_action("win.go-note-history", ["<Ctrl>4"])
        self.set_accels_for_action("win.go-settings", ["<Ctrl>comma"])
        self.set_accels_for_action("win.new-worship", ["<Ctrl>N"])
        self.set_accels_for_action("win.search", ["<Ctrl>F"])
        self.set_accels_for_action("win.undo", ["<Ctrl>Z"])
        self.set_accels_for_action("win.shortcuts", ["<Ctrl>question"])

    def _on_open_muhasabah(self, *_args: object) -> None:
        window = self.props.active_window
        if window is None:
            window = MainWindow(application=self, repository=self.repository)
        window.present()
        window.open_muhasabah_today()

    def do_activate(self) -> None:
        window = self.props.active_window
        if window is None:
            window = MainWindow(application=self, repository=self.repository)
        window.present()
        if self.startup_notice is not None:
            window.show_startup_notice(self.startup_notice)
            self.startup_notice = None

    def do_shutdown(self) -> None:
        if hasattr(self, "repository"):
            self.repository.close()
        Adw.Application.do_shutdown(self)


def main(argv: list[str] | None = None) -> int:
    """Jalankan aplikasi; mengembalikan kode keluar."""

    # libadwaita perlu diinisialisasi sebelum objek UI dibuat.
    Adw.init()
    app = IslamicHabitsApplication()
    return app.run(argv if argv is not None else sys.argv)


if __name__ == "__main__":
    sys.exit(main())
