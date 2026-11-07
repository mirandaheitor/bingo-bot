from __future__ import annotations

from pathlib import Path

import config
from calibrate import load_calibration
from capture import capture_region
from models import PlayerCalibration, PlayerSide, TurnState
from template_matcher import TemplateMatch, draw_match_box, find_best_template


STATE_DIR = Path("assets") / "states"
TURN_TEMPLATE_MAP = {
    TurnState.MY_TURN: "my_turn.png",
    TurnState.WAITING: "waiting.png",
}


def turn_templates(directory: Path = STATE_DIR) -> list[tuple[str, Path]]:
    return [(state.value, directory / filename) for state, filename in TURN_TEMPLATE_MAP.items()]


def detect_turn(image, threshold: float = config.MIN_TEMPLATE_CONFIDENCE) -> tuple[TurnState, TemplateMatch]:
    match = find_best_template(image, turn_templates(), threshold=threshold)
    if not match.found:
        return TurnState.UNKNOWN, match
    return TurnState(match.name), match


def detect_turn_for_player(
    calibration: PlayerCalibration,
    debug_dir: Path | None = None,
    threshold: float = config.MIN_TEMPLATE_CONFIDENCE,
) -> TurnState:
    captured = capture_region(calibration.turn_region)
    state, match = detect_turn(captured.image, threshold=threshold)
    if debug_dir is not None and match.center is not None:
        draw_match_box(captured.image, match, debug_dir / f"turn_{calibration.side.value}.png")
    return state


def detect_turn_for_side(side: PlayerSide, debug_dir: Path | None = None) -> TurnState:
    return detect_turn_for_player(load_calibration(side), debug_dir=debug_dir)
