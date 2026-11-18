"""Pengujian repository tanpa GTK."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from src.logic.database import connect
from src.logic.repository import DailyNoteRecord, Repository
from src.logic.statistics import EntryKind, StatusValue, compute_daily, compute_range

DAY = date(2026, 11, 18)


class RepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = connect(":memory:", seed=False)
        self.addCleanup(self.connection.close)
        self.repo = Repository(self.connection)
        self.sholat = self.repo.add_category("Sholat")
        self.quran = self.repo.add_category("Al-Qur'an")

    def _check_worship(self, **kwargs: object):
        return self.repo.add_worship(
            name="Subuh",
            category_id=self.sholat.id,
            kind=EntryKind.CHECK,
            active_from=date(2026, 11, 1),
            **kwargs,  # type: ignore[arg-type]
        )

    def test_add_and_list_worships(self) -> None:
        worship = self.repo.add_worship(
            name="Tilawah",
            category_id=self.quran.id,
            kind=EntryKind.NUMBER,
            target=5,
            unit="halaman",
            active_weekdays={0, 3},
            active_from=DAY,
        )
        self.assertEqual(worship.category_name, "Al-Qur'an")
        self.assertEqual(worship.kind, EntryKind.NUMBER)
        self.assertEqual(worship.target, 5)
        self.assertEqual(worship.active_weekdays, frozenset({0, 3}))
        self.assertEqual(worship.active_from, DAY)
        self.assertEqual([item.id for item in self.repo.list_worships()], [worship.id])
        self.assertEqual(self.repo.get_worship(worship.id), worship)

    def test_new_worship_defaults_to_today(self) -> None:
        worship = self.repo.add_worship(name="Baru", kind=EntryKind.CHECK)
        self.assertEqual(worship.active_from, date.today())

    def test_update_worship_keeps_active_from_unless_requested(self) -> None:
        worship = self._check_worship()
        updated = self.repo.update_worship(worship.id, name="Subuh (qadha)", target=2)
        self.assertEqual(updated.name, "Subuh (qadha)")
        self.assertEqual(updated.active_from, date(2026, 11, 1))
        changed = self.repo.update_worship(worship.id, active_from=DAY)
        self.assertEqual(changed.active_from, DAY)

    def test_entries_are_unique_per_worship_and_day(self) -> None:
        worship = self._check_worship()
        first = self.repo.set_entry(worship.id, DAY, value=True, time="05:12", note="tekad")
        self.assertTrue(first.value)
        self.assertEqual(first.time, "05:12")
        self.assertEqual(first.note, "tekad")

        updated = self.repo.set_entry(worship.id, DAY, value=False, note="")
        self.assertFalse(updated.value)
        self.assertIsNone(updated.time)
        self.assertEqual(len(self.repo.list_entries(worship_id=worship.id)), 1)
        self.assertIsNotNone(self.repo.get_entry(worship.id, DAY))

        self.repo.delete_entry(worship.id, DAY)
        self.assertIsNone(self.repo.get_entry(worship.id, DAY))

    def test_number_and_status_values_are_decoded(self) -> None:
        number = self.repo.add_worship(
            name="Tilawah", kind=EntryKind.NUMBER, target=5, active_from=DAY
        )
        status = self.repo.add_worship(
            name="Dzuhur", kind=EntryKind.STATUS, active_from=DAY
        )
        number_entry = self.repo.set_entry(number.id, DAY, value=3)
        status_entry = self.repo.set_entry(status.id, DAY, value=StatusValue.QADHA)
        self.assertEqual(number_entry.value, 3.0)
        self.assertEqual(status_entry.value, StatusValue.QADHA)
        self.assertEqual(status_entry.to_statistics().value, StatusValue.QADHA)

        with self.assertRaises(ValueError):
            self.repo.set_entry(number.id, DAY, value="bukan angka")
        with self.assertRaises(ValueError):
            self.repo.set_entry(status.id, DAY, value="tidak dikenal")
        with self.assertRaises(ValueError):
            self.repo.set_entry(status.id, DAY, value=StatusValue.BELUM, time="25:00")

    def test_archive_restore_and_permanent_delete(self) -> None:
        worship = self._check_worship()
        self.repo.set_entry(worship.id, DAY, value=True)
        self.repo.archive_worship(worship.id, date(2026, 11, 20))
        self.assertEqual(self.repo.list_worships(), ())
        archived = self.repo.list_worships(include_archived=True)
        self.assertEqual(archived[0].archived_on, date(2026, 11, 20))
        self.repo.restore_worship(worship.id)
        self.assertEqual(len(self.repo.list_worships()), 1)

        self.repo.delete_worship(worship.id)
        self.assertEqual(self.repo.list_worships(include_archived=True), ())
        self.assertEqual(self.repo.list_entries(), ())

    def test_statistics_inputs_respect_archive_date(self) -> None:
        worship = self._check_worship()
        self.repo.set_entry(worship.id, date(2026, 11, 5), value=True)
        self.repo.archive_worship(worship.id, date(2026, 11, 10))
        worships, entries = self.repo.statistics_inputs(
            start=date(2026, 11, 1), end=date(2026, 11, 30)
        )
        summary = compute_range(
            date(2026, 11, 1), date(2026, 11, 30), worships, entries
        )[0]
        self.assertEqual(summary.expected_days, 9)
        self.assertEqual(summary.completed_days, 1)
        self.assertEqual(
            len(compute_daily(DAY, worships, entries).per_worship), 0
        )

    def test_reordering(self) -> None:
        first = self._check_worship()
        second = self.repo.add_worship(name="Dzuhur", kind=EntryKind.CHECK, active_from=DAY)
        third = self.repo.add_worship(name="Ashar", kind=EntryKind.CHECK, active_from=DAY)
        self.repo.reorder_worships([third.id, first.id, second.id])
        self.assertEqual(
            [item.id for item in self.repo.list_worships()],
            [third.id, first.id, second.id],
        )

    def test_categories_can_be_renamed_collapsed_and_reordered(self) -> None:
        third = self.repo.add_category("Amal")
        self.repo.rename_category(third.id, "Sedekah")
        self.repo.set_category_collapsed(third.id, True)
        self.repo.reorder_categories([third.id, self.sholat.id, self.quran.id])
        categories = self.repo.list_categories()
        self.assertEqual(categories[0].name, "Sedekah")
        self.assertTrue(categories[0].collapsed)

    def test_muhasabah_and_settings(self) -> None:
        empty = self.repo.get_muhasabah(DAY)
        self.assertEqual(empty.text, "")
        self.repo.save_muhasabah(DAY, "Hari ini cukup tenang.", "hadir")
        saved = self.repo.get_muhasabah(DAY)
        self.assertEqual(saved.text, "Hari ini cukup tenang.")
        self.assertEqual(saved.answers, "hadir")

        self.repo.delete_muhasabah(DAY)
        self.assertEqual(self.repo.get_muhasabah(DAY).text, "")
        self.assertEqual(self.repo.list_muhasabah(), ())

        self.assertEqual(self.repo.get_setting("tema", "sistem"), "sistem")
        self.repo.set_setting("tema", "gelap")
        self.assertEqual(self.repo.get_setting("tema"), "gelap")
        self.repo.set_meta("cadangan_terakhir", DAY.isoformat())
        self.assertEqual(self.repo.get_meta("cadangan_terakhir"), DAY.isoformat())

    def test_daily_notes_are_saved_listed_and_deleted(self) -> None:
        self.assertEqual(self.repo.get_daily_note(DAY), DailyNoteRecord(DAY, ""))

        self.repo.save_daily_note(DAY, "  Banyak membaca hari ini.  ")
        self.assertEqual(
            self.repo.get_daily_note(DAY),
            DailyNoteRecord(DAY, "Banyak membaca hari ini."),
        )

        previous = DAY - timedelta(days=1)
        self.repo.save_daily_note(previous, "Kemarin sempat qadha.")
        notes = self.repo.list_daily_notes(
            start=previous, end=DAY + timedelta(days=1)
        )
        self.assertEqual([item.day for item in notes], [DAY, previous])

        self.repo.save_daily_note(DAY, "   ")
        self.assertEqual(self.repo.get_daily_note(DAY).text, "")
        self.repo.delete_daily_note(previous)
        self.assertEqual(self.repo.list_daily_notes(), ())

    def test_clear_all_data_removes_daily_notes(self) -> None:
        self.repo.save_daily_note(DAY, "Catatan yang harus hilang.")
        self.repo.clear_all_data()
        self.assertEqual(self.repo.list_daily_notes(), ())

    def test_photo_memo_is_copied_listed_and_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            folder_path = Path(folder)
            repo = Repository(self.connection, photos_dir=folder_path / "memo")
            source = folder_path / "pagi.jpg"
            source.write_bytes(b"\xff\xd8\xff" + b"x" * 32)

            photo = repo.add_memo_photo(DAY, source, caption="Suasana pagi")
            self.assertEqual(photo.day, DAY)
            self.assertEqual(photo.caption, "Suasana pagi")
            self.assertTrue(repo.photo_path(photo).is_file())
            self.assertEqual(repo.list_memo_photos(DAY), (photo,))
            self.assertEqual(repo.get_daily_note(DAY).photo_count, 1)
            self.assertEqual(repo.list_daily_notes()[0].photo_count, 1)

            repo.delete_memo_photo(photo.id)
            self.assertFalse(repo.photo_path(photo).is_file())
            self.assertEqual(repo.list_memo_photos(DAY), ())
            self.assertEqual(repo.list_daily_notes(), ())

    def test_photo_rejects_unsupported_extension(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            folder_path = Path(folder)
            repo = Repository(self.connection, photos_dir=folder_path / "memo")
            source = folder_path / "catatan.txt"
            source.write_text("bukan foto", encoding="utf-8")
            with self.assertRaises(ValueError):
                repo.add_memo_photo(DAY, source)

    def test_clear_all_data_removes_photo_files(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            folder_path = Path(folder)
            repo = Repository(self.connection, photos_dir=folder_path / "memo")
            source = folder_path / "foto.png"
            source.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 32)
            photo = repo.add_memo_photo(DAY, source)
            path = repo.photo_path(photo)

            repo.clear_all_data()

            self.assertFalse(path.exists())
            self.assertEqual(repo.list_memo_photos(DAY), ())

    def test_update_memo_caption_keeps_the_photo_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            folder_path = Path(folder)
            repo = Repository(self.connection, photos_dir=folder_path / "memo")
            source = folder_path / "pagi.jpg"
            source.write_bytes(b"\xff\xd8\xff" + b"x" * 32)
            photo = repo.add_memo_photo(DAY, source, caption="Awal")

            updated = repo.update_memo_caption(photo.id, "  Suasana baru  ")

            self.assertIsNotNone(updated)
            assert updated is not None
            self.assertEqual(updated.caption, "Suasana baru")
            self.assertTrue(repo.photo_path(updated).is_file())
            self.assertIsNone(repo.update_memo_caption(9999, "tidak ada"))

    def test_search_all_mencari_ke_semua_sumber(self) -> None:
        worship = self.repo.add_worship(
            name="Subuh",
            category_id=self.sholat.id,
            kind=EntryKind.CHECK,
            active_from=date(2026, 11, 1),
        )
        self.repo.save_daily_note(DAY, "Syukur pagi ini")
        self.repo.save_muhasabah(DAY, "Refleksi sabar", "Jawaban syukur")
        self.repo.set_entry(worship.id, DAY, value=True, note="Tepat waktu")

        self.assertEqual(self.repo.search_all("s"), ())

        hits = self.repo.search_all("syukur")
        self.assertEqual({hit.kind for hit in hits}, {"memo", "muhasabah"})
        self.assertTrue(all(hit.day == DAY for hit in hits))

        entry_hits = self.repo.search_all("tepat")
        self.assertEqual(len(entry_hits), 1)
        self.assertEqual(entry_hits[0].kind, "entry")
        self.assertEqual(entry_hits[0].title, "Subuh")
        self.assertEqual(entry_hits[0].worship_id, worship.id)

        worship_hits = self.repo.search_all("sub")
        self.assertEqual(worship_hits[0].kind, "worship")
        self.assertEqual(worship_hits[0].worship_id, worship.id)

        self.assertEqual(self.repo.search_all("tidak ada"), ())


if __name__ == "__main__":
    unittest.main()
