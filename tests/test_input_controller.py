import unittest
from unittest.mock import patch

from battle_runtime import BattleDryRunAction, BattleDryRunCommand
from board_builder import BoardBuildAction, BoardBuildCommand
from input_controller import InputController, RealClickDisabledError
from models import PlayerCalibration, PlayerSide, Point, Region


def sample_calibration() -> PlayerCalibration:
    return PlayerCalibration(
        side=PlayerSide.LEFT,
        name="teste",
        window_region=Region(x=100, y=100, width=300, height=260),
        grid_region=Region(x=110, y=120, width=100, height=100),
        setup_number_region=Region(x=200, y=20, width=40, height=40),
        setup_text_region=Region(x=0, y=220, width=200, height=20),
        turn_region=Region(x=0, y=230, width=200, height=20),
        result_region=Region(x=20, y=40, width=180, height=140),
        ready_button=Point(x=250, y=220),
        undo_button=Point(x=210, y=180),
        clear_button=Point(x=230, y=180),
        confirm_button=Point(x=250, y=180),
        continue_button=Point(x=250, y=180),
    )


class InputControllerTests(unittest.TestCase):
    def test_dry_run_click_only_records_action(self):
        controller = InputController(dry_run=True, real_clicks_enabled=False)
        controller.click_point(Point(10, 20), "teste")
        self.assertEqual(controller.action_log, ["click:teste:10,20:left"])

    def test_real_click_requires_explicit_enable(self):
        controller = InputController(dry_run=False, real_clicks_enabled=False)
        with self.assertRaises(RealClickDisabledError):
            controller.click_point(Point(10, 20), "bloqueado")

    def test_window_message_backend_sends_configured_method(self):
        controller = InputController(dry_run=False, real_clicks_enabled=True, backend="window_message")
        with patch("input_controller.message_click_at_point") as click_mock:
            controller.click_point(Point(10, 20), "mensagem")

        click_mock.assert_called_once_with(Point(10, 20), button="left", method="send_hover_child")

    def test_activate_window_focus_backend_does_not_click_mouse(self):
        calibration = sample_calibration()
        controller = InputController(dry_run=False, real_clicks_enabled=True, focus_backend="activate_window")
        with patch("input_controller.activate_window_for_region") as activate_mock:
            controller.focus_window(calibration)

        activate_mock.assert_called_once_with(calibration.window_region)
        self.assertEqual(controller.action_log, ["focus:left:250,112:activate_window"])

    def test_invalid_backend_fails(self):
        controller = InputController(dry_run=False, real_clicks_enabled=True, backend="invalido")
        with self.assertRaises(RealClickDisabledError):
            controller.click_point(Point(10, 20), "backend invalido")

    def test_setup_command_focuses_and_clicks_in_dry_run(self):
        calibration = sample_calibration()
        controller = InputController(dry_run=True)
        command = BoardBuildCommand(
            action=BoardBuildAction.CONFIRM,
            side=PlayerSide.LEFT,
            expected_number=26,
            detected_number=None,
            point=calibration.confirm_button,
        )
        self.assertTrue(controller.execute_setup_command(calibration, command))
        self.assertEqual(controller.action_log[0], "focus:left:250,112:activate_window")
        self.assertEqual(controller.action_log[1], "click:left Confirm:250,180:left")

    def test_battle_command_ignored_when_not_clickable(self):
        calibration = sample_calibration()
        controller = InputController(dry_run=True)
        command = BattleDryRunCommand(
            action=BattleDryRunAction.WAIT,
            side=PlayerSide.LEFT,
            sequence_index=0,
        )
        self.assertFalse(controller.execute_battle_command(calibration, command))
        self.assertEqual(controller.action_log, [])


if __name__ == "__main__":
    unittest.main()
