"""Ibadah dan kategori bawaan untuk pengguna baru.

Data di sini hanya dipakai sekali saat basis data dibuat. Ibadah bawaan
memakai ``aktif_mulai`` = hari dibuat supaya riwayat lama tidak dianggap
seharusnya sudah terisi (lihat prinsip "hari ini dulu" di README).
"""

from __future__ import annotations

from typing import NamedTuple

from .statistics import EntryKind

__all__ = [
    "DEFAULT_CATEGORIES",
    "DEFAULT_WORSHIPS",
    "HABIT_CATEGORY",
    "DefaultWorship",
]


class DefaultWorship(NamedTuple):
    name: str
    category: str
    kind: EntryKind
    target: float | None = None
    unit: str = ""
    weekdays: tuple[int, ...] = tuple(range(7))


DEFAULT_CATEGORIES: tuple[str, ...] = (
    "Sholat fardhu",
    "Sholat sunnah",
    "Al-Qur'an",
    "Dzikir",
    "Puasa sunnah",
    "Amal",
    "Kebiasaan",
    "Pribadi",
)

HABIT_CATEGORY = "Kebiasaan"

# 0 = Senin ... 6 = Minggu, mengikuti numbering Python.
SENIN_KAMIS = (0, 3)

DEFAULT_WORSHIPS: tuple[DefaultWorship, ...] = (
    DefaultWorship("Subuh", "Sholat fardhu", EntryKind.STATUS),
    DefaultWorship("Dzuhur", "Sholat fardhu", EntryKind.STATUS),
    DefaultWorship("Ashar", "Sholat fardhu", EntryKind.STATUS),
    DefaultWorship("Maghrib", "Sholat fardhu", EntryKind.STATUS),
    DefaultWorship("Isya", "Sholat fardhu", EntryKind.STATUS),
    DefaultWorship("Rawatib", "Sholat sunnah", EntryKind.STATUS),
    DefaultWorship("Dhuha", "Sholat sunnah", EntryKind.STATUS),
    DefaultWorship("Tahajud", "Sholat sunnah", EntryKind.STATUS),
    DefaultWorship("Witir", "Sholat sunnah", EntryKind.STATUS),
    DefaultWorship("Tilawah", "Al-Qur'an", EntryKind.NUMBER, 1, "halaman"),
    DefaultWorship("Hafalan", "Al-Qur'an", EntryKind.NUMBER, 1, "ayat"),
    DefaultWorship("Muraja'ah", "Al-Qur'an", EntryKind.NUMBER, 1, "halaman"),
    DefaultWorship("Dzikir pagi", "Dzikir", EntryKind.CHECK),
    DefaultWorship("Dzikir petang", "Dzikir", EntryKind.CHECK),
    DefaultWorship("Dzikir setelah sholat", "Dzikir", EntryKind.CHECK),
    DefaultWorship("Puasa Senin-Kamis", "Puasa sunnah", EntryKind.CHECK, weekdays=SENIN_KAMIS),
    DefaultWorship("Sedekah", "Amal", EntryKind.CHECK),
    DefaultWorship("Silaturahmi", "Amal", EntryKind.CHECK),
    # Kebiasaan umum memakai sistem yang sama dengan ibadah, sehingga masuk
    # statistik harian, bulanan, dan tahunan tanpa jalur data terpisah.
    DefaultWorship("Belajar", HABIT_CATEGORY, EntryKind.NUMBER, 30, "menit"),
    DefaultWorship("Baca buku", HABIT_CATEGORY, EntryKind.NUMBER, 10, "halaman"),
    DefaultWorship("Olahraga", HABIT_CATEGORY, EntryKind.CHECK),
    DefaultWorship("Jalan kaki", HABIT_CATEGORY, EntryKind.NUMBER, 20, "menit"),
    DefaultWorship("Tidur awal", HABIT_CATEGORY, EntryKind.CHECK),
)
