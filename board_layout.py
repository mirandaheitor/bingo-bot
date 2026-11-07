from __future__ import annotations

from collections.abc import Sequence

from models import Cell, PlayerRole, PlayerSide, Point, Region


BOARD_SIZE = 5
BOARD_NUMBERS = set(range(1, BOARD_SIZE * BOARD_SIZE + 1))
Layout = list[list[int]]


class LayoutError(ValueError):
    pass


def validate_layout(layout: Sequence[Sequence[int]]) -> None:
    if len(layout) != BOARD_SIZE:
        raise LayoutError("Layout deve ter 5 linhas.")
    numbers: list[int] = []
    for row_index, row in enumerate(layout):
        if len(row) != BOARD_SIZE:
            raise LayoutError(f"Linha {row_index} deve ter 5 colunas.")
        numbers.extend(row)
    if set(numbers) != BOARD_NUMBERS:
        raise LayoutError("Layout deve conter todos os numeros de 1 a 25 sem repeticao.")
    if len(numbers) != len(set(numbers)):
        raise LayoutError("Layout contem numeros repetidos.")


def number_to_cell(layout: Sequence[Sequence[int]], number: int) -> Cell:
    validate_layout(layout)
    for row_index, row in enumerate(layout):
        for col_index, value in enumerate(row):
            if value == number:
                return Cell(row=row_index, col=col_index)
    raise LayoutError(f"Numero fora do layout: {number}")


def number_to_cell_map(layout: Sequence[Sequence[int]]) -> dict[int, Cell]:
    validate_layout(layout)
    return {value: Cell(row=row_index, col=col_index) for row_index, row in enumerate(layout) for col_index, value in enumerate(row)}


def cell_center(grid_region: Region, cell: Cell) -> Point:
    if cell.row < 0 or cell.row >= BOARD_SIZE or cell.col < 0 or cell.col >= BOARD_SIZE:
        raise LayoutError(f"Celula fora da grade: {cell}")
    cell_width = grid_region.width / BOARD_SIZE
    cell_height = grid_region.height / BOARD_SIZE
    return Point(
        x=grid_region.x + int(round((cell.col + 0.5) * cell_width)),
        y=grid_region.y + int(round((cell.row + 0.5) * cell_height)),
    )


def layout_for_side(
    side: PlayerSide,
    winner_side: PlayerSide,
    winner_layout: Sequence[Sequence[int]],
    loser_layout: Sequence[Sequence[int]],
) -> list[list[int]]:
    validate_layout(winner_layout)
    validate_layout(loser_layout)
    source = winner_layout if side is winner_side else loser_layout
    return [list(row) for row in source]


def role_for_side(side: PlayerSide, winner_side: PlayerSide) -> PlayerRole:
    return PlayerRole.WINNER if side is winner_side else PlayerRole.LOSER


def winning_lines() -> list[list[Cell]]:
    rows = [[Cell(row=row, col=col) for col in range(BOARD_SIZE)] for row in range(BOARD_SIZE)]
    cols = [[Cell(row=row, col=col) for row in range(BOARD_SIZE)] for col in range(BOARD_SIZE)]
    diagonals = [
        [Cell(row=index, col=index) for index in range(BOARD_SIZE)],
        [Cell(row=index, col=BOARD_SIZE - 1 - index) for index in range(BOARD_SIZE)],
    ]
    return rows + cols + diagonals


def completed_lines(layout: Sequence[Sequence[int]], called_numbers: set[int]) -> list[list[Cell]]:
    validate_layout(layout)
    completed: list[list[Cell]] = []
    for line in winning_lines():
        if all(layout[cell.row][cell.col] in called_numbers for cell in line):
            completed.append(line)
    return completed


def count_completed_lines(layout: Sequence[Sequence[int]], called_numbers: set[int]) -> int:
    return len(completed_lines(layout, called_numbers))


def format_layout(layout: Sequence[Sequence[int]]) -> str:
    validate_layout(layout)
    return "\n".join(" ".join(f"{value:2d}" for value in row) for row in layout)
