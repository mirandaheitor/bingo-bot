from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import config
from battle_runtime import BattleDryRunAction, BattleDryRunCommand, BattleDryRunRuntime
from board_builder import BoardBuildAction, BoardBuildCommand, BoardBuilder
from board_layout import layout_for_side
from calibrate import load_calibration
from hotkeys import raise_if_escape_pressed
from input_controller import InputController
from models import MatchObservation, PlayerCalibration, PlayerObservation, PlayerSide, ResultState, SetupState, TurnState
from result_detector import detect_result_for_player
from setup_number_detector import detect_setup_number_for_player
from setup_state_detector import detect_setup_state_for_player
from turn_detector import detect_turn_for_player


class BotRunError(RuntimeError):
    pass


@dataclass(frozen=True)
class SetupRunResult:
    side: PlayerSide
    completed: bool
    cycles: int
    reason: str


@dataclass(frozen=True)
class SetupBothRunResult:
    completed: bool
    cycles: int
    reason: str


@dataclass(frozen=True)
class MatchRunResult:
    completed: bool
    cycles: int
    reason: str


@dataclass
class BotRuntime:
    winner_side: PlayerSide
    dry_run: bool = True
    real_clicks_enabled: bool = False
    input_controller: InputController | None = None

    def __post_init__(self) -> None:
        self.focused_side: PlayerSide | None = None
        self.calibrations = {
            PlayerSide.LEFT: load_calibration(PlayerSide.LEFT),
            PlayerSide.RIGHT: load_calibration(PlayerSide.RIGHT),
        }
        if self.input_controller is None:
            self.input_controller = InputController(
                dry_run=self.dry_run,
                real_clicks_enabled=self.real_clicks_enabled,
            )

    def run_match(self, max_cycles: int, debug_root: Path | None = None) -> MatchRunResult:
        debug_root = debug_root or Path("debug") / f"real_match_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        debug_root.mkdir(parents=True, exist_ok=True)

        setup = self.run_setup_both(max_cycles=max_cycles, debug_dir=debug_root / "setup")
        if not setup.completed:
            return MatchRunResult(False, setup.cycles, setup.reason)

        battle = self.run_battle(max_cycles=max_cycles, debug_dir=debug_root / "battle")
        return MatchRunResult(
            completed=battle.completed,
            cycles=setup.cycles + battle.cycles,
            reason=battle.reason,
        )

    def run_setup_both(self, max_cycles: int, debug_dir: Path) -> SetupBothRunResult:
        debug_dir.mkdir(parents=True, exist_ok=True)
        sides = [PlayerSide.LEFT, PlayerSide.RIGHT]
        builders = {
            side: BoardBuilder(
                calibration=self.calibrations[side],
                layout=layout_for_side(side, self.winner_side, config.WINNER_LAYOUT, config.LOSER_LAYOUT),
            )
            for side in sides
        }
        completed = {side: False for side in sides}
        unknown_counts = {side: 0 for side in sides}
        final_number_retries = {side: 0 for side in sides}

        for cycle in range(1, max_cycles + 1):
            for side in sides:
                if completed[side]:
                    continue

                raise_if_escape_pressed()
                calibration = self.calibrations[side]
                self._focus_for_read(calibration)
                command = builders[side].command_from_visual_detection(
                    detector=lambda current_calibration: detect_setup_number_for_player(
                        current_calibration,
                        debug_dir / current_calibration.side.value if config.SAVE_DEBUG_IMAGES else None,
                    )
                )
                if command.action is BoardBuildAction.CONFIRM:
                    command = self._confirm_or_retry_setup_ready(
                        builder=builders[side],
                        calibration=calibration,
                        command=command,
                        retry_counts=final_number_retries,
                        debug_dir=debug_dir,
                    )
                print(f"SETUP {cycle}: {command.describe()}")

                if command.action is BoardBuildAction.WAIT:
                    unknown_counts[side] += 1
                    if unknown_counts[side] >= config.MAX_UNKNOWN_RETRIES:
                        return SetupBothRunResult(False, cycle, f"{side.value}: Numero de preparacao UNKNOWN repetido.")
                    self._sleep(config.LOOP_INTERVAL)
                    continue

                unknown_counts[side] = 0

                if command.action is BoardBuildAction.BLOCKED:
                    return SetupBothRunResult(False, cycle, f"{side.value}: {command.reason}")

                executed = self.input_controller.execute_setup_command(calibration, command, focus=False)
                self._sleep(_setup_delay(command))

                if command.action is BoardBuildAction.CONFIRM:
                    completed[side] = True
                elif not executed:
                    self._sleep(config.LOOP_INTERVAL)

            if all(completed.values()):
                return SetupBothRunResult(True, cycle, "Cartelas confirmadas.")

        return SetupBothRunResult(False, max_cycles, "Limite de ciclos de setup excedido.")

    def run_setup(self, side: PlayerSide, max_cycles: int, debug_dir: Path) -> SetupRunResult:
        debug_dir.mkdir(parents=True, exist_ok=True)
        calibration = self.calibrations[side]
        layout = layout_for_side(side, self.winner_side, config.WINNER_LAYOUT, config.LOSER_LAYOUT)
        builder = BoardBuilder(calibration=calibration, layout=layout)
        unknown_count = 0

        for cycle in range(1, max_cycles + 1):
            raise_if_escape_pressed()
            self._focus_for_read(calibration)
            command = builder.command_from_visual_detection(
                detector=lambda current_calibration: detect_setup_number_for_player(
                    current_calibration,
                    debug_dir if config.SAVE_DEBUG_IMAGES else None,
                )
            )
            print(f"SETUP {cycle}: {command.describe()}")

            if command.action is BoardBuildAction.WAIT:
                unknown_count += 1
                if unknown_count >= config.MAX_UNKNOWN_RETRIES:
                    return SetupRunResult(side, False, cycle, "Numero de preparacao UNKNOWN repetido.")
                self._sleep(config.LOOP_INTERVAL)
                continue

            unknown_count = 0

            if command.action is BoardBuildAction.BLOCKED:
                return SetupRunResult(side, False, cycle, command.reason)

            executed = self.input_controller.execute_setup_command(calibration, command, focus=False)
            self._sleep(_setup_delay(command))

            if command.action is BoardBuildAction.CONFIRM:
                return SetupRunResult(side, True, cycle, "Cartela confirmada.")
            if not executed:
                self._sleep(config.LOOP_INTERVAL)

        return SetupRunResult(side, False, max_cycles, "Limite de ciclos de setup excedido.")

    def run_battle(self, max_cycles: int, debug_dir: Path) -> MatchRunResult:
        debug_dir.mkdir(parents=True, exist_ok=True)
        battle = BattleDryRunRuntime(
            winner_side=self.winner_side,
            left_calibration=self.calibrations[PlayerSide.LEFT],
            right_calibration=self.calibrations[PlayerSide.RIGHT],
        )
        wait_count = 0

        for cycle in range(1, max_cycles + 1):
            raise_if_escape_pressed()
            observation = self._observe_battle_focused(debug_dir if config.SAVE_DEBUG_IMAGES else None)
            command = battle.step(observation)
            print(
                f"BATALHA {cycle}: left turno={observation.left.turn_state.value} resultado={observation.left.result_state.value} | "
                f"right turno={observation.right.turn_state.value} resultado={observation.right.result_state.value}"
            )
            print(f"BATALHA {cycle}: {command.describe()}")

            if command.action is BattleDryRunAction.WAIT:
                wait_count += 1
                if battle.call_index == 0 and wait_count >= config.MAX_READY_RECOVERY_WAITS:
                    recovered = self._recover_ready_if_needed(observation)
                    if recovered:
                        wait_count = 0
                        continue
                if wait_count >= config.MAX_BATTLE_WAIT_RETRIES:
                    return MatchRunResult(False, cycle, "Turno nao acionavel repetido.")
                self._sleep(config.LOOP_INTERVAL)
                continue

            wait_count = 0

            if command.action is BattleDryRunAction.BLOCKED:
                return MatchRunResult(False, cycle, command.reason)

            if command.action is BattleDryRunAction.CONTINUE_BOTH:
                if self._click_continue_both(debug_dir):
                    return MatchRunResult(True, cycle, "Resultado confirmado nas duas instancias.")
                return MatchRunResult(False, cycle, "Continue/OK nao fechou resultado nas duas instancias.")

            command_side = _require_side(command)
            calibration = self.calibrations[command_side]
            should_focus = self.focused_side is not command_side
            self.input_controller.execute_battle_command(calibration, command, focus=should_focus)
            self.focused_side = command_side
            self._sleep(config.DELAY_AFTER_BATTLE_CLICK)

        return MatchRunResult(False, max_cycles, "Limite de ciclos de batalha excedido.")

    def _click_continue_both(self, debug_dir: Path) -> bool:
        self._sleep(config.DELAY_AFTER_RESULT)
        pending = [PlayerSide.LEFT, PlayerSide.RIGHT]
        for attempt in range(1, config.MAX_CONTINUE_RETRIES + 1):
            for index, side in enumerate(list(pending)):
                self.input_controller.click_continue(self.calibrations[side])
                if index < len(pending) - 1:
                    self._sleep(config.DELAY_BETWEEN_CONTINUE_CLICKS)
            self._sleep(config.DELAY_AFTER_CONTINUE)

            pending = [
                side
                for side in pending
                if self._result_still_visible(
                    self.calibrations[side],
                    debug_dir / f"continue_retry_{attempt}" if config.SAVE_DEBUG_IMAGES else None,
                )
            ]
            if not pending:
                return True
            print(f"Continue/OK ainda visivel em: {', '.join(side.value for side in pending)}; tentando novamente.")
        return False

    def _result_still_visible(self, calibration: PlayerCalibration, debug_dir: Path | None) -> bool:
        self._focus_for_read(calibration)
        result = detect_result_for_player(calibration, debug_dir)
        return result in {ResultState.WIN, ResultState.LOSE, ResultState.DRAW}

    def _confirm_or_retry_setup_ready(
        self,
        builder: BoardBuilder,
        calibration: PlayerCalibration,
        command: BoardBuildCommand,
        retry_counts: dict[PlayerSide, int],
        debug_dir: Path,
    ) -> BoardBuildCommand:
        state = detect_setup_state_for_player(
            calibration,
            debug_dir / calibration.side.value if config.SAVE_DEBUG_IMAGES else None,
        )
        if state is SetupState.READY:
            retry_counts[calibration.side] = 0
            return command

        retry_counts[calibration.side] += 1
        if retry_counts[calibration.side] > config.MAX_FINAL_NUMBER_RETRIES:
            return BoardBuildCommand(
                action=BoardBuildAction.BLOCKED,
                side=calibration.side,
                expected_number=command.expected_number,
                detected_number=command.detected_number,
                confidence=command.confidence,
                reason="Cartela completa planejada, mas READY nao apareceu apos repetir o 25.",
            )

        return builder.retry_number_command(
            25,
            confidence=command.confidence,
            reason="Cartela completa ainda nao esta READY; repetir numero 25 antes de Confirm.",
        )

    def _recover_ready_if_needed(self, observation: MatchObservation) -> bool:
        sides: list[PlayerSide] = []
        if observation.left.turn_state is TurnState.UNKNOWN and observation.right.turn_state is TurnState.WAITING:
            sides.append(PlayerSide.LEFT)
        elif observation.right.turn_state is TurnState.UNKNOWN and observation.left.turn_state is TurnState.WAITING:
            sides.append(PlayerSide.RIGHT)
        elif observation.left.turn_state is TurnState.UNKNOWN and observation.right.turn_state is TurnState.UNKNOWN:
            sides.extend([PlayerSide.LEFT, PlayerSide.RIGHT])

        if not sides:
            return False

        recovered = False
        for side in sides:
            calibration = self.calibrations[side]
            self._focus_for_read(calibration)
            setup_state = detect_setup_state_for_player(calibration)
            if setup_state is not SetupState.READY:
                continue
            self.input_controller.click_point(calibration.confirm_button, f"{side.value} Confirm recuperacao", focus=calibration)
            self._sleep(config.DELAY_AFTER_CONFIRM)
            recovered = True
        return recovered

    def _observe_battle_focused(self, debug_dir: Path | None) -> MatchObservation:
        left = self._observe_player_focused(PlayerSide.LEFT, debug_dir)
        right = self._observe_player_focused(PlayerSide.RIGHT, debug_dir)
        return MatchObservation(left=left, right=right)

    def _observe_player_focused(self, side: PlayerSide, debug_dir: Path | None) -> PlayerObservation:
        calibration = self.calibrations[side]
        self._focus_for_read(calibration)
        return PlayerObservation(
            turn_state=detect_turn_for_player(calibration, debug_dir),
            result_state=detect_result_for_player(calibration, debug_dir),
        )

    def _focus_for_read(self, calibration: PlayerCalibration) -> None:
        self.input_controller.focus_window(calibration)
        self.focused_side = calibration.side
        self._sleep(config.DELAY_AFTER_FOCUS)

    def _sleep(self, seconds: float) -> None:
        deadline = time.monotonic() + max(0.0, seconds)
        while True:
            raise_if_escape_pressed()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(0.05, remaining))


def _setup_delay(command: BoardBuildCommand) -> float:
    if command.action is BoardBuildAction.UNDO:
        return config.DELAY_AFTER_UNDO
    if command.action is BoardBuildAction.CONFIRM:
        return config.DELAY_AFTER_CONFIRM
    if command.action in {BoardBuildAction.PLACE_NUMBER, BoardBuildAction.RETRY_NUMBER}:
        return config.DELAY_AFTER_SETUP_CLICK
    return config.LOOP_INTERVAL


def _require_side(command: BattleDryRunCommand) -> PlayerSide:
    if command.side is None:
        raise BotRunError("Comando de batalha sem instancia.")
    return command.side
