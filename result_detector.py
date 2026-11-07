from __future__ import annotations

from pathlib import Path

import config
from calibrate import load_calibration
from capture import capture_region
from models import PlayerCalibration, PlayerSide, ResultState
from template_matcher import TemplateMatch, draw_match_box, find_best_template


STATE_DIR = Path("assets") / "states"
RESULT_TEMPLATE_MAP = {
    ResultState.WIN: "you_win.png",
    ResultState.LOSE: "you_lose.png",
    ResultState.DRAW: "draw.png",
}


def result_templates(directory: Path = STATE_DIR) -> list[tuple[str, Path]]:
    return [(state.value, directory / filename) for state, filename in RESULT_TEMPLATE_MAP.items()]


def detect_result(image, threshold: float = config.MIN_TEMPLATE_CONFIDENCE) -> tuple[ResultState, TemplateMatch]:
    match = find_best_template(image, result_templates(), threshold=threshold)
    if not match.found:
        return ResultState.NONE, match
    return ResultState(match.name), match


def detect_result_for_player(
    calibration: PlayerCalibration,
    debug_dir: Path | None = None,
    threshold: float = config.MIN_TEMPLATE_CONFIDENCE,
) -> ResultState:
    captured = capture_region(calibration.result_region)
    state, match = detect_result(captured.image, threshold=threshold)
    if debug_dir is not None and match.center is not None:
        draw_match_box(captured.image, match, debug_dir / f"result_{calibration.side.value}.png")
    return state


def detect_result_for_side(side: PlayerSide, debug_dir: Path | None = None) -> ResultState:
    return detect_result_for_player(load_calibration(side), debug_dir=debug_dir)
