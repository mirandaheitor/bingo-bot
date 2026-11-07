import unittest

import config
from board_layout import cell_center, layout_for_side, number_to_cell, number_to_cell_map
from models import Cell, PlayerSide, Point, Region


class NumberMappingTests(unittest.TestCase):
    def test_number_to_cell_uses_zero_based_row_col(self):
        self.assertEqual(number_to_cell(config.WINNER_LAYOUT, 1), Cell(row=4, col=0))
        self.assertEqual(number_to_cell(config.WINNER_LAYOUT, 13), Cell(row=2, col=2))
        self.assertEqual(number_to_cell(config.LOSER_LAYOUT, 25), Cell(row=0, col=4))

    def test_number_to_cell_map_has_25_entries(self):
        mapping = number_to_cell_map(config.WINNER_LAYOUT)
        self.assertEqual(len(mapping), 25)
        self.assertEqual(mapping[25], Cell(row=4, col=4))

    def test_cell_center_from_grid_region(self):
        grid = Region(x=10, y=20, width=100, height=100)
        self.assertEqual(cell_center(grid, Cell(row=0, col=0)), Point(x=20, y=30))
        self.assertEqual(cell_center(grid, Cell(row=4, col=4)), Point(x=100, y=110))

    def test_layout_for_side_inverts_by_winner_side(self):
        left = layout_for_side(PlayerSide.LEFT, PlayerSide.RIGHT, config.WINNER_LAYOUT, config.LOSER_LAYOUT)
        right = layout_for_side(PlayerSide.RIGHT, PlayerSide.RIGHT, config.WINNER_LAYOUT, config.LOSER_LAYOUT)
        self.assertEqual(left, config.LOSER_LAYOUT)
        self.assertEqual(right, config.WINNER_LAYOUT)


if __name__ == "__main__":
    unittest.main()
