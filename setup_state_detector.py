from __future__ import annotations

from pathlib import Path

import config
from calibrate import load_calibration
from capture import capture_region
from models import PlayerCalibration, PlayerSide, SetupState
from template_matcher import TemplateMatch, draw_match_box, find_best_template


STATE_DIR = Path("assets") / "states"
SETUP_STATE_TEMPLATE_MAP = {
    SetupState.READY: "ready.png",
}


def setup_state_templates(directory: Path = STATE_DIR) -> list[tuple[str, Path]]:
    return [(state.value, directory / filename) for state, filename in SETUP_STATE_TEMPLATE_MAP.items()]


def detect_setup_state(image, threshold: float = config.MIN_TEMPLATE_CONFIDENCE) -> tuple[SetupState, TemplateMatch]:
    match = find_best_template(image, setup_state_templates(), threshold=threshold)
    if not match.found:
        return SetupState.UNKNOWN, match
    return SetupState(match.name), match


def detect_setup_state_for_player(
    calibration: PlayerCalibration,
    debug_dir: Path | None = None,
    threshold: float = config.MIN_TEMPLATE_CONFIDENCE,
) -> SetupState:
    captured = capture_region(calibration.setup_text_region)
    state, match = detect_setup_state(captured.image, threshold=threshold)
    if debug_dir is not None and match.center is not None:
        draw_match_box(captured.image, match, debug_dir / f"setup_state_{calibration.side.value}.png")
    return state


def detect_setup_state_for_side(side: PlayerSide, debug_dir: Path | None = None) -> SetupState:
    return detect_setup_state_for_player(load_calibration(side), debug_dir=debug_dir)
