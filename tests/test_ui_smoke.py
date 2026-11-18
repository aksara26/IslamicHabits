"""Smoke test headless untuk memastikan halaman GTK bisa dibuat."""

from __future__ import annotations

import unittest
from datetime import date, timedelta

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
    from src.logic.statistics import EntryKind
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
            on_test_notification=lambda: None,
        )

        for page in (today, history, muhasabah, settings):
            self.assertIsNotNone(page.get_first_child())

    def test_kartu_catatan_harian_tersimpan(self) -> None:
        today = TodayPage(
            self.repo,
            on_add_worship=lambda: None,
            on_data_changed=lambda: None,
        )
        buffer = today._note_view.get_buffer()
        buffer.set_text("Catatan dari halaman Hari Ini")
        today._save_note_now()
        self.assertEqual(
            self.repo.get_daily_note(date.today()).text,
            "Catatan dari halaman Hari Ini",
        )

    def test_kalender_menampilkan_capaian_dan_catatan_hari_lalu(self) -> None:
        day = date.today() - timedelta(days=1)
        worship = self.repo.add_worship(
            name="Subuh kemarin",
            kind=EntryKind.CHECK,
            active_from=day,
        )
        self.repo.set_entry(
            worship.id, day, value=True, note="catatan ibadah kemarin"
        )
        self.repo.save_daily_note(day, "Catatan harian kemarin")

        history = HistoryPage(
            self.repo,
            on_open_day=lambda _day: None,
            on_toast=self._toast,
        )
        history.go_to_day(day)
        history.set_mode("month")

        self.assertEqual(history._views.get_visible_child_name(), "month")
        self.assertIn(
            "Terlaksana 1 dari 1 ibadah",
            history._calendar_detail_state.get_label(),
        )
        self.assertIn("●", history._calendar_detail_state.get_label())

        rows = []
        child = history._calendar_detail_list.get_first_child()
        while child is not None:
            rows.append(child)
            child = child.get_next_sibling()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get_title(), "Subuh kemarin")
        self.assertIn("Selesai", rows[0].get_subtitle())
        self.assertIn("catatan ibadah kemarin", rows[0].get_subtitle())
        self.assertIn(
            "Catatan harian kemarin", history._calendar_detail_note.get_label()
        )

        history.set_mode("day")
        self.assertIn("Catatan harian kemarin", history._day_note_text.get_label())

    def test_garis_tren_bisa_difokus(self) -> None:
        self.assertTrue(TrendLine().get_focusable())


if __name__ == "__main__":
    unittest.main()
