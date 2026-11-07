import unittest

from models import Point, Region
from window_message_input import (
    WindowCandidate,
    WindowMessageError,
    choose_window_for_region,
    contains_point,
    make_lparam,
    overlap_area,
    region_center,
    _button_messages,
    _move_points,
)


class WindowMessageInputTests(unittest.TestCase):
    def test_make_lparam_packs_client_coordinates(self):
        self.assertEqual(make_lparam(10, 20), (20 << 16) | 10)

    def test_region_helpers(self):
        region = Region(x=100, y=50, width=80, height=40)
        self.assertEqual(region_center(region), Point(x=140, y=70))
        self.assertTrue(contains_point(region, Point(x=120, y=60)))
        self.assertFalse(contains_point(region, Point(x=200, y=60)))

    def test_overlap_area(self):
        first = Region(x=0, y=0, width=100, height=100)
        second = Region(x=50, y=50, width=100, height=100)
        self.assertEqual(overlap_area(first, second), 2500)

    def test_choose_window_prefers_candidate_containing_center(self):
        calibrated = Region(x=100, y=100, width=200, height=200)
        small = WindowCandidate(hwnd=1, title="small", region=Region(x=120, y=120, width=180, height=180))
        large = WindowCandidate(hwnd=2, title="large", region=Region(x=0, y=0, width=800, height=600))
        chosen = choose_window_for_region(calibrated, [large, small])
        self.assertEqual(chosen.hwnd, 1)

    def test_button_messages_rejects_invalid_button(self):
        with self.assertRaises(WindowMessageError):
            _button_messages("middle")

    def test_move_points_ends_on_target(self):
        point = Point(x=10, y=20)
        moves = _move_points(point)
        self.assertEqual(moves[-1], point)
        self.assertEqual(moves[-2], point)


if __name__ == "__main__":
    unittest.main()
