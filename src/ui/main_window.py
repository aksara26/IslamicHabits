"""Jendela utama IslamicHabits (masih kerangka kosong)."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw

from ..logic.constants import APP_NAME

__all__ = ["MainWindow"]


class MainWindow(Adw.ApplicationWindow):
    """Satu jendela dengan header bar dan placeholder tenang.

    Halaman Hari Ini, Riwayat, Muhasabah, dan pengaturan akan dipasang di
    area konten pada langkah berikutnya.
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)

        self.set_title(APP_NAME)
        self.set_default_size(880, 620)
        self.set_size_request(420, 320)

        view = Adw.ToolbarView()
        view.add_top_bar(Adw.HeaderBar())

        placeholder = Adw.StatusPage(
            title="IslamicHabits",
            description=(
                "Kerangka jendela sudah berjalan. Halaman Hari Ini akan "
                "dibuat berikutnya."
            ),
            icon_name="io.github.kurakura.IslamicHabits",
        )
        view.set_content(placeholder)
        self.set_content(view)
