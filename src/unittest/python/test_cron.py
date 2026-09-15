import unittest
from datetime import datetime

from ycappuccino.scheduler.cron import next_fire_time


class TestNextFireTime(unittest.TestCase):

    def test_every_minute(self):
        after = datetime(2026, 1, 1, 10, 30, 15)

        self.assertEqual(next_fire_time("* * * * *", after), datetime(2026, 1, 1, 10, 31))

    def test_exact_minute_and_hour(self):
        after = datetime(2026, 1, 1, 10, 0)

        self.assertEqual(next_fire_time("0 3 * * *", after), datetime(2026, 1, 2, 3, 0))

    def test_after_the_hour_moves_to_next_day(self):
        after = datetime(2026, 1, 1, 4, 0)

        self.assertEqual(next_fire_time("0 3 * * *", after), datetime(2026, 1, 2, 3, 0))

    def test_list_of_minutes(self):
        after = datetime(2026, 1, 1, 10, 0)

        self.assertEqual(next_fire_time("0,15,30,45 * * * *", after), datetime(2026, 1, 1, 10, 15))

    def test_range(self):
        after = datetime(2026, 1, 1, 9, 30)

        self.assertEqual(next_fire_time("0 9-17 * * *", after), datetime(2026, 1, 1, 10, 0))

    def test_range_excludes_outside_hours(self):
        after = datetime(2026, 1, 1, 18, 0)

        self.assertEqual(next_fire_time("0 9-17 * * *", after), datetime(2026, 1, 2, 9, 0))

    def test_step(self):
        after = datetime(2026, 1, 1, 10, 1)

        self.assertEqual(next_fire_time("*/15 * * * *", after), datetime(2026, 1, 1, 10, 15))

    def test_range_with_step(self):
        after = datetime(2026, 1, 1, 0, 0)

        self.assertEqual(next_fire_time("0 8-20/4 * * *", after), datetime(2026, 1, 1, 8, 0))

    def test_month_rollover(self):
        after = datetime(2026, 1, 31, 23, 59)

        self.assertEqual(next_fire_time("0 0 1 * *", after), datetime(2026, 2, 1, 0, 0))

    def test_year_rollover(self):
        after = datetime(2026, 12, 31, 23, 59)

        self.assertEqual(next_fire_time("0 0 1 1 *", after), datetime(2027, 1, 1, 0, 0))

    def test_specific_month(self):
        after = datetime(2026, 1, 1, 0, 0)

        self.assertEqual(next_fire_time("0 0 1 6 *", after), datetime(2026, 6, 1, 0, 0))

    def test_weekday_sunday_is_zero(self):
        # 2026-01-04 is a Sunday
        after = datetime(2026, 1, 1, 0, 0)

        self.assertEqual(next_fire_time("0 0 * * 0", after), datetime(2026, 1, 4, 0, 0))

    def test_day_of_month_and_weekday_are_combined_with_and(self):
        # documented simplification: both restricted fields must match (not POSIX cron's OR).
        # 2026-01-01 is a Thursday (cron weekday 4).
        after = datetime(2026, 1, 1, 0, 1)

        result = next_fire_time("0 0 1 * 4", after)

        self.assertEqual(result.day, 1)
        self.assertEqual(result.isoweekday() % 7, 4)

    def test_no_solution_raises(self):
        with self.assertRaises(ValueError):
            next_fire_time("0 0 31 2 *", datetime(2026, 1, 1))


if __name__ == "__main__":
    unittest.main()
