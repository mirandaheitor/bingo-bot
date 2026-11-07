from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PlayerSide(Enum):
    LEFT = "left"
    RIGHT = "right"


class PlayerRole(Enum):
    WINNER = "winner"
    LOSER = "loser"


class SetupState(Enum):
    NOT_STARTED = "not_started"
    PLACING = "placing"
    READY = "ready"
    ERROR = "error"
    UNKNOWN = "unknown"


class TurnState(Enum):
    MY_TURN = "my_turn"
    WAITING = "waiting"
    UNKNOWN = "unknown"


class ResultState(Enum):
    WIN = "win"
    LOSE = "lose"
    DRAW = "draw"
    NONE = "none"
    UNKNOWN = "unknown"


class BotState(Enum):
    IDLE = "idle"
    SETUP_LEFT = "setup_left"
    SETUP_RIGHT = "setup_right"
    CONFIRM_LEFT = "confirm_left"
    CONFIRM_RIGHT = "confirm_right"
    WAIT_FIRST_TURN = "wait_first_turn"
    BATTLE = "battle"
    CHECK_RESULT = "check_result"
    CONTINUE_BOTH = "continue_both"
    WAIT_NEXT_MATCH = "wait_next_match"
    FINISHED = "finished"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass(frozen=True)
class Region:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class Point:
    x: int
    y: int


@dataclass(frozen=True)
class Cell:
    row: int
    col: int


@dataclass(frozen=True)
class PlayerCalibration:
    side: PlayerSide
    window_region: Region
    grid_region: Region
    setup_number_region: Region
    setup_text_region: Region
    turn_region: Region
    result_region: Region
    ready_button: Point
    undo_button: Point
    clear_button: Point
    confirm_button: Point
    continue_button: Point
    name: str = ""


@dataclass(frozen=True)
class PlayerObservation:
    turn_state: TurnState = TurnState.UNKNOWN
    result_state: ResultState = ResultState.NONE
    setup_state: SetupState = SetupState.UNKNOWN


@dataclass(frozen=True)
class MatchObservation:
    left: PlayerObservation
    right: PlayerObservation


@dataclass(frozen=True)
class StepResult:
    state_before: BotState
    state_after: BotState
    action: str | None
    reason: str
