from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import config
from board_layout import Layout, number_to_cell, validate_layout
from models import Cell


class SetupAction(Enum):
    PLACE_NUMBER = "place_number"
    RETRY_NUMBER = "retry_number"
    UNDO_AND_RESTART = "undo_and_restart"
    CONFIRM = "confirm"
    WAIT = "wait"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class SetupStep:
    action: SetupAction
    expected_number: int
    detected_number: int | None
    cell: Cell | None = None
    reason: str = ""


@dataclass
class SetupController:
    layout: Layout
    max_retries: int = config.MAX_SETUP_RETRIES
    max_stale_waits: int = config.MAX_STALE_NUMBER_WAITS
    expected_number: int = 1
    retries: int = 0
    stale_waits: int = 0
    completed: bool = False

    def __post_init__(self) -> None:
        validate_layout(self.layout)

    def step(self, detected_number: int | None) -> SetupStep:
        if self.completed:
            return SetupStep(SetupAction.CONFIRM, self.expected_number, detected_number, reason="Cartela completa.")

        if detected_number is None:
            return SetupStep(SetupAction.WAIT, self.expected_number, detected_number, reason="Numero desconhecido.")

        if detected_number < self.expected_number:
            if detected_number == self.expected_number - 1:
                if self.stale_waits < self.max_stale_waits:
                    self.stale_waits += 1
                    return SetupStep(
                        SetupAction.WAIT,
                        self.expected_number,
                        detected_number,
                        reason="Numero anterior detectado; aguardar atualizacao.",
                    )
                self.stale_waits = 0
                return SetupStep(
                    SetupAction.RETRY_NUMBER,
                    self.expected_number,
                    detected_number,
                    cell=number_to_cell(self.layout, detected_number),
                    reason="Numero anterior persistente; repetir clique.",
                )
            return SetupStep(
                SetupAction.WAIT,
                self.expected_number,
                detected_number,
                reason="Numero antigo detectado; aguardar nova leitura.",
            )

        if detected_number != self.expected_number:
            self.stale_waits = 0
            self.retries += 1
            self.expected_number = 1
            if self.retries >= self.max_retries:
                return SetupStep(SetupAction.BLOCKED, self.expected_number, detected_number, reason="Limite de retries excedido.")
            return SetupStep(
                SetupAction.UNDO_AND_RESTART,
                self.expected_number,
                detected_number,
                reason="Numero pulado detectado; reiniciar montagem.",
            )

        self.stale_waits = 0
        cell = number_to_cell(self.layout, detected_number)
        self.expected_number += 1
        if self.expected_number > 25:
            self.completed = True
        return SetupStep(SetupAction.PLACE_NUMBER, self.expected_number - 1, detected_number, cell=cell, reason="Numero esperado.")
