"""Titik masuk aplikasi IslamicHabits."""

from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio

from .logic.constants import APP_ID
from .logic.database import connect
from .logic.repository import Repository
from .ui.main_window import MainWindow


class IslamicHabitsApplication(Adw.Application):
    """Aplikasi GNOME satu jendela."""

    repository: Repository

    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)

        self.repository = Repository(connect())

        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_action: self.quit())
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<Ctrl>Q"])

        self.set_accels_for_action("win.prev-day", ["<Ctrl>Left"])
        self.set_accels_for_action("win.next-day", ["<Ctrl>Right"])
        self.set_accels_for_action("win.today", ["<Ctrl>T"])
        # Ctrl+1/2/3 akan menjadi harian/bulanan/tahunan saat Riwayat dibuat.
        self.set_accels_for_action("win.go-history", ["<Ctrl>1", "<Ctrl>2", "<Ctrl>3"])
        self.set_accels_for_action("win.go-settings", ["<Ctrl>comma"])
        self.set_accels_for_action("win.new-worship", ["<Ctrl>N"])
        self.set_accels_for_action("win.search", ["<Ctrl>F"])
        self.set_accels_for_action("win.undo", ["<Ctrl>Z"])
        self.set_accels_for_action("win.shortcuts", ["<Ctrl>question"])

    def do_activate(self) -> None:
        window = self.props.active_window
        if window is None:
            window = MainWindow(application=self, repository=self.repository)
        window.present()

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
