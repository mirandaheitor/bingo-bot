import unittest

import config
from board_builder import BoardBuildAction, BoardBuilder, build_scripted_dry_run
from models import PlayerCalibration, PlayerSide, Point, Region
from setup_number_detector import SetupNumberDetection
from template_matcher import TemplateMatch


def sample_calibration() -> PlayerCalibration:
    return PlayerCalibration(
        side=PlayerSide.LEFT,
        name="teste",
        window_region=Region(x=0, y=0, width=300, height=260),
        grid_region=Region(x=10, y=20, width=100, height=100),
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


class BoardBuilderTests(unittest.TestCase):
    def test_place_number_uses_calibrated_grid_center(self):
        builder = BoardBuilder(sample_calibration(), config.WINNER_LAYOUT)
        command = builder.command_for_detection(1, confidence=0.99)
        self.assertEqual(command.action, BoardBuildAction.PLACE_NUMBER)
        self.assertEqual(command.point, Point(x=20, y=110))
        self.assertEqual(command.confidence, 0.99)

    def test_skipped_number_generates_undo_command(self):
        builder = BoardBuilder(sample_calibration(), config.WINNER_LAYOUT)
        builder.command_for_detection(1)
        command = builder.command_for_detection(3)
        self.assertEqual(command.action, BoardBuildAction.UNDO)
        self.assertEqual(command.point, Point(x=210, y=180))
        self.assertEqual(command.expected_number, 1)

    def test_previous_number_generates_retry_after_stale_wait(self):
        builder = BoardBuilder(sample_calibration(), config.WINNER_LAYOUT)
        builder.controller.max_stale_waits = 1
        builder.command_for_detection(1)
        wait = builder.command_for_detection(1)
        retry = builder.command_for_detection(1)
        self.assertEqual(wait.action, BoardBuildAction.WAIT)
        self.assertEqual(retry.action, BoardBuildAction.RETRY_NUMBER)
        self.assertEqual(retry.point, Point(x=20, y=110))
        self.assertTrue(retry.executable)

    def test_complete_board_generates_confirm_after_last_number(self):
        commands = build_scripted_dry_run(sample_calibration(), config.WINNER_LAYOUT, list(range(1, 26)) + [None])
        self.assertEqual(commands[-1].action, BoardBuildAction.CONFIRM)
        self.assertEqual(commands[-1].point, Point(x=250, y=180))

    def test_unknown_visual_detection_waits_without_click(self):
        builder = BoardBuilder(sample_calibration(), config.WINNER_LAYOUT)

        def detector(_calibration):
            return SetupNumberDetection(
                number=None,
                confidence=0.12,
                match=TemplateMatch(name="", found=False, confidence=0.12),
            )

        command = builder.command_from_visual_detection(detector=detector)
        self.assertEqual(command.action, BoardBuildAction.WAIT)
        self.assertFalse(command.executable)
        self.assertEqual(command.confidence, 0.12)


if __name__ == "__main__":
    unittest.main()
