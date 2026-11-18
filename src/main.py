"""Titik masuk aplikasi IslamicHabits."""

from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio

from .logic.constants import APP_ID
from .ui.main_window import MainWindow


class IslamicHabitsApplication(Adw.Application):
    """Aplikasi GNOME satu jendela."""

    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)

        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_action: self.quit())
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<Ctrl>Q"])

    def do_activate(self) -> None:
        window = self.props.active_window
        if window is None:
            window = MainWindow(application=self)
        window.present()


def main(argv: list[str] | None = None) -> int:
    """Jalankan aplikasi; mengembalikan kode keluar."""

    # libadwaita perlu diinisialisasi sebelum objek UI dibuat.
    Adw.init()
    app = IslamicHabitsApplication()
    return app.run(argv if argv is not None else sys.argv)


if __name__ == "__main__":
    sys.exit(main())
