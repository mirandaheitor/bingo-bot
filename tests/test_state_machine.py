import unittest

from game_controller import GameController, empty_observation
from models import BotState, MatchObservation, PlayerObservation, PlayerSide, ResultState, TurnState


def obs(left_turn=TurnState.UNKNOWN, right_turn=TurnState.UNKNOWN, left_result=ResultState.NONE, right_result=ResultState.NONE):
    return MatchObservation(
        left=PlayerObservation(turn_state=left_turn, result_state=left_result),
        right=PlayerObservation(turn_state=right_turn, result_state=right_result),
    )


class StateMachineTests(unittest.TestCase):
    def test_setup_flow_reaches_wait_first_turn(self):
        controller = GameController(winner_side=PlayerSide.LEFT)
        self.assertEqual(controller.start().action, "setup_left")
        self.assertEqual(controller.step(empty_observation()).action, "setup_right")
        self.assertEqual(controller.step(empty_observation()).action, "confirm_left")
        self.assertEqual(controller.step(empty_observation()).action, "confirm_right")
        wait = controller.step(empty_observation())
        self.assertIsNone(wait.action)
        self.assertEqual(wait.state_after, BotState.WAIT_FIRST_TURN)

    def test_first_known_turn_calls_next_number(self):
        controller = GameController(winner_side=PlayerSide.LEFT, call_sequence=[1])
        controller.start()
        for _ in range(4):
            controller.step(empty_observation())
        result = controller.step(obs(left_turn=TurnState.MY_TURN, right_turn=TurnState.WAITING))
        self.assertEqual(result.action, "call_left_1")
        self.assertEqual(result.state_after, BotState.BATTLE)

    def test_unknown_turn_does_not_click(self):
        controller = GameController(winner_side=PlayerSide.LEFT, call_sequence=[1])
        controller.start()
        for _ in range(4):
            controller.step(empty_observation())
        result = controller.step(empty_observation())
        self.assertIsNone(result.action)
        self.assertEqual(controller.call_index, 0)

    def test_result_stops_battle_and_continues_both(self):
        controller = GameController(winner_side=PlayerSide.LEFT, call_sequence=[1, 2])
        controller.start()
        for _ in range(4):
            controller.step(empty_observation())
        result = controller.step(obs(left_result=ResultState.WIN, right_result=ResultState.LOSE))
        self.assertEqual(result.action, "continue_both")
        self.assertEqual(result.state_after, BotState.CONTINUE_BOTH)

    def test_draw_counts_as_result(self):
        controller = GameController(winner_side=PlayerSide.LEFT)
        controller.start()
        result = controller.step(obs(left_result=ResultState.DRAW, right_result=ResultState.DRAW))
        self.assertEqual(result.action, "continue_both")
        self.assertEqual(result.state_after, BotState.CONTINUE_BOTH)

    def test_sequence_exhaustion_enters_error(self):
        controller = GameController(winner_side=PlayerSide.LEFT, call_sequence=[])
        controller.start()
        for _ in range(4):
            controller.step(empty_observation())
        result = controller.step(obs(left_turn=TurnState.MY_TURN, right_turn=TurnState.WAITING))
        self.assertIsNone(result.action)
        self.assertEqual(result.state_after, BotState.ERROR)


if __name__ == "__main__":
    unittest.main()
