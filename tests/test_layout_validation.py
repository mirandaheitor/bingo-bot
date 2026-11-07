import unittest

import config
from board_layout import LayoutError, count_completed_lines, format_layout, validate_layout


class LayoutValidationTests(unittest.TestCase):
    def test_default_layouts_are_valid(self):
        validate_layout(config.WINNER_LAYOUT)
        validate_layout(config.LOSER_LAYOUT)

    def test_rejects_wrong_row_count(self):
        with self.assertRaises(LayoutError):
            validate_layout([[1, 2, 3, 4, 5]])

    def test_rejects_wrong_column_count(self):
        layout = [list(row) for row in config.LOSER_LAYOUT]
        layout[0] = [1, 2, 3]
        with self.assertRaises(LayoutError):
            validate_layout(layout)

    def test_rejects_repeated_number(self):
        layout = [list(row) for row in config.LOSER_LAYOUT]
        layout[0][0] = layout[0][1]
        with self.assertRaises(LayoutError):
            validate_layout(layout)

    def test_counts_completed_lines(self):
        self.assertEqual(count_completed_lines(config.LOSER_LAYOUT, {1, 2, 3, 4, 5}), 1)
        self.assertEqual(count_completed_lines(config.WINNER_LAYOUT, {1, 2, 3, 4, 5}), 1)

    def test_format_layout_outputs_five_lines(self):
        self.assertEqual(len(format_layout(config.WINNER_LAYOUT).splitlines()), 5)


if __name__ == "__main__":
    unittest.main()
