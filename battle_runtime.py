from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import config
from board_layout import Layout, cell_center, layout_for_side, number_to_cell
from calibrate import load_calibration
from models import MatchObservation, PlayerCalibration, PlayerObservation, PlayerSide, Point, ResultState, TurnState
from result_detector import detect_result_for_player
from turn_detector import detect_turn_for_player


class BattleDryRunAction(Enum):
    CALL_NUMBER = "call_number"
    RETRY_CALL_NUMBER = "retry_call_number"
    CONTINUE_BOTH = "continue_both"
    WAIT = "wait"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class BattleDryRunCommand:
    action: BattleDryRunAction
    side: PlayerSide | None
    sequence_index: int
    number: int | None = None
    cell: object | None = None
    point: Point | None = None
    reason: str = ""

    @property
    def executable(self) -> bool:
        return self.action in {BattleDryRunAction.CALL_NUMBER, BattleDryRunAction.CONTINUE_BOTH}

    def describe(self) -> str:
        side = "both" if self.side is None else self.side.value
        number = "" if self.number is None else f" numero={self.number}"
        cell = "" if self.cell is None else f" celula=({self.cell.row},{self.cell.col})"
        point = "" if self.point is None else f" ponto=({self.point.x},{self.point.y})"
        return f"{side}: {self.action.value} seq={self.sequence_index}{number}{cell}{point} | {self.reason}"


@dataclass(frozen=True)
class BattleDryRunCycle:
    observation: MatchObservation
    command: BattleDryRunCommand

    def describe(self) -> str:
        return (
            f"LEFT turno={self.observation.left.turn_state.value} resultado={self.observation.left.result_state.value} | "
            f"RIGHT turno={self.observation.right.turn_state.value} resultado={self.observation.right.result_state.value}\n"
            f"DRY-RUN {self.command.describe()}"
        )


@dataclass
class BattleDryRunRuntime:
    winner_side: PlayerSide
    left_calibration: PlayerCalibration
    right_calibration: PlayerCalibration
    winner_layout: Layout = field(default_factory=lambda: [list(row) for row in config.WINNER_LAYOUT])
    loser_layout: Layout = field(default_factory=lambda: [list(row) for row in config.LOSER_LAYOUT])
    call_sequence: list[int] = field(default_factory=lambda: list(config.CALL_SEQUENCE))
    call_index: int = 0
    last_planned_turn: PlayerSide | None = None
    last_call_command: BattleDryRunCommand | None = None
    stale_turn_waits: int = 0

    @classmethod
    def from_calibrations(cls, winner_side: PlayerSide) -> "BattleDryRunRuntime":
        return cls(
            winner_side=winner_side,
            left_calibration=load_calibration(PlayerSide.LEFT),
            right_calibration=load_calibration(PlayerSide.RIGHT),
        )

    def observe(self, debug_dir: Path | None = None) -> MatchObservation:
        return MatchObservation(
            left=PlayerObservation(
                turn_state=detect_turn_for_player(self.left_calibration, debug_dir),
                result_state=detect_result_for_player(self.left_calibration, debug_dir),
            ),
            right=PlayerObservation(
                turn_state=detect_turn_for_player(self.right_calibration, debug_dir),
                result_state=detect_result_for_player(self.right_calibration, debug_dir),
            ),
        )

    def step(self, observation: MatchObservation) -> BattleDryRunCommand:
        if _has_visible_result(observation):
            return BattleDryRunCommand(
                action=BattleDryRunAction.CONTINUE_BOTH,
                side=None,
                sequence_index=self.call_index,
                reason="Resultado detectado; na etapa real deve clicar Continue/OK nas duas instancias.",
            )

        active_side = _active_side(observation)
        if active_side is None:
            self.last_planned_turn = None
            self.last_call_command = None
            self.stale_turn_waits = 0
            return BattleDryRunCommand(
                action=BattleDryRunAction.WAIT,
                side=None,
                sequence_index=self.call_index,
                reason="Nenhum turno unico detectado; nao planejar clique.",
            )

        if self.last_planned_turn is active_side:
            self.stale_turn_waits += 1
            if self.last_call_command is not None and self.stale_turn_waits >= config.MAX_STALE_TURN_WAITS:
                self.stale_turn_waits = 0
                return BattleDryRunCommand(
                    action=BattleDryRunAction.RETRY_CALL_NUMBER,
                    side=self.last_call_command.side,
                    sequence_index=self.last_call_command.sequence_index,
                    number=self.last_call_command.number,
                    cell=self.last_call_command.cell,
                    point=self.last_call_command.point,
                    reason="Mesmo turno persistente; repetir ultima chamada sem consumir sequencia.",
                )
            return BattleDryRunCommand(
                action=BattleDryRunAction.WAIT,
                side=active_side,
                sequence_index=self.call_index,
                reason="Acao ja planejada para este turno; aguarde mudanca de tela ou avance manualmente.",
            )

        if self.call_index >= len(self.call_sequence):
            return BattleDryRunCommand(
                action=BattleDryRunAction.BLOCKED,
                side=active_side,
                sequence_index=self.call_index,
                reason="Sequencia de chamadas esgotada.",
            )

        number = self.call_sequence[self.call_index]
        layout = self.layout_for(active_side)
        calibration = self.calibration_for(active_side)
        cell = number_to_cell(layout, number)
        point = cell_center(calibration.grid_region, cell)
        command = BattleDryRunCommand(
            action=BattleDryRunAction.CALL_NUMBER,
            side=active_side,
            sequence_index=self.call_index,
            number=number,
            cell=cell,
            point=point,
            reason="Turno detectado; numero da sequencia configurada.",
        )
        self.call_index += 1
        self.last_planned_turn = active_side
        self.last_call_command = command
        self.stale_turn_waits = 0
        return command

    def observe_and_step(self, debug_dir: Path | None = None) -> BattleDryRunCycle:
        observation = self.observe(debug_dir)
        return BattleDryRunCycle(observation=observation, command=self.step(observation))

    def layout_for(self, side: PlayerSide) -> Layout:
        return layout_for_side(side, self.winner_side, self.winner_layout, self.loser_layout)

    def calibration_for(self, side: PlayerSide) -> PlayerCalibration:
        return self.left_calibration if side is PlayerSide.LEFT else self.right_calibration


def _active_side(observation: MatchObservation) -> PlayerSide | None:
    if observation.left.turn_state is TurnState.MY_TURN and observation.right.turn_state is not TurnState.MY_TURN:
        return PlayerSide.LEFT
    if observation.right.turn_state is TurnState.MY_TURN and observation.left.turn_state is not TurnState.MY_TURN:
        return PlayerSide.RIGHT
    return None


def _has_visible_result(observation: MatchObservation) -> bool:
    visible = {ResultState.WIN, ResultState.LOSE, ResultState.DRAW}
    return observation.left.result_state in visible or observation.right.result_state in visible
