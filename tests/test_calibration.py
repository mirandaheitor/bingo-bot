import tempfile
import unittest
from pathlib import Path

from calibrate import (
    calibration_from_file_data,
    calibration_to_file_data,
    load_calibration,
    make_region,
    point_to_absolute,
    point_to_relative,
    save_calibration,
)
from models import PlayerCalibration, PlayerSide, Point, Region


def sample_calibration() -> PlayerCalibration:
    return PlayerCalibration(
        side=PlayerSide.LEFT,
        name="teste",
        window_region=Region(x=-100, y=50, width=300, height=200),
        grid_region=Region(x=-80, y=80, width=100, height=100),
        setup_number_region=Region(x=20, y=90, width=40, height=30),
        setup_text_region=Region(x=-90, y=210, width=180, height=20),
        turn_region=Region(x=-90, y=220, width=200, height=20),
        result_region=Region(x=-70, y=100, width=140, height=90),
        ready_button=Point(x=150, y=210),
        undo_button=Point(x=130, y=210),
        clear_button=Point(x=110, y=210),
        confirm_button=Point(x=160, y=210),
        continue_button=Point(x=170, y=230),
    )


class CalibrationTests(unittest.TestCase):
    def test_make_region_normalizes_points(self):
        region = make_region(Point(x=20, y=40), Point(x=10, y=10))
        self.assertEqual(region, Region(x=10, y=10, width=10, height=30))

    def test_file_data_uses_relative_coordinates(self):
        data = calibration_to_file_data(sample_calibration())
        self.assertEqual(data["coordinate_mode"], "relative_to_window")
        self.assertEqual(data["regions"]["grid_region"]["x"], 20)
        self.assertEqual(data["regions"]["grid_region"]["y"], 30)
        self.assertEqual(data["points"]["continue_button"]["x"], 270)
        self.assertEqual(data["points"]["continue_button"]["y"], 180)

    def test_roundtrip_restores_absolute_coordinates(self):
        calibration = sample_calibration()
        restored = calibration_from_file_data(calibration_to_file_data(calibration))
        self.assertEqual(restored, calibration)

    def test_save_and_load_calibration(self):
        calibration = sample_calibration()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "player_left.json"
            save_calibration(calibration, path)
            self.assertEqual(load_calibration(PlayerSide.LEFT, path), calibration)

    def test_continue_button_can_differ_from_confirm_button(self):
        calibration = sample_calibration()
        data = calibration_to_file_data(calibration)
        self.assertNotEqual(data["points"]["continue_button"], data["points"]["confirm_button"])
        restored = calibration_from_file_data(data)
        self.assertNotEqual(restored.continue_button, restored.confirm_button)

    def test_point_relative_roundtrip(self):
        window = Region(x=500, y=300, width=200, height=200)
        point = Point(x=650, y=420)
        self.assertEqual(point_to_absolute(point_to_relative(point, window), window), point)


if __name__ == "__main__":
    unittest.main()
