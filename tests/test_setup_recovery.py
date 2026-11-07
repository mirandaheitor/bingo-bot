import unittest

import config
from models import Cell
from setup_controller import SetupAction, SetupController


class SetupRecoveryTests(unittest.TestCase):
    def test_places_expected_number_in_configured_cell(self):
        controller = SetupController(layout=config.WINNER_LAYOUT)
        step = controller.step(1)
        self.assertEqual(step.action, SetupAction.PLACE_NUMBER)
        self.assertEqual(step.cell, Cell(row=4, col=0))
        self.assertEqual(controller.expected_number, 2)

    def test_unknown_number_does_not_click(self):
        controller = SetupController(layout=config.WINNER_LAYOUT)
        step = controller.step(None)
        self.assertEqual(step.action, SetupAction.WAIT)
        self.assertEqual(controller.expected_number, 1)

    def test_skipped_number_requests_undo_and_restart(self):
        controller = SetupController(layout=config.WINNER_LAYOUT)
        controller.step(1)
        step = controller.step(3)
        self.assertEqual(step.action, SetupAction.UNDO_AND_RESTART)
        self.assertEqual(controller.expected_number, 1)
        self.assertEqual(controller.retries, 1)

    def test_previous_number_waits_then_retries_without_undo(self):
        controller = SetupController(layout=config.WINNER_LAYOUT, max_stale_waits=1)
        controller.step(1)
        wait = controller.step(1)
        retry = controller.step(1)
        self.assertEqual(wait.action, SetupAction.WAIT)
        self.assertEqual(retry.action, SetupAction.RETRY_NUMBER)
        self.assertEqual(retry.cell, Cell(row=4, col=0))
        self.assertEqual(controller.expected_number, 2)
        self.assertEqual(controller.retries, 0)

    def test_blocks_after_max_setup_retries(self):
        controller = SetupController(layout=config.WINNER_LAYOUT, max_retries=2)
        self.assertEqual(controller.step(2).action, SetupAction.UNDO_AND_RESTART)
        self.assertEqual(controller.step(2).action, SetupAction.BLOCKED)

    def test_confirms_after_25_numbers(self):
        controller = SetupController(layout=config.LOSER_LAYOUT)
        for number in range(1, 26):
            controller.step(number)
        step = controller.step(None)
        self.assertEqual(step.action, SetupAction.CONFIRM)


if __name__ == "__main__":
    unittest.main()
