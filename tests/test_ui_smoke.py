"""Smoke test headless untuk memastikan halaman GTK bisa dibuat."""

from __future__ import annotations

import unittest

try:
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw

    GTK_TERSEDIA = True
except Exception:  # pragma: no cover - bergantung pada lingkungan
    GTK_TERSEDIA = False

if GTK_TERSEDIA:
    from src.logic.database import connect
    from src.logic.repository import Repository
    from src.ui.history_page import HistoryPage
    from src.ui.muhasabah_page import MuhasabahPage
    from src.ui.settings_page import SettingsPage
    from src.ui.today_page import TodayPage
    from src.ui.trend_line import TrendLine


@unittest.skipUnless(GTK_TERSEDIA, "GTK4/libadwaita tidak tersedia")
class UiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Adw.init()

    def setUp(self) -> None:
        self.connection = connect(":memory:")
        self.addCleanup(self.connection.close)
        self.repo = Repository(self.connection)

    @staticmethod
    def _toast(*_args: object) -> None:
        return None

    def test_semua_halaman_dapat_dibuat_tanpa_jendela(self) -> None:
        today = TodayPage(
            self.repo,
            on_add_worship=lambda: None,
            on_data_changed=lambda: None,
        )
        history = HistoryPage(
            self.repo,
            on_open_day=lambda _day: None,
            on_toast=self._toast,
        )
        muhasabah = MuhasabahPage(self.repo, on_toast=self._toast)
        settings = SettingsPage(
            self.repo,
            on_theme_changed=lambda _theme: None,
            on_toast=self._toast,
            on_data_changed=lambda: None,
        )

        for page in (today, history, muhasabah, settings):
            self.assertIsNotNone(page.get_first_child())

    def test_garis_tren_bisa_difokus(self) -> None:
        self.assertTrue(TrendLine().get_focusable())


if __name__ == "__main__":
    unittest.main()
