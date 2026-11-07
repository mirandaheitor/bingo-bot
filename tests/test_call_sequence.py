import unittest

import config
from battle_controller import BattleController, BattleError
from models import Cell, TurnState


class CallSequenceTests(unittest.TestCase):
    def test_consumes_sequence_only_on_my_turn(self):
        controller = BattleController(layout=config.WINNER_LAYOUT, call_sequence=[1, 2])
        self.assertIsNone(controller.next_action(TurnState.WAITING))
        first = controller.next_action(TurnState.MY_TURN)
        self.assertIsNotNone(first)
        self.assertEqual(first.number, 1)
        self.assertEqual(first.cell, Cell(row=4, col=0))
        self.assertEqual(controller.call_index, 1)

    def test_raises_when_sequence_is_exhausted(self):
        controller = BattleController(layout=config.WINNER_LAYOUT, call_sequence=[1])
        controller.next_action(TurnState.MY_TURN)
        with self.assertRaises(BattleError):
            controller.next_action(TurnState.MY_TURN)

    def test_rejects_invalid_call_sequence_number(self):
        with self.assertRaises(BattleError):
            BattleController(layout=config.WINNER_LAYOUT, call_sequence=[0, 1])


if __name__ == "__main__":
    unittest.main()
