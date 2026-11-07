import unittest

import config
from battle_runtime import BattleDryRunAction, BattleDryRunRuntime
from models import MatchObservation, PlayerCalibration, PlayerObservation, PlayerSide, Point, Region, ResultState, TurnState


def sample_calibration(side: PlayerSide, x: int = 0) -> PlayerCalibration:
    return PlayerCalibration(
        side=side,
        name=side.value,
        window_region=Region(x=x, y=0, width=300, height=260),
        grid_region=Region(x=x + 10, y=20, width=100, height=100),
        setup_number_region=Region(x=x + 200, y=20, width=40, height=40),
        setup_text_region=Region(x=x, y=220, width=200, height=20),
        turn_region=Region(x=x, y=230, width=200, height=20),
        result_region=Region(x=x + 20, y=40, width=180, height=140),
        ready_button=Point(x=x + 250, y=220),
        undo_button=Point(x=x + 210, y=180),
        clear_button=Point(x=x + 230, y=180),
        confirm_button=Point(x=x + 250, y=180),
        continue_button=Point(x=x + 250, y=180),
    )


def obs(
    left_turn=TurnState.UNKNOWN,
    right_turn=TurnState.UNKNOWN,
    left_result=ResultState.NONE,
    right_result=ResultState.NONE,
) -> MatchObservation:
    return MatchObservation(
        left=PlayerObservation(turn_state=left_turn, result_state=left_result),
        right=PlayerObservation(turn_state=right_turn, result_state=right_result),
    )


class BattleRuntimeTests(unittest.TestCase):
    def runtime(self, winner_side=PlayerSide.LEFT, call_sequence=None) -> BattleDryRunRuntime:
        return BattleDryRunRuntime(
            winner_side=winner_side,
            left_calibration=sample_calibration(PlayerSide.LEFT, x=0),
            right_calibration=sample_calibration(PlayerSide.RIGHT, x=400),
            call_sequence=list(call_sequence if call_sequence is not None else [1, 2]),
        )

    def test_unique_turn_plans_number_click_and_consumes_sequence(self):
        runtime = self.runtime()
        command = runtime.step(obs(left_turn=TurnState.MY_TURN, right_turn=TurnState.WAITING))
        self.assertEqual(command.action, BattleDryRunAction.CALL_NUMBER)
        self.assertEqual(command.side, PlayerSide.LEFT)
        self.assertEqual(command.number, 1)
        self.assertEqual(command.point, Point(x=20, y=110))
        self.assertEqual(runtime.call_index, 1)

    def test_same_turn_does_not_consume_twice_without_screen_change(self):
        runtime = self.runtime()
        runtime.step(obs(left_turn=TurnState.MY_TURN, right_turn=TurnState.WAITING))
        second = runtime.step(obs(left_turn=TurnState.MY_TURN, right_turn=TurnState.WAITING))
        self.assertEqual(second.action, BattleDryRunAction.WAIT)
        self.assertEqual(runtime.call_index, 1)

    def test_same_turn_persistent_retries_last_call_without_consuming_sequence(self):
        runtime = self.runtime(call_sequence=[1, 2])
        first = runtime.step(obs(left_turn=TurnState.MY_TURN, right_turn=TurnState.WAITING))
        retry = None
        for _index in range(config.MAX_STALE_TURN_WAITS):
            retry = runtime.step(obs(left_turn=TurnState.MY_TURN, right_turn=TurnState.WAITING))

        self.assertEqual(first.action, BattleDryRunAction.CALL_NUMBER)
        self.assertEqual(retry.action, BattleDryRunAction.RETRY_CALL_NUMBER)
        self.assertEqual(retry.number, 1)
        self.assertEqual(retry.point, first.point)
        self.assertEqual(runtime.call_index, 1)

    def test_result_plans_continue_both(self):
        runtime = self.runtime()
        command = runtime.step(obs(left_result=ResultState.WIN, right_result=ResultState.LOSE))
        self.assertEqual(command.action, BattleDryRunAction.CONTINUE_BOTH)
        self.assertIsNone(command.side)

    def test_unknown_or_conflicting_turn_waits(self):
        runtime = self.runtime()
        unknown = runtime.step(obs())
        self.assertEqual(unknown.action, BattleDryRunAction.WAIT)
        both = runtime.step(obs(left_turn=TurnState.MY_TURN, right_turn=TurnState.MY_TURN))
        self.assertEqual(both.action, BattleDryRunAction.WAIT)

    def test_loser_layout_is_used_when_winner_is_right(self):
        runtime = self.runtime(winner_side=PlayerSide.RIGHT, call_sequence=[25])
        command = runtime.step(obs(left_turn=TurnState.MY_TURN, right_turn=TurnState.WAITING))
        self.assertEqual(command.number, 25)
        self.assertEqual(command.point, Point(x=100, y=30))

    def test_sequence_exhaustion_blocks(self):
        runtime = self.runtime(call_sequence=[])
        command = runtime.step(obs(left_turn=TurnState.MY_TURN, right_turn=TurnState.WAITING))
        self.assertEqual(command.action, BattleDryRunAction.BLOCKED)


if __name__ == "__main__":
    unittest.main()
