from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable

import config
from board_layout import Layout, cell_center, layout_for_side, number_to_cell
from calibrate import load_calibration
from models import Cell, PlayerCalibration, PlayerSide, Point
from setup_controller import SetupAction, SetupController, SetupStep
from setup_number_detector import SetupNumberDetection, detect_setup_number_for_player


class BoardBuildAction(Enum):
    PLACE_NUMBER = "place_number"
    RETRY_NUMBER = "retry_number"
    UNDO = "undo"
    CONFIRM = "confirm"
    WAIT = "wait"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class BoardBuildCommand:
    action: BoardBuildAction
    side: PlayerSide
    expected_number: int
    detected_number: int | None
    point: Point | None = None
    cell: Cell | None = None
    confidence: float | None = None
    reason: str = ""

    @property
    def executable(self) -> bool:
        return self.action in {
            BoardBuildAction.PLACE_NUMBER,
            BoardBuildAction.RETRY_NUMBER,
            BoardBuildAction.UNDO,
            BoardBuildAction.CONFIRM,
        }

    def describe(self) -> str:
        target = ""
        if self.cell is not None and self.point is not None:
            target = f" celula=({self.cell.row},{self.cell.col}) ponto=({self.point.x},{self.point.y})"
        elif self.point is not None:
            target = f" ponto=({self.point.x},{self.point.y})"
        confidence = "" if self.confidence is None else f" confianca={self.confidence:.3f}"
        detected = "UNKNOWN" if self.detected_number is None else str(self.detected_number)
        return (
            f"{self.side.value}: {self.action.value} esperado={self.expected_number} "
            f"detectado={detected}{confidence}{target} | {self.reason}"
        )


class BoardBuilderError(RuntimeError):
    pass


@dataclass
class BoardBuilder:
    calibration: PlayerCalibration
    layout: Layout
    controller: SetupController | None = None

    def __post_init__(self) -> None:
        if self.controller is None:
            self.controller = SetupController(layout=self.layout)

    def command_for_detection(self, detected_number: int | None, confidence: float | None = None) -> BoardBuildCommand:
        if self.controller is None:
            raise BoardBuilderError("Controlador de setup nao inicializado.")
        step = self.controller.step(detected_number)
        return self._command_from_step(step, confidence)

    def command_from_visual_detection(
        self,
        detector: Callable[[PlayerCalibration], SetupNumberDetection] = detect_setup_number_for_player,
    ) -> BoardBuildCommand:
        detection = detector(self.calibration)
        return self.command_for_detection(
            detected_number=detection.number if detection.found else None,
            confidence=detection.confidence,
        )

    def retry_number_command(self, number: int, confidence: float | None = None, reason: str = "") -> BoardBuildCommand:
        cell = number_to_cell(self.layout, number)
        expected_number = self.controller.expected_number if self.controller is not None else number + 1
        return BoardBuildCommand(
            action=BoardBuildAction.RETRY_NUMBER,
            side=self.calibration.side,
            expected_number=expected_number,
            detected_number=number,
            point=cell_center(self.calibration.grid_region, cell),
            cell=cell,
            confidence=confidence,
            reason=reason,
        )

    def _command_from_step(self, step: SetupStep, confidence: float | None) -> BoardBuildCommand:
        if step.action is SetupAction.PLACE_NUMBER:
            if step.cell is None:
                raise BoardBuilderError("Acao PLACE_NUMBER sem celula.")
            return BoardBuildCommand(
                action=BoardBuildAction.PLACE_NUMBER,
                side=self.calibration.side,
                expected_number=step.expected_number,
                detected_number=step.detected_number,
                point=cell_center(self.calibration.grid_region, step.cell),
                cell=step.cell,
                confidence=confidence,
                reason=step.reason,
            )
        if step.action is SetupAction.RETRY_NUMBER:
            if step.cell is None:
                raise BoardBuilderError("Acao RETRY_NUMBER sem celula.")
            return BoardBuildCommand(
                action=BoardBuildAction.RETRY_NUMBER,
                side=self.calibration.side,
                expected_number=step.expected_number,
                detected_number=step.detected_number,
                point=cell_center(self.calibration.grid_region, step.cell),
                cell=step.cell,
                confidence=confidence,
                reason=step.reason,
            )
        if step.action is SetupAction.UNDO_AND_RESTART:
            return BoardBuildCommand(
                action=BoardBuildAction.UNDO,
                side=self.calibration.side,
                expected_number=step.expected_number,
                detected_number=step.detected_number,
                point=self.calibration.undo_button,
                confidence=confidence,
                reason=step.reason,
            )
        if step.action is SetupAction.CONFIRM:
            return BoardBuildCommand(
                action=BoardBuildAction.CONFIRM,
                side=self.calibration.side,
                expected_number=step.expected_number,
                detected_number=step.detected_number,
                point=self.calibration.confirm_button,
                confidence=confidence,
                reason=step.reason,
            )
        if step.action is SetupAction.BLOCKED:
            return BoardBuildCommand(
                action=BoardBuildAction.BLOCKED,
                side=self.calibration.side,
                expected_number=step.expected_number,
                detected_number=step.detected_number,
                confidence=confidence,
                reason=step.reason,
            )
        return BoardBuildCommand(
            action=BoardBuildAction.WAIT,
            side=self.calibration.side,
            expected_number=step.expected_number,
            detected_number=step.detected_number,
            confidence=confidence,
            reason=step.reason,
        )


def build_scripted_dry_run(
    calibration: PlayerCalibration,
    layout: Layout,
    detected_numbers: Iterable[int | None],
) -> list[BoardBuildCommand]:
    builder = BoardBuilder(calibration=calibration, layout=layout)
    commands: list[BoardBuildCommand] = []
    for detected_number in detected_numbers:
        command = builder.command_for_detection(detected_number)
        commands.append(command)
        if command.action is BoardBuildAction.BLOCKED:
            break
    return commands


def simulate_setup_for_side(
    side: PlayerSide,
    winner_side: PlayerSide,
    detected_numbers: Iterable[int | None] | None = None,
) -> list[BoardBuildCommand]:
    calibration = load_calibration(side)
    layout = layout_for_side(side, winner_side, config.WINNER_LAYOUT, config.LOSER_LAYOUT)
    sequence = list(detected_numbers) if detected_numbers is not None else list(range(1, 26)) + [None]
    return build_scripted_dry_run(calibration, layout, sequence)
