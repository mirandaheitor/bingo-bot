import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from models import ResultState, SetupState, TurnState
from result_detector import detect_result
from setup_number_detector import detect_setup_number
from setup_state_detector import detect_setup_state
from template_matcher import find_best_template, match_template
from turn_detector import detect_turn


def patterned_template() -> Image.Image:
    image = Image.new("RGB", (8, 8), "white")
    pixels = image.load()
    for index in range(8):
        pixels[index, index] = (0, 0, 0)
        pixels[7 - index, index] = (0, 0, 0)
    return image


def image_with_template(template: Image.Image) -> Image.Image:
    image = Image.new("RGB", (30, 30), "white")
    image.paste(template, (11, 13))
    return image


class TemplateDetectionTests(unittest.TestCase):
    def test_match_template_finds_inserted_pattern(self):
        template = patterned_template()
        image = image_with_template(template)
        match = match_template(image, template, name="x", threshold=0.90)
        self.assertTrue(match.found)
        self.assertGreaterEqual(match.confidence, 0.90)
        self.assertEqual(match.top_left.x, 11)
        self.assertEqual(match.top_left.y, 13)

    def test_template_larger_than_image_does_not_match(self):
        match = match_template(Image.new("RGB", (5, 5)), Image.new("RGB", (10, 10)), threshold=0.90)
        self.assertFalse(match.found)
        self.assertEqual(match.confidence, 0.0)

    def test_find_best_template_ignores_missing_files(self):
        match = find_best_template(Image.new("RGB", (10, 10)), [("missing", Path("missing.png"))], threshold=0.90)
        self.assertFalse(match.found)
        self.assertEqual(match.name, "")

    def test_setup_number_detector_uses_best_numeric_template(self):
        template = patterned_template()
        image = image_with_template(template)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "7.png"
            template.save(path)
            with patch("setup_number_detector.setup_number_templates", return_value=[("7", path)]):
                detection = detect_setup_number(image, threshold=0.90)
        self.assertTrue(detection.found)
        self.assertEqual(detection.number, 7)

    def test_turn_detector_returns_unknown_below_threshold(self):
        with patch("turn_detector.turn_templates", return_value=[]):
            state, match = detect_turn(Image.new("RGB", (10, 10)), threshold=0.90)
        self.assertEqual(state, TurnState.UNKNOWN)
        self.assertFalse(match.found)

    def test_setup_state_detector_returns_ready(self):
        template = patterned_template()
        image = image_with_template(template)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "ready.png"
            template.save(path)
            with patch("setup_state_detector.setup_state_templates", return_value=[("ready", path)]):
                state, match = detect_setup_state(image, threshold=0.90)
        self.assertEqual(state, SetupState.READY)
        self.assertTrue(match.found)

    def test_result_detector_returns_result_state(self):
        template = patterned_template()
        image = image_with_template(template)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "you_win.png"
            template.save(path)
            with patch("result_detector.result_templates", return_value=[("win", path)]):
                state, match = detect_result(image, threshold=0.90)
        self.assertEqual(state, ResultState.WIN)
        self.assertTrue(match.found)


if __name__ == "__main__":
    unittest.main()
