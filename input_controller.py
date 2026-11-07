from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable

import config
from board_builder import BoardBuildAction, BoardBuildCommand
from battle_runtime import BattleDryRunAction, BattleDryRunCommand
from hotkeys import BotCancelledError
from models import PlayerCalibration, Point
from window_message_input import activate_window_for_region, message_click_at_point


class RealClickDisabledError(RuntimeError):
    pass


def _import_pydirectinput():
    try:
        import pydirectinput
    except ImportError as exc:
        raise RealClickDisabledError("Instale as dependencias com: pip install -r requirements.txt") from exc
    return pydirectinput


@dataclass
class InputController:
    dry_run: bool = config.DRY_RUN
    real_clicks_enabled: bool = False
    backend: str = config.INPUT_BACKEND
    focus_backend: str = config.FOCUS_BACKEND
    move_duration: float = config.MOVE_DURATION
    cancel_checker: Callable[[], bool] | None = None
    action_log: list[str] = field(default_factory=list)

    def clear_log(self) -> None:
        self.action_log.clear()

    def focus_window(self, calibration: PlayerCalibration) -> None:
        point = Point(
            x=calibration.window_region.x + calibration.window_region.width // 2,
            y=calibration.window_region.y + 12,
        )
        if self.focus_backend == "activate_window":
            message = f"focus:{calibration.side.value}:{point.x},{point.y}:activate_window"
            self.action_log.append(message)
            logging.info("FOCO %s", message)
            if not self.dry_run:
                if not self.real_clicks_enabled:
                    raise RealClickDisabledError("Foco real bloqueado. Ative real_clicks_enabled explicitamente.")
                activate_window_for_region(calibration.window_region)
            return
        if self.focus_backend != "right_click":
            raise RealClickDisabledError(f"FOCUS_BACKEND invalido: {self.focus_backend}")
        self.click_point(point, label=f"foco {calibration.side.value}", button="right")

    def click_point(
        self,
        point: Point,
        label: str,
        button: str = "left",
        focus: PlayerCalibration | None = None,
        hold_seconds: float | None = None,
    ) -> None:
        self._check_cancel()
        if focus is not None:
            self.focus_window(focus)
        message = f"click:{label}:{point.x},{point.y}:{button}"
        self.action_log.append(message)
        logging.info("CLIQUE %s", message)
        if self.dry_run:
            return
        if not self.real_clicks_enabled:
            raise RealClickDisabledError("Clique real bloqueado. Ative real_clicks_enabled explicitamente.")
        if self.backend == "window_message":
            message_click_at_point(point, button=button, method=config.WINDOW_MESSAGE_METHOD)
            return
        if self.backend != "real_mouse":
            raise RealClickDisabledError(f"INPUT_BACKEND invalido: {self.backend}")
        pydirectinput = _import_pydirectinput()
        pydirectinput.moveTo(point.x, point.y, duration=self.move_duration)
        pydirectinput.mouseDown(button=button)
        time.sleep(config.CLICK_HOLD if hold_seconds is None else hold_seconds)
        pydirectinput.mouseUp(button=button)

    def execute_setup_command(self, calibration: PlayerCalibration, command: BoardBuildCommand, focus: bool = True) -> bool:
        focus_target = calibration if focus else None
        if command.action in {BoardBuildAction.PLACE_NUMBER, BoardBuildAction.RETRY_NUMBER} and command.point is not None:
            self.click_point(command.point, f"{calibration.side.value} numero {command.detected_number}", focus=focus_target)
            return True
        if command.action is BoardBuildAction.UNDO and command.point is not None:
            self.click_point(command.point, f"{calibration.side.value} Undo", focus=focus_target)
            return True
        if command.action is BoardBuildAction.CONFIRM and command.point is not None:
            self.click_point(command.point, f"{calibration.side.value} Confirm", focus=focus_target)
            return True
        return False

    def execute_battle_command(self, calibration: PlayerCalibration, command: BattleDryRunCommand, focus: bool = True) -> bool:
        if command.action in {BattleDryRunAction.CALL_NUMBER, BattleDryRunAction.RETRY_CALL_NUMBER} and command.point is not None:
            self.click_point(
                command.point,
                f"{calibration.side.value} chamada {command.number}",
                focus=calibration if focus else None,
            )
            return True
        return False

    def click_continue(self, calibration: PlayerCalibration) -> None:
        self.click_point(calibration.continue_button, f"{calibration.side.value} Continue", focus=calibration)

    def _check_cancel(self) -> None:
        if self.cancel_checker is not None and self.cancel_checker():
            raise BotCancelledError("Interrompido por ESC.")
