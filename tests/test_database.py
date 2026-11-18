"""Pengujian skema, migrasi, dan data awal SQLite."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.logic.constants import APP_ID, SCHEMA_VERSION
from src.logic.database import connect, default_database_path, default_data_dir, initialize
from src.logic.defaults import DEFAULT_CATEGORIES, DEFAULT_WORSHIPS

TABLES = (
    "meta",
    "kategori",
    "ibadah",
    "catatan",
    "muhasabah",
    "catatan_harian",
    "pengaturan",
)


class DatabaseTests(unittest.TestCase):
    def test_memory_database_has_all_tables_and_version(self) -> None:
        connection = connect(":memory:")
        self.addCleanup(connection.close)
        names = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        self.assertTrue(set(TABLES).issubset(names))
        self.assertEqual(
            connection.execute(
                "SELECT nilai FROM meta WHERE kunci = 'schema_version'"
            ).fetchone()["nilai"],
            str(SCHEMA_VERSION),
        )

    def test_default_paths_follow_app_id(self) -> None:
        self.assertEqual(default_data_dir().name, APP_ID)
        self.assertEqual(default_database_path().parent, default_data_dir())

    def test_default_worships_are_seeded_once_with_today_as_start(self) -> None:
        connection = connect(":memory:")
        self.addCleanup(connection.close)

        categories = connection.execute("SELECT * FROM kategori").fetchall()
        worships = connection.execute("SELECT * FROM ibadah").fetchall()
        self.assertEqual(len(categories), len(DEFAULT_CATEGORIES))
        self.assertEqual(len(worships), len(DEFAULT_WORSHIPS))
        self.assertTrue(all(row["aktif_mulai"] == date.today().isoformat() for row in worships))
        self.assertEqual(
            connection.execute(
                "SELECT nilai FROM meta WHERE kunci = 'defaults_seeded'"
            ).fetchone()["nilai"],
            "1",
        )

        initialize(connection)
        self.assertEqual(connection.execute("SELECT COUNT(*) AS n FROM ibadah").fetchone()["n"], len(DEFAULT_WORSHIPS))

    def test_initialize_without_seed_leaves_tables_empty(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        self.addCleanup(connection.close)
        initialize(connection, seed=False)
        self.assertEqual(connection.execute("SELECT COUNT(*) AS n FROM kategori").fetchone()["n"], 0)
        self.assertEqual(connection.execute("SELECT COUNT(*) AS n FROM ibadah").fetchone()["n"], 0)

    def test_newer_schema_version_is_rejected(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        self.addCleanup(connection.close)
        connection.execute("CREATE TABLE meta (kunci TEXT PRIMARY KEY, nilai TEXT NOT NULL)")
        connection.execute(
            "INSERT INTO meta (kunci, nilai) VALUES ('schema_version', '99')"
        )
        connection.commit()
        with self.assertRaises(RuntimeError):
            initialize(connection, seed=False)

    def test_migration_from_schema_v1_creates_daily_notes(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        self.addCleanup(connection.close)
        connection.execute("CREATE TABLE meta (kunci TEXT PRIMARY KEY, nilai TEXT NOT NULL)")
        connection.execute(
            "INSERT INTO meta (kunci, nilai) VALUES ('schema_version', '1')"
        )
        connection.execute("CREATE TABLE warisan (nilai TEXT)")
        connection.execute("INSERT INTO warisan (nilai) VALUES ('tetap ada')")
        connection.commit()

        initialize(connection, seed=False)

        names = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        self.assertIn("catatan_harian", names)
        self.assertEqual(
            connection.execute(
                "SELECT nilai FROM meta WHERE kunci = 'schema_version'"
            ).fetchone()["nilai"],
            str(SCHEMA_VERSION),
        )
        self.assertEqual(
            connection.execute("SELECT nilai FROM warisan").fetchone()["nilai"],
            "tetap ada",
        )

    def test_database_file_is_created_in_requested_directory(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "nested" / "data.sqlite3"
            connection = connect(path)
            self.addCleanup(connection.close)
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
