"""Smoke test headless untuk memastikan halaman GTK bisa dibuat."""

from __future__ import annotations

import os
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

# Adw.init() memerlukan sesi tampilan. CI tanpa X/Wayland akan melewati smoke
# test GTK, sedangkan pengujian logika tetap berjalan.
DISPLAY_TERSEDIA = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))

if GTK_TERSEDIA:
    from src.logic.database import connect
    from src.logic.repository import Repository
    from src.logic.statistics import EntryKind
    from src.ui.calendar_page import CalendarPage
    from src.ui.history_page import HistoryPage
    from src.ui.memo_page import MemoPage
    from src.ui.muhasabah_page import MuhasabahPage
    from src.ui.note_history_page import NoteHistoryPage
    from src.ui.settings_page import SettingsPage
    from src.ui.today_page import TodayPage
    from src.ui.trend_line import TrendLine


@unittest.skipUnless(
    GTK_TERSEDIA and DISPLAY_TERSEDIA,
    "GTK4/libadwaita atau sesi tampilan tidak tersedia",
)
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
            on_open_memo=lambda _day: None,
        )
        history = HistoryPage(
            self.repo,
            on_open_day=lambda _day: None,
            on_open_calendar=lambda _day: None,
            on_toast=self._toast,
        )
        calendar = CalendarPage(
            self.repo,
            on_open_day=lambda _day: None,
            on_toast=self._toast,
        )
        notes = NoteHistoryPage(
            self.repo,
            on_open_day=lambda _day: None,
            on_toast=self._toast,
        )
        memo = MemoPage(
            self.repo,
            on_data_changed=lambda: None,
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

        for page in (today, history, calendar, notes, memo, muhasabah, settings):
            self.assertIsNotNone(page.get_first_child())

    def test_memo_tersimpan_dan_kartu_hari_ini_menautkan(self) -> None:
        memo = MemoPage(
            self.repo,
            on_data_changed=lambda: None,
            on_toast=self._toast,
        )
        memo._note_view.get_buffer().set_text("Memo dari halaman Memo")
        memo._save_note_now()
        self.assertEqual(
            self.repo.get_daily_note(date.today()).text,
            "Memo dari halaman Memo",
        )

        opened: list[date] = []
        today = TodayPage(
            self.repo,
            on_add_worship=lambda: None,
            on_data_changed=lambda: None,
            on_open_memo=opened.append,
        )
        self.assertIn("Memo dari halaman Memo", today._note_preview.get_label())
        today._on_open_memo(today.day)
        self.assertEqual(opened, [date.today()])

    def test_halaman_memo_menampilkan_foto(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as folder:
            folder_path = Path(folder)
            repo = Repository(self.connection, photos_dir=folder_path / "memo")
            source = folder_path / "contoh.png"
            source.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 32)
            repo.add_memo_photo(date.today(), source)

            memo = MemoPage(
                repo,
                on_data_changed=lambda: None,
                on_toast=self._toast,
            )
            self.assertEqual(memo._photo_count.get_label(), "1 foto")
            self.assertEqual(memo._photo_stack.get_visible_child_name(), "photos")
            self.assertEqual(len(repo.list_memo_photos(date.today())), 1)

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

        calendar = CalendarPage(
            self.repo,
            on_open_day=lambda _day: None,
            on_toast=self._toast,
        )
        calendar.go_to_day(day)

        self.assertEqual(calendar._calendar_selected, day)
        self.assertIn(
            "Terlaksana 1 dari 1 kegiatan",
            calendar._calendar_detail_state.get_label(),
        )
        self.assertIn("●", calendar._calendar_detail_state.get_label())

        rows = []
        child = calendar._calendar_detail_list.get_first_child()
        while child is not None:
            rows.append(child)
            child = child.get_next_sibling()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get_title(), "Subuh kemarin")
        self.assertIn("Selesai", rows[0].get_subtitle())
        self.assertIn("catatan ibadah kemarin", rows[0].get_subtitle())
        self.assertIn(
            "Catatan harian kemarin", calendar._calendar_detail_note.get_label()
        )

    def test_histori_catatan_harian_hanya_memuat_catatan_harian(self) -> None:
        day = date.today() - timedelta(days=1)
        worship = self.repo.add_worship(
            name="Subuh kemarin", kind=EntryKind.CHECK, active_from=day
        )
        self.repo.set_entry(worship.id, day, value=True, note="catatan ibadah rahasia")
        self.repo.save_muhasabah(day, "muhasabah rahasia")
        self.repo.save_daily_note(day, "Catatan harian kemarin")

        opened: list[date] = []
        page = NoteHistoryPage(
            self.repo,
            on_open_day=opened.append,
            on_toast=self._toast,
        )
        self.assertEqual(len(page._visible_notes), 1)
        self.assertEqual(page._visible_notes[0].text, "Catatan harian kemarin")

        page._search_entry.set_text("rahasia")
        self.assertEqual(page._visible_notes, ())
        page._search_entry.set_text("Catatan harian")
        self.assertEqual(len(page._visible_notes), 1)

        row = page._notes_list.get_row_at_index(0)
        self.assertIsNotNone(row)
        page._notes_list.emit("row-activated", row)
        self.assertEqual(opened, [day])

    def test_riwayat_memiliki_tiga_mode_tren(self) -> None:
        opened: list[date] = []
        history = HistoryPage(
            self.repo,
            on_open_day=lambda _day: None,
            on_open_calendar=opened.append,
            on_toast=self._toast,
        )
        for mode in ("day", "month", "year"):
            history.set_mode(mode)
            self.assertEqual(history._views.get_visible_child_name(), mode)
            self.assertEqual(history._toggle.get_active_name(), mode)

        history._on_month_activated(None, 3)
        self.assertEqual(opened, [date(history._anchor.year, 3, 1)])

    def test_kebiasaan_bawaan_ikut_tercatat_di_hari_ini(self) -> None:
        categories = {item.name for item in self.repo.list_categories()}
        self.assertIn("Kebiasaan", categories)

        names = {item.name for item in self.repo.list_worships()}
        for habit in ("Belajar", "Baca buku", "Olahraga", "Jalan kaki", "Tidur awal"):
            self.assertIn(habit, names)

        today = TodayPage(
            self.repo,
            on_add_worship=lambda: None,
            on_add_habit=lambda: None,
            on_data_changed=lambda: None,
            on_open_memo=lambda _day: None,
        )
        self.assertIn("Belajar", [row.worship.name for row in today._rows.values()])

    def test_kalender_menampilkan_status_pengingat(self) -> None:
        from src.logic.constants import (
            SETTING_REMINDER_ENABLED,
            SETTING_REMINDER_PERMISSION,
            SETTING_REMINDER_TIME,
        )

        self.repo.set_setting(SETTING_REMINDER_ENABLED, "1")
        self.repo.set_setting(SETTING_REMINDER_TIME, "20:30")
        self.repo.set_setting(SETTING_REMINDER_PERMISSION, "0")
        calendar = CalendarPage(
            self.repo,
            on_open_day=lambda _day: None,
            on_toast=self._toast,
        )
        self.assertIn("20:30", calendar._reminder_label.get_label())
        self.assertIn("belum diizinkan", calendar._reminder_label.get_label())

        self.repo.set_setting(SETTING_REMINDER_PERMISSION, "1")
        calendar.refresh()
        self.assertIn("diizinkan", calendar._reminder_label.get_label())

    def test_garis_tren_bisa_difokus(self) -> None:
        self.assertTrue(TrendLine().get_focusable())


if __name__ == "__main__":
    unittest.main()
