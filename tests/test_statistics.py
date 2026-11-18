"""Pengujian logika statistik tanpa jendela GTK."""

from __future__ import annotations

import unittest
from datetime import date

from src.logic.statistics import (
    DayState,
    Entry,
    EntryKind,
    StatusValue,
    Worship,
    classify_day,
    compute_daily,
    compute_range,
    compute_yearly_series,
    describe_completion,
    is_active,
    is_completed,
)

DAY = date(2026, 11, 18)


def check_worship(
    worship_id: int = 1,
    name: str = "Subuh",
    **kwargs: object,
) -> Worship:
    return Worship(
        id=worship_id,
        name=name,
        kind=EntryKind.CHECK,
        **kwargs,  # type: ignore[arg-type]
    )


class CompletionRulesTests(unittest.TestCase):
    def test_check_true_and_false(self) -> None:
        worship = check_worship()
        self.assertTrue(is_completed(worship, Entry(1, DAY, True)))
        self.assertFalse(is_completed(worship, Entry(1, DAY, False)))
        self.assertFalse(is_completed(worship, Entry(1, DAY, None)))

    def test_number_uses_target(self) -> None:
        worship = Worship(2, "Tilawah", EntryKind.NUMBER, target=5)
        self.assertFalse(is_completed(worship, Entry(2, DAY, 3)))
        self.assertTrue(is_completed(worship, Entry(2, DAY, 5)))
        self.assertTrue(is_completed(worship, Entry(2, DAY, 6)))

    def test_number_without_target(self) -> None:
        worship = Worship(2, "Hafalan", EntryKind.NUMBER)
        self.assertFalse(is_completed(worship, Entry(2, DAY, 0)))
        self.assertTrue(is_completed(worship, Entry(2, DAY, 1)))

    def test_status_except_belum_counts(self) -> None:
        worship = Worship(3, "Subuh", EntryKind.STATUS)
        self.assertFalse(is_completed(worship, Entry(3, DAY, StatusValue.BELUM)))
        self.assertTrue(is_completed(worship, Entry(3, DAY, StatusValue.QADHA)))
        self.assertTrue(is_completed(worship, Entry(3, DAY, "berjamaah")))


class ActiveDayTests(unittest.TestCase):
    def test_active_from_excludes_earlier_days(self) -> None:
        worship = check_worship(active_from=date(2026, 3, 1))
        self.assertFalse(is_active(worship, date(2026, 2, 28)))
        self.assertTrue(is_active(worship, date(2026, 3, 1)))

    def test_archived_day_is_excluded(self) -> None:
        worship = check_worship(archived_on=date(2026, 6, 1))
        self.assertTrue(is_active(worship, date(2026, 5, 31)))
        self.assertFalse(is_active(worship, date(2026, 6, 1)))

    def test_weekday_filter(self) -> None:
        # 18 November 2026 adalah Rabu (weekday 2).
        worship = check_worship(active_weekdays=frozenset({0, 3}))
        self.assertFalse(is_active(worship, DAY))


class DailyTests(unittest.TestCase):
    def test_states(self) -> None:
        worships = (check_worship(1), check_worship(2, name="Dzuhur"))

        empty = compute_daily(DAY, worships, [])
        self.assertEqual(empty.state, DayState.EMPTY)
        self.assertEqual(empty.expected, 2)

        partial = compute_daily(DAY, worships, [Entry(1, DAY, True)])
        self.assertEqual(partial.state, DayState.PARTIAL)
        self.assertEqual(partial.completed, 1)

        full = compute_daily(
            DAY, worships, [Entry(1, DAY, True), Entry(2, DAY, False)]
        )
        self.assertEqual(full.state, DayState.PARTIAL)  # False sengaja dicatat.

        full = compute_daily(
            DAY, worships, [Entry(1, DAY, True), Entry(2, DAY, True)]
        )
        self.assertEqual(full.state, DayState.FULL)

        self.assertEqual(classify_day(DAY, worships, []), DayState.EMPTY)

    def test_day_without_active_worship_is_empty(self) -> None:
        worship = check_worship(active_weekdays=frozenset({0}))
        summary = compute_daily(DAY, (worship,), [Entry(1, DAY, True)])
        self.assertEqual(summary.state, DayState.EMPTY)
        self.assertEqual(summary.expected, 0)


class RangeTests(unittest.TestCase):
    def test_leap_february_has_29_days(self) -> None:
        summary = compute_range(
            date(2028, 2, 1), date(2028, 2, 29), (check_worship(),), []
        )[0]
        self.assertEqual(summary.expected_days, 29)
        self.assertEqual(summary.key, "2028-02")

    def test_monthly_summary_uses_full_days(self) -> None:
        worship = check_worship()
        entries = [Entry(1, date(2026, 11, day), True) for day in (17, 18, 19)]
        summary = compute_range(
            date(2026, 11, 1), date(2026, 11, 30), (worship,), entries
        )[0]
        self.assertEqual(summary.completed_days, 3)
        self.assertEqual(summary.expected_days, 30)
        self.assertEqual(summary.state, DayState.PARTIAL)
        self.assertEqual(summary.per_worship[0].name, "Subuh")

    def test_new_worship_does_not_count_older_months(self) -> None:
        worship = check_worship(active_from=date(2026, 11, 15))
        months = compute_range(
            date(2026, 1, 1),
            date(2026, 11, 30),
            (worship,),
            [],
            granularity="month",
        )
        january, november = months[0], months[10]
        self.assertEqual(january.expected_days, 0)
        self.assertEqual(january.state, DayState.EMPTY)
        self.assertEqual(november.expected_days, 16)

    def test_yearly_series_has_twelve_points_and_gaps(self) -> None:
        worship = check_worship(
            active_from=date(2026, 11, 15),
            archived_on=date(2026, 12, 1),
        )
        points = compute_yearly_series(2026, (worship,), [])
        self.assertEqual(len(points), 12)
        self.assertFalse(points[0].has_data)
        self.assertTrue(points[10].has_data)
        self.assertEqual(points[10].month, 11)
        self.assertFalse(points[11].has_data)


class LabelTests(unittest.TestCase):
    def test_neutral_wording(self) -> None:
        self.assertEqual(describe_completion(18, 30), "Terlaksana 18 dari 30 hari")
        self.assertEqual(
            describe_completion(0, 0), "Tidak ada ibadah aktif pada rentang ini"
        )


if __name__ == "__main__":
    unittest.main()
