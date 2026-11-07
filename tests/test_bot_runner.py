import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import config
from board_builder import BoardBuildAction, BoardBuildCommand, BoardBuilder
from bot_runner import BotRuntime, _setup_delay
from input_controller import InputController
from models import MatchObservation, PlayerCalibration, PlayerObservation, PlayerSide, Point, Region, ResultState, SetupState, TurnState
from setup_number_detector import SetupNumberDetection
from template_matcher import TemplateMatch


def sample_calibration(side: PlayerSide) -> PlayerCalibration:
    x = 100 if side is PlayerSide.LEFT else 500
    return PlayerCalibration(
        side=side,
        name=side.value,
        window_region=Region(x=x, y=100, width=300, height=260),
        grid_region=Region(x=x + 10, y=120, width=100, height=100),
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


def found_number(number: int | None) -> SetupNumberDetection:
    return SetupNumberDetection(
        number=number,
        confidence=1.0 if number is not None else 0.0,
        match=TemplateMatch(name="" if number is None else str(number), found=number is not None, confidence=1.0),
    )


class BotRunnerTests(unittest.TestCase):
    def test_setup_delay_uses_action_specific_values(self):
        self.assertEqual(
            _setup_delay(BoardBuildCommand(BoardBuildAction.PLACE_NUMBER, PlayerSide.LEFT, 1, 1)),
            config.DELAY_AFTER_SETUP_CLICK,
        )
        self.assertEqual(
            _setup_delay(BoardBuildCommand(BoardBuildAction.RETRY_NUMBER, PlayerSide.LEFT, 2, 1)),
            config.DELAY_AFTER_SETUP_CLICK,
        )
        self.assertEqual(
            _setup_delay(BoardBuildCommand(BoardBuildAction.UNDO, PlayerSide.LEFT, 1, 2)),
            config.DELAY_AFTER_UNDO,
        )
        self.assertEqual(
            _setup_delay(BoardBuildCommand(BoardBuildAction.CONFIRM, PlayerSide.LEFT, 26, None)),
            config.DELAY_AFTER_CONFIRM,
        )
        self.assertEqual(
            _setup_delay(BoardBuildCommand(BoardBuildAction.WAIT, PlayerSide.LEFT, 1, None)),
            config.LOOP_INTERVAL,
        )

    def test_setup_both_interleaves_left_and_right(self):
        sequences = {
            PlayerSide.LEFT: iter(list(range(1, 26)) + [None]),
            PlayerSide.RIGHT: iter(list(range(1, 26)) + [None]),
        }

        def detect(calibration, _debug_dir=None):
            return found_number(next(sequences[calibration.side]))

        with (
            patch("bot_runner.load_calibration", side_effect=sample_calibration),
            patch("bot_runner.detect_setup_number_for_player", side_effect=detect),
            patch("bot_runner.detect_setup_state_for_player", return_value=SetupState.READY),
            patch("bot_runner.raise_if_escape_pressed"),
            patch("builtins.print"),
            TemporaryDirectory() as temp_dir,
        ):
            input_controller = InputController(dry_run=True)
            runtime = BotRuntime(
                winner_side=PlayerSide.LEFT,
                dry_run=True,
                input_controller=input_controller,
            )
            runtime._sleep = lambda _seconds: None

            result = runtime.run_setup_both(max_cycles=26, debug_dir=Path(temp_dir))

        self.assertTrue(result.completed)
        number_clicks = [entry for entry in input_controller.action_log if " numero " in entry]
        self.assertIn("click:left numero 1:", number_clicks[0])
        self.assertIn("click:right numero 1:", number_clicks[1])
        self.assertIn("click:left numero 2:", number_clicks[2])
        self.assertIn("click:right numero 2:", number_clicks[3])

    def test_setup_confirm_requires_ready_or_retries_number_25(self):
        with (
            patch("bot_runner.load_calibration", side_effect=sample_calibration),
            patch("bot_runner.detect_setup_state_for_player", return_value=SetupState.UNKNOWN),
        ):
            runtime = BotRuntime(winner_side=PlayerSide.LEFT, dry_run=True)
            builder = BoardBuilder(sample_calibration(PlayerSide.RIGHT), config.LOSER_LAYOUT)
            command = BoardBuildCommand(BoardBuildAction.CONFIRM, PlayerSide.RIGHT, 26, 25)
            retry_counts = {PlayerSide.LEFT: 0, PlayerSide.RIGHT: 0}

            retry = runtime._confirm_or_retry_setup_ready(
                builder=builder,
                calibration=sample_calibration(PlayerSide.RIGHT),
                command=command,
                retry_counts=retry_counts,
                debug_dir=Path("debug"),
            )

        self.assertEqual(retry.action, BoardBuildAction.RETRY_NUMBER)
        self.assertEqual(retry.detected_number, 25)
        self.assertEqual(retry.point, Point(x=600, y=130))
        self.assertEqual(retry_counts[PlayerSide.RIGHT], 1)

    def test_ready_recovery_clicks_confirm_on_unknown_side(self):
        observation = MatchObservation(
            left=PlayerObservation(turn_state=TurnState.UNKNOWN),
            right=PlayerObservation(turn_state=TurnState.WAITING),
        )

        with (
            patch("bot_runner.load_calibration", side_effect=sample_calibration),
            patch("bot_runner.detect_setup_state_for_player", return_value=SetupState.READY),
            patch("bot_runner.raise_if_escape_pressed"),
        ):
            input_controller = InputController(dry_run=True)
            runtime = BotRuntime(
                winner_side=PlayerSide.LEFT,
                dry_run=True,
                input_controller=input_controller,
            )
            runtime._sleep = lambda _seconds: None

            recovered = runtime._recover_ready_if_needed(observation)

        self.assertTrue(recovered)
        self.assertEqual(input_controller.action_log[0], "focus:left:250,112:activate_window")
        self.assertEqual(input_controller.action_log[1], "focus:left:250,112:activate_window")
        self.assertIn("click:left Confirm recuperacao:", input_controller.action_log[2])

    def test_ready_recovery_does_not_click_confirm_without_ready_state(self):
        observation = MatchObservation(
            left=PlayerObservation(turn_state=TurnState.UNKNOWN),
            right=PlayerObservation(turn_state=TurnState.WAITING),
        )

        with (
            patch("bot_runner.load_calibration", side_effect=sample_calibration),
            patch("bot_runner.detect_setup_state_for_player", return_value=SetupState.UNKNOWN),
            patch("bot_runner.raise_if_escape_pressed"),
        ):
            input_controller = InputController(dry_run=True)
            runtime = BotRuntime(
                winner_side=PlayerSide.LEFT,
                dry_run=True,
                input_controller=input_controller,
            )
            runtime._sleep = lambda _seconds: None

            recovered = runtime._recover_ready_if_needed(observation)

        self.assertFalse(recovered)
        self.assertEqual(input_controller.action_log, ["focus:left:250,112:activate_window"])

    def test_continue_retries_side_that_still_has_result(self):
        right_results = iter([ResultState.LOSE, ResultState.NONE])

        def detect_result(calibration, _debug_dir=None):
            if calibration.side is PlayerSide.LEFT:
                return ResultState.NONE
            return next(right_results)

        with (
            patch("bot_runner.load_calibration", side_effect=sample_calibration),
            patch("bot_runner.detect_result_for_player", side_effect=detect_result),
            patch("bot_runner.raise_if_escape_pressed"),
            patch("builtins.print"),
        ):
            input_controller = InputController(dry_run=True)
            runtime = BotRuntime(
                winner_side=PlayerSide.LEFT,
                dry_run=True,
                input_controller=input_controller,
            )
            runtime._sleep = lambda _seconds: None

            closed = runtime._click_continue_both(Path("debug"))

        self.assertTrue(closed)
        continue_clicks = [entry for entry in input_controller.action_log if "Continue" in entry]
        self.assertEqual(len(continue_clicks), 3)
        self.assertIn("click:left Continue:", continue_clicks[0])
        self.assertIn("click:right Continue:", continue_clicks[1])
        self.assertIn("click:right Continue:", continue_clicks[2])


if __name__ == "__main__":
    unittest.main()
