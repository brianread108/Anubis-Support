"""Unit tests for app.history.period_delta.

Run with: python3 -m unittest tests.test_history -v
(from the anubis-monitor/ directory)
"""

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.history import period_delta


def rows_from(values, field="decisions"):
    return [{field: value} for value in values]


class PeriodDeltaTests(unittest.TestCase):
    def test_no_rows(self):
        self.assertEqual(period_delta([], "decisions"), 0)

    def test_single_row(self):
        self.assertEqual(period_delta(rows_from([100]), "decisions"), 0)

    def test_steady_increase_matches_simple_subtraction(self):
        # No restart in the window: behaviour should match the old
        # last - first calculation.
        rows = rows_from([100, 150, 200])
        self.assertEqual(period_delta(rows, "decisions"), 100)

    def test_single_restart_mid_window_is_not_lost(self):
        # Counter climbs 100 -> 150 -> 200, Anubis restarts, then climbs
        # 5 -> 20 -> 40. The true total activity in the window is
        # (200 - 100) + 40 = 140, not last - first (40 - 100 => old code
        # would have returned 40, silently dropping the pre-restart 100).
        rows = rows_from([100, 150, 200, 5, 20, 40])
        self.assertEqual(period_delta(rows, "decisions"), 140)

    def test_restart_as_very_first_step(self):
        # Restart happens between the first two samples.
        rows = rows_from([200, 5])
        self.assertEqual(period_delta(rows, "decisions"), 5)

    def test_multiple_restarts_in_window(self):
        # Two restarts. Each cycle's contribution is its own last value,
        # since a post-reset counter is assumed to start fresh from zero:
        # cycle 1 (100 -> 200) contributes 200 - 100 = 100.
        # cycle 2 (reset, 10 -> 60) contributes 60 (10 counted in full as
        #   the first post-reset sample, then + (60 - 10) = 60 total).
        # cycle 3 (reset, 3 -> 13) contributes 13 for the same reason.
        # Total = 100 + 60 + 13 = 173.
        rows = rows_from([100, 200, 10, 60, 3, 13])
        self.assertEqual(period_delta(rows, "decisions"), 173)

    def test_missing_field_treated_as_zero(self):
        rows = [{"decisions": 100}, {}, {"decisions": 150}]
        # previous=100 -> current=0 (missing) => reset, +0
        # previous=0 -> current=150 => +150
        self.assertEqual(period_delta(rows, "decisions"), 150)


if __name__ == "__main__":
    unittest.main()
