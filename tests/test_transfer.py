"""Pengujian ekspor, impor, dan cadangan tanpa GTK."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from src.logic.constants import (
    EXPORT_FORMAT,
    EXPORT_VERSION,
    META_LAST_BACKUP,
    SCHEMA_VERSION,
    SETTING_BACKUP_FOLDER,
)
from src.logic.database import connect
from src.logic.repository import Repository
from src.logic.statistics import EntryKind
from src.logic.transfer import (
    TransferError,
    backup_due,
    backup_folder,
    create_backup,
    create_export,
    describe_import,
    import_payload,
    maybe_backup,
    parse_export,
    validate_payload,
    write_export,
)

class TransferTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = connect(":memory:")
        self.addCleanup(self.connection.close)
        self.repo = Repository(self.connection)

    def _check_worship_id(self) -> int:
        return next(
            item.id
            for item in self.repo.list_worships()
            if item.kind is EntryKind.CHECK
        )

    def _sample_payload(self) -> dict:
        return {
            "format": EXPORT_FORMAT,
            "schema_version": SCHEMA_VERSION,
            "export_version": EXPORT_VERSION,
            "app_version": "0.1.0",
            "exported_at": "2026-11-18T00:00:00+00:00",
            "data": {
                "kategori": [{"id": 100, "nama": "Impor", "urutan": 0, "lipat": 0}],
                "ibadah": [
                    {
                        "id": 200,
                        "nama": "Ibadah impor",
                        "kategori_id": 100,
                        "jenis": "centang",
                        "target": None,
                        "satuan": "",
                        "hari_aktif": 127,
                        "aktif_mulai": "2026-11-01",
                        "diarsipkan_pada": None,
                        "urutan": 0,
                    }
                ],
                "catatan": [
                    {
                        "ibadah_id": 200,
                        "tanggal": "2026-11-18",
                        "nilai_bool": 1,
                        "nilai_angka": None,
                        "nilai_status": None,
                        "jam": "05:10",
                        "catatan": "dari impor",
                    }
                ],
                "muhasabah": [
                    {"tanggal": "2026-11-18", "teks": "Renungan", "jawaban": "hadir"}
                ],
                "catatan_harian": [
                    {"tanggal": "2026-11-18", "teks": "Catatan dari impor"}
                ],
                "pengaturan": [{"kunci": "tema", "nilai": "gelap"}],
                "meta": [{"kunci": "cadangan_terakhir", "nilai": "2026-11-18"}],
            },
        }

    # -- ekspor ----------------------------------------------------------

    def test_export_contains_all_tables_and_metadata(self) -> None:
        self.repo.set_setting("tema", "terang")
        payload = create_export(self.repo)
        self.assertEqual(payload["format"], EXPORT_FORMAT)
        self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
        self.assertEqual(payload["export_version"], EXPORT_VERSION)
        for table in (
            "kategori",
            "ibadah",
            "catatan",
            "muhasabah",
            "catatan_harian",
            "pengaturan",
            "meta",
        ):
            self.assertIn(table, payload["data"])
        self.assertGreater(len(payload["data"]["ibadah"]), 0)
        self.assertIn("exported_at", payload)

    def test_write_export_and_parse_roundtrip(self) -> None:
        self.repo.set_entry(
            self._check_worship_id(), date(2026, 11, 18), value=True, note="uji"
        )
        self.repo.save_muhasabah(date(2026, 11, 18), "Catatan uji")
        self.repo.set_setting("tema", "gelap")

        with tempfile.TemporaryDirectory() as folder:
            path = write_export(self.repo, Path(folder) / "ekspor.json")
            self.assertTrue(path.exists())
            payload = parse_export(path)
            self.assertEqual(payload["data"]["pengaturan"][0]["nilai"], "gelap")
            self.assertTrue(any(row["catatan"] == "uji" for row in payload["data"]["catatan"]))

            # String JSON juga bisa dibaca langsung.
            from_string = parse_export(path.read_text(encoding="utf-8"))
            self.assertEqual(from_string["data"], payload["data"])

    def test_daily_notes_are_exported_and_imported(self) -> None:
        self.repo.save_daily_note(date(2026, 11, 18), "Catatan harian asli")
        payload = create_export(self.repo)
        self.assertEqual(
            payload["data"]["catatan_harian"],
            [{"tanggal": "2026-11-18", "teks": "Catatan harian asli"}],
        )

        other = Repository(connect(":memory:"))
        self.addCleanup(other.close)
        preview = describe_import(other, payload)
        self.assertEqual(preview.counts["catatan_harian"], 1)
        self.assertEqual(preview.new["catatan_harian"], 1)

        summary = import_payload(other, payload, mode="merge")
        self.assertEqual(summary.inserted["catatan_harian"], 1)
        self.assertEqual(
            other.get_daily_note(date(2026, 11, 18)).text, "Catatan harian asli"
        )

    def test_old_export_without_daily_notes_is_accepted(self) -> None:
        payload = self._sample_payload()
        payload["schema_version"] = 1
        payload["export_version"] = 1
        payload["data"].pop("catatan_harian")

        validate_payload(payload)
        self.assertEqual(describe_import(self.repo, payload).counts["catatan_harian"], 0)

        self.repo.save_daily_note(date(2026, 11, 18), "Catatan lokal tetap ada")
        import_payload(self.repo, payload, mode="merge")
        self.assertEqual(
            self.repo.get_daily_note(date(2026, 11, 18)).text,
            "Catatan lokal tetap ada",
        )

    # -- validasi --------------------------------------------------------

    def test_malformed_json_is_rejected(self) -> None:
        with self.assertRaises(TransferError):
            parse_export("bukan json")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "rusak.json"
            path.write_text("{ rusak", encoding="utf-8")
            with self.assertRaises(TransferError):
                parse_export(path)

    def test_unknown_format_and_versions_are_rejected(self) -> None:
        payload = self._sample_payload()
        payload["format"] = "format-lain"
        with self.assertRaises(TransferError):
            validate_payload(payload)

        payload = self._sample_payload()
        payload["export_version"] = EXPORT_VERSION + 1
        with self.assertRaises(TransferError):
            validate_payload(payload)

        payload = self._sample_payload()
        payload["schema_version"] = SCHEMA_VERSION + 1
        with self.assertRaises(TransferError):
            validate_payload(payload)

        payload = self._sample_payload()
        payload.pop("data")
        with self.assertRaises(TransferError):
            validate_payload(payload)

    def test_foreign_key_validation(self) -> None:
        payload = self._sample_payload()
        payload["data"]["ibadah"][0]["kategori_id"] = 999
        with self.assertRaises(TransferError):
            validate_payload(payload)

        payload = self._sample_payload()
        payload["data"]["catatan"][0]["ibadah_id"] = 999
        with self.assertRaises(TransferError):
            validate_payload(payload)

    def test_duplicate_keys_are_rejected(self) -> None:
        payload = self._sample_payload()
        payload["data"]["kategori"].append(
            {"id": 100, "nama": "Duplikat", "urutan": 1, "lipat": 0}
        )
        with self.assertRaises(TransferError):
            validate_payload(payload)

    def test_invalid_dates_and_status_are_rejected(self) -> None:
        payload = self._sample_payload()
        payload["data"]["catatan"][0]["tanggal"] = "18-11-2026"
        with self.assertRaises(TransferError):
            validate_payload(payload)

        payload = self._sample_payload()
        payload["data"]["catatan"][0]["nilai_status"] = "tidak-dikenal"
        with self.assertRaises(TransferError):
            validate_payload(payload)

        payload = self._sample_payload()
        payload["data"]["ibadah"][0]["hari_aktif"] = 200
        with self.assertRaises(TransferError):
            validate_payload(payload)

    def test_invalid_daily_note_is_rejected(self) -> None:
        payload = self._sample_payload()
        payload["data"]["catatan_harian"][0]["tanggal"] = "18-11-2026"
        with self.assertRaises(TransferError):
            validate_payload(payload)

        payload = self._sample_payload()
        payload["data"]["catatan_harian"][0]["teks"] = 42
        with self.assertRaises(TransferError):
            validate_payload(payload)

    def test_wrong_numeric_types_are_rejected(self) -> None:
        payload = self._sample_payload()
        payload["data"]["ibadah"][0]["id"] = "200"
        with self.assertRaises(TransferError):
            validate_payload(payload)

        payload = self._sample_payload()
        payload["data"]["ibadah"][0]["target"] = "abc"
        with self.assertRaises(TransferError):
            validate_payload(payload)

        payload = self._sample_payload()
        payload["data"]["catatan"][0]["nilai_angka"] = "dua"
        with self.assertRaises(TransferError):
            validate_payload(payload)

        payload = self._sample_payload()
        payload["data"]["muhasabah"][0]["teks"] = 42
        with self.assertRaises(TransferError):
            validate_payload(payload)

    # -- pratinjau dan impor ---------------------------------------------

    def test_preview_counts_new_and_conflicts(self) -> None:
        payload = self._sample_payload()
        preview = describe_import(self.repo, payload)
        self.assertEqual(preview.counts["kategori"], 1)
        self.assertEqual(preview.new["kategori"], 1)
        self.assertEqual(preview.conflicts["kategori"], 0)
        self.assertGreater(preview.total_new, 0)

        # Impor dulu, lalu pratinjau ulang → semua kunci bentrok.
        import_payload(self.repo, payload, mode="merge")
        again = describe_import(self.repo, payload)
        self.assertEqual(again.total_new, 0)
        self.assertGreater(again.total_conflicts, 0)

    def test_merge_import_skips_existing_and_keeps_current(self) -> None:
        before = len(self.repo.list_worships())
        payload = self._sample_payload()
        summary = import_payload(self.repo, payload, mode="merge")
        self.assertEqual(summary.inserted["ibadah"], 1)
        self.assertEqual(len(self.repo.list_worships()), before + 1)
        self.assertEqual(
            self.repo.get_setting("tema"), "gelap"
        )  # pengaturan baru masuk

        # Impor ulang tidak menambah duplikat.
        import_payload(self.repo, payload, mode="merge")
        self.assertEqual(len(self.repo.list_worships()), before + 1)
        entry = self.repo.get_entry(200, date(2026, 11, 18))
        self.assertIsNotNone(entry)
        self.assertEqual(entry.note, "dari impor")  # type: ignore[union-attr]

    def test_replace_import_removes_old_data(self) -> None:
        old = self.repo.get_worship(self._check_worship_id())
        self.repo.set_entry(old.id, date(2026, 11, 17), value=True)
        payload = self._sample_payload()
        summary = import_payload(self.repo, payload, mode="replace")
        self.assertGreater(summary.deleted["ibadah"], 0)
        self.assertEqual([item.id for item in self.repo.list_worships()], [200])
        # Catatan lama ikut terhapus; hanya catatan hasil impor yang tersisa.
        self.assertEqual(self.repo.list_entries()[0].worship_id, 200)
        self.assertIsNone(self.repo.get_entry(old.id, date(2026, 11, 17)))
        self.assertIsNotNone(self.repo.get_entry(200, date(2026, 11, 18)))
        self.assertEqual(
            self.repo.connection.execute(
                "SELECT nilai FROM meta WHERE kunci = 'schema_version'"
            ).fetchone()["nilai"],
            str(SCHEMA_VERSION),
        )

    def test_invalid_mode_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            import_payload(self.repo, self._sample_payload(), mode="hapus")

    def test_merge_roundtrip_preserves_all_content(self) -> None:
        self.repo.set_entry(
            self._check_worship_id(), date(2026, 11, 18), value=True, time="05:00"
        )
        self.repo.save_muhasabah(date(2026, 11, 18), "Asli")
        original = create_export(self.repo)

        other = Repository(connect(":memory:"))
        self.addCleanup(other.close)
        import_payload(other, original, mode="merge")
        copy = create_export(other)
        self.assertEqual(copy["data"], original["data"])

    # -- cadangan --------------------------------------------------------

    def test_backup_folder_defaults_inside_data_dir(self) -> None:
        self.assertEqual(backup_folder(self.repo).name, "backups")

    def test_backup_folder_can_be_configured(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self.repo.set_setting(SETTING_BACKUP_FOLDER, folder)
            self.assertEqual(backup_folder(self.repo), Path(folder))

    def test_create_backup_writes_file_and_marks_meta(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = create_backup(self.repo, folder)
            self.assertTrue(path.exists())
            self.assertEqual(path.parent, Path(folder))
            self.assertEqual(
                self.repo.get_meta(META_LAST_BACKUP), date.today().isoformat()
            )
            payload = parse_export(path)
            self.assertEqual(payload["format"], EXPORT_FORMAT)

    def test_backup_due_logic(self) -> None:
        today = date(2026, 11, 18)
        self.assertTrue(backup_due(self.repo, today))  # belum pernah
        self.repo.set_meta(META_LAST_BACKUP, today.isoformat())
        self.assertFalse(backup_due(self.repo, today))
        self.assertFalse(backup_due(self.repo, today + timedelta(days=6)))
        self.assertTrue(backup_due(self.repo, today + timedelta(days=7)))

        self.repo.set_meta(META_LAST_BACKUP, "tanggal-rusak")
        self.assertTrue(backup_due(self.repo, today))

    def test_maybe_backup_skips_when_not_due(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            first = maybe_backup(self.repo, folder)
            self.assertIsNotNone(first)
            second = maybe_backup(self.repo, folder)
            self.assertIsNone(second)


if __name__ == "__main__":
    unittest.main()
