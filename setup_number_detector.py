from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import config
from calibrate import load_calibration
from capture import capture_region
from models import PlayerCalibration, PlayerSide
from template_matcher import TemplateMatch, draw_match_box, find_best_template


SETUP_NUMBER_DIR = Path("assets") / "setup_numbers"


@dataclass(frozen=True)
class SetupNumberDetection:
    number: int | None
    confidence: float
    match: TemplateMatch

    @property
    def found(self) -> bool:
        return self.number is not None and self.match.found


def setup_number_templates(directory: Path = SETUP_NUMBER_DIR) -> list[tuple[str, Path]]:
    return [(str(number), directory / f"{number}.png") for number in range(1, 26)]


def detect_setup_number(image, threshold: float = config.MIN_TEMPLATE_CONFIDENCE) -> SetupNumberDetection:
    match = find_best_template(image, setup_number_templates(), threshold=threshold)
    number = int(match.name) if match.found and match.name.isdigit() else None
    return SetupNumberDetection(number=number, confidence=match.confidence, match=match)


def detect_setup_number_for_player(
    calibration: PlayerCalibration,
    debug_dir: Path | None = None,
    threshold: float = config.MIN_TEMPLATE_CONFIDENCE,
) -> SetupNumberDetection:
    captured = capture_region(calibration.setup_number_region)
    detection = detect_setup_number(captured.image, threshold=threshold)
    if debug_dir is not None and detection.match.center is not None:
        draw_match_box(captured.image, detection.match, debug_dir / f"setup_number_{calibration.side.value}.png")
    return detection


def detect_setup_number_for_side(side: PlayerSide, debug_dir: Path | None = None) -> SetupNumberDetection:
    return detect_setup_number_for_player(load_calibration(side), debug_dir=debug_dir)
