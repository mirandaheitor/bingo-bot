from __future__ import annotations

from dataclasses import dataclass

from board_layout import Layout, number_to_cell, validate_layout
from models import Cell, TurnState


class BattleError(ValueError):
    pass


@dataclass(frozen=True)
class BattleAction:
    number: int
    cell: Cell
    sequence_index: int
    reason: str


@dataclass
class BattleController:
    layout: Layout
    call_sequence: list[int]
    call_index: int = 0

    def __post_init__(self) -> None:
        validate_layout(self.layout)
        invalid = [number for number in self.call_sequence if number < 1 or number > 25]
        if invalid:
            raise BattleError(f"Sequencia contem numeros invalidos: {invalid}")

    def next_action(self, turn_state: TurnState) -> BattleAction | None:
        if turn_state is not TurnState.MY_TURN:
            return None
        if self.call_index >= len(self.call_sequence):
            raise BattleError("Sequencia de chamadas esgotada.")
        number = self.call_sequence[self.call_index]
        action = BattleAction(
            number=number,
            cell=number_to_cell(self.layout, number),
            sequence_index=self.call_index,
            reason="Numero da sequencia configurada.",
        )
        self.call_index += 1
        return action
