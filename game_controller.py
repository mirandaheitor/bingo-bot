from __future__ import annotations

from dataclasses import dataclass, field

import config
from board_layout import layout_for_side
from models import BotState, MatchObservation, PlayerObservation, PlayerSide, ResultState, StepResult, TurnState


VISIBLE_RESULTS = {ResultState.WIN, ResultState.LOSE, ResultState.DRAW}


class GameControllerError(RuntimeError):
    pass


@dataclass
class GameController:
    winner_side: PlayerSide
    winner_layout: list[list[int]] = field(default_factory=lambda: [list(row) for row in config.WINNER_LAYOUT])
    loser_layout: list[list[int]] = field(default_factory=lambda: [list(row) for row in config.LOSER_LAYOUT])
    call_sequence: list[int] = field(default_factory=lambda: list(config.CALL_SEQUENCE))
    state: BotState = BotState.IDLE
    call_index: int = 0

    def start(self) -> StepResult:
        state_before = self.state
        if self.state is not BotState.IDLE:
            raise GameControllerError("Controller ja iniciado.")
        self.state = BotState.SETUP_LEFT
        return StepResult(state_before, self.state, "setup_left", "Iniciar montagem da instancia esquerda.")

    def step(self, observation: MatchObservation) -> StepResult:
        state_before = self.state

        if self.state in {BotState.FINISHED, BotState.ERROR, BotState.STOPPED}:
            return StepResult(state_before, self.state, None, "Estado terminal.")

        if self._any_result_visible(observation):
            self.state = BotState.CHECK_RESULT

        if self.state is BotState.IDLE:
            return self.start()
        if self.state is BotState.SETUP_LEFT:
            self.state = BotState.SETUP_RIGHT
            return StepResult(state_before, self.state, "setup_right", "Montagem esquerda planejada; iniciar direita.")
        if self.state is BotState.SETUP_RIGHT:
            self.state = BotState.CONFIRM_LEFT
            return StepResult(state_before, self.state, "confirm_left", "Montagem direita planejada; confirmar esquerda.")
        if self.state is BotState.CONFIRM_LEFT:
            self.state = BotState.CONFIRM_RIGHT
            return StepResult(state_before, self.state, "confirm_right", "Confirmar direita.")
        if self.state is BotState.CONFIRM_RIGHT:
            self.state = BotState.WAIT_FIRST_TURN
            return StepResult(state_before, self.state, None, "Aguardar primeiro turno.")
        if self.state is BotState.WAIT_FIRST_TURN:
            return self._battle_step(state_before, observation, first_turn=True)
        if self.state is BotState.BATTLE:
            return self._battle_step(state_before, observation, first_turn=False)
        if self.state is BotState.CHECK_RESULT:
            self.state = BotState.CONTINUE_BOTH
            return StepResult(state_before, self.state, "continue_both", "Resultado detectado; continuar nas duas instancias.")
        if self.state is BotState.CONTINUE_BOTH:
            self.state = BotState.WAIT_NEXT_MATCH
            return StepResult(state_before, self.state, None, "Continuar concluido; aguardar proxima partida.")
        if self.state is BotState.WAIT_NEXT_MATCH:
            return StepResult(state_before, self.state, None, "Aguardando nova preparacao.")

        self.state = BotState.ERROR
        return StepResult(state_before, self.state, None, "Estado desconhecido.")

    def _battle_step(self, state_before: BotState, observation: MatchObservation, first_turn: bool) -> StepResult:
        side = self._active_side(observation)
        if side is None:
            message = "Aguardando primeiro turno." if first_turn else "Aguardando turno conhecido."
            return StepResult(state_before, self.state, None, message)
        if self.call_index >= len(self.call_sequence):
            self.state = BotState.ERROR
            return StepResult(state_before, self.state, None, "Sequencia de chamadas esgotada.")

        number = self.call_sequence[self.call_index]
        self.call_index += 1
        self.state = BotState.BATTLE
        return StepResult(
            state_before,
            self.state,
            f"call_{side.value}_{number}",
            f"Chamar numero {number} na instancia {side.value}.",
        )

    def layout_for(self, side: PlayerSide) -> list[list[int]]:
        return layout_for_side(side, self.winner_side, self.winner_layout, self.loser_layout)

    @staticmethod
    def _active_side(observation: MatchObservation) -> PlayerSide | None:
        if observation.left.turn_state is TurnState.MY_TURN and observation.right.turn_state is not TurnState.MY_TURN:
            return PlayerSide.LEFT
        if observation.right.turn_state is TurnState.MY_TURN and observation.left.turn_state is not TurnState.MY_TURN:
            return PlayerSide.RIGHT
        return None

    @staticmethod
    def _any_result_visible(observation: MatchObservation) -> bool:
        return observation.left.result_state in VISIBLE_RESULTS or observation.right.result_state in VISIBLE_RESULTS


def empty_observation() -> MatchObservation:
    return MatchObservation(left=PlayerObservation(), right=PlayerObservation())
