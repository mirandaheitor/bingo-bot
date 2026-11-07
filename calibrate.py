from __future__ import annotations

import ctypes
import json
from dataclasses import asdict
from dataclasses import replace
from pathlib import Path
import tkinter as tk
from typing import Any

from capture import CapturedImage, capture_region, capture_virtual_screen
from models import PlayerCalibration, PlayerSide, Point, Region


CALIBRATION_DIR = Path("calibration")
CALIBRATION_VERSION = 1


class CalibrationError(ValueError):
    pass


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def calibration_path(side: PlayerSide) -> Path:
    return CALIBRATION_DIR / f"player_{side.value}.json"


def get_cursor_position() -> Point:
    point = POINT()
    if not ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
        raise CalibrationError("Nao foi possivel ler a posicao do mouse.")
    return Point(x=int(point.x), y=int(point.y))


def wait_for_cursor(label: str) -> Point:
    input(f"{label}. Posicione o mouse e pressione Enter...")
    point = get_cursor_position()
    print(f"Capturado: ({point.x}, {point.y})")
    return point


def make_region(first: Point, second: Point) -> Region:
    x1 = min(first.x, second.x)
    y1 = min(first.y, second.y)
    x2 = max(first.x, second.x)
    y2 = max(first.y, second.y)
    width = x2 - x1
    height = y2 - y1
    if width <= 0 or height <= 0:
        raise CalibrationError("Regiao invalida: largura e altura precisam ser maiores que zero.")
    return Region(x=x1, y=y1, width=width, height=height)


def wait_for_region(label: str) -> Region:
    print(f"\n{label}")
    top_left = wait_for_cursor("Canto superior esquerdo")
    bottom_right = wait_for_cursor("Canto inferior direito")
    region = make_region(top_left, bottom_right)
    print(f"Regiao: x={region.x}, y={region.y}, w={region.width}, h={region.height}")
    return region


def region_to_relative(region: Region, window_region: Region) -> Region:
    return Region(
        x=region.x - window_region.x,
        y=region.y - window_region.y,
        width=region.width,
        height=region.height,
    )


def region_to_absolute(region: Region, window_region: Region) -> Region:
    return Region(
        x=window_region.x + region.x,
        y=window_region.y + region.y,
        width=region.width,
        height=region.height,
    )


def point_to_relative(point: Point, window_region: Region) -> Point:
    return Point(x=point.x - window_region.x, y=point.y - window_region.y)


def point_to_absolute(point: Point, window_region: Region) -> Point:
    return Point(x=window_region.x + point.x, y=window_region.y + point.y)


def _region_from_dict(data: dict[str, Any]) -> Region:
    return Region(x=int(data["x"]), y=int(data["y"]), width=int(data["width"]), height=int(data["height"]))


def _point_from_dict(data: dict[str, Any]) -> Point:
    return Point(x=int(data["x"]), y=int(data["y"]))


def calibration_to_file_data(calibration: PlayerCalibration) -> dict[str, Any]:
    window = calibration.window_region
    return {
        "version": CALIBRATION_VERSION,
        "side": calibration.side.value,
        "name": calibration.name,
        "coordinate_mode": "relative_to_window",
        "window_region": asdict(window),
        "regions": {
            "grid_region": asdict(region_to_relative(calibration.grid_region, window)),
            "setup_number_region": asdict(region_to_relative(calibration.setup_number_region, window)),
            "setup_text_region": asdict(region_to_relative(calibration.setup_text_region, window)),
            "turn_region": asdict(region_to_relative(calibration.turn_region, window)),
            "result_region": asdict(region_to_relative(calibration.result_region, window)),
        },
        "points": {
            "ready_button": asdict(point_to_relative(calibration.ready_button, window)),
            "undo_button": asdict(point_to_relative(calibration.undo_button, window)),
            "clear_button": asdict(point_to_relative(calibration.clear_button, window)),
            "confirm_button": asdict(point_to_relative(calibration.confirm_button, window)),
            "continue_button": asdict(point_to_relative(calibration.continue_button, window)),
        },
    }


def calibration_from_file_data(data: dict[str, Any]) -> PlayerCalibration:
    if data.get("coordinate_mode") != "relative_to_window":
        raise CalibrationError("Modo de coordenadas nao suportado na calibracao.")
    window = _region_from_dict(data["window_region"])
    regions = data["regions"]
    points = data["points"]
    return PlayerCalibration(
        side=PlayerSide(data["side"]),
        name=str(data.get("name", "")),
        window_region=window,
        grid_region=region_to_absolute(_region_from_dict(regions["grid_region"]), window),
        setup_number_region=region_to_absolute(_region_from_dict(regions["setup_number_region"]), window),
        setup_text_region=region_to_absolute(_region_from_dict(regions["setup_text_region"]), window),
        turn_region=region_to_absolute(_region_from_dict(regions["turn_region"]), window),
        result_region=region_to_absolute(_region_from_dict(regions["result_region"]), window),
        ready_button=point_to_absolute(_point_from_dict(points["ready_button"]), window),
        undo_button=point_to_absolute(_point_from_dict(points["undo_button"]), window),
        clear_button=point_to_absolute(_point_from_dict(points["clear_button"]), window),
        confirm_button=point_to_absolute(_point_from_dict(points["confirm_button"]), window),
        continue_button=point_to_absolute(_point_from_dict(points["continue_button"]), window),
    )


def save_calibration(calibration: PlayerCalibration, path: Path | None = None) -> Path:
    target = path or calibration_path(calibration.side)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(calibration_to_file_data(calibration), indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    return target


def load_calibration(side: PlayerSide, path: Path | None = None) -> PlayerCalibration:
    source = path or calibration_path(side)
    if not source.exists():
        raise CalibrationError(f"Calibracao nao encontrada: {source}")
    return calibration_from_file_data(json.loads(source.read_text(encoding="utf-8")))


def calibrate_side(side: PlayerSide) -> PlayerCalibration:
    print(f"\n=== Calibracao {side.value} ===")
    print("Nenhum clique real sera executado. O bot usa uma imagem da tela para recortar regioes.")
    print("Nao mova nem redimensione as janelas durante esta etapa.")
    print("Em cada janela de selecao: arraste para regioes, clique para pontos, Enter confirma, ESC cancela.")
    name = input("Nome opcional desta instancia: ").strip()

    desktop = capture_virtual_screen()
    window_region = select_region(
        desktop,
        "Arraste a janela inteira do mini-game Bingo",
        relative_to_capture=False,
    )
    window_capture = capture_region(window_region)
    grid_region = select_region(window_capture, "Arraste a grade 5x5", relative_to_capture=False)
    setup_number_region = select_region(
        window_capture,
        "Arraste a regiao do numero grande de preparacao",
        relative_to_capture=False,
    )
    setup_text_region = select_region(
        window_capture,
        "Arraste a regiao do texto de preparacao",
        relative_to_capture=False,
    )
    turn_region = select_region(window_capture, "Arraste a regiao do texto de turno/rodape", relative_to_capture=False)
    result_region = select_region(
        window_capture,
        "Arraste a area onde o resultado aparecera, mesmo sem YOU WIN / YOU LOSE visivel",
        relative_to_capture=False,
    )
    undo_button = select_point(window_capture, "Clique no centro do botao Undo", relative_to_capture=False)
    clear_button = select_point(window_capture, "Clique no centro do botao Clear", relative_to_capture=False)
    confirm_button = select_point(
        window_capture,
        "Clique no centro do botao Confirm/Continue, o botao de confirmar no canto inferior direito",
        relative_to_capture=False,
    )
    ready_button = confirm_button
    continue_button = confirm_button
    return PlayerCalibration(
        side=side,
        name=name,
        window_region=window_region,
        grid_region=grid_region,
        setup_number_region=setup_number_region,
        setup_text_region=setup_text_region,
        turn_region=turn_region,
        result_region=result_region,
        ready_button=ready_button,
        undo_button=undo_button,
        clear_button=clear_button,
        confirm_button=confirm_button,
        continue_button=continue_button,
    )


def run_calibration(side: PlayerSide) -> Path:
    calibration = calibrate_side(side)
    path = save_calibration(calibration)
    print(f"Calibracao salva em: {path}")
    return path


def recalibrate_continue_button(side: PlayerSide) -> Path:
    calibration = load_calibration(side)
    print(f"\n=== Recalibrar Continue/OK {side.value} ===")
    print("Deixe essa instancia na tela final, com o botao Continue/OK visivel.")
    input("Pressione Enter para capturar a janela calibrada...")
    window_capture = capture_region(calibration.window_region)
    continue_button = select_point(
        window_capture,
        "Clique no centro do botao Continue/OK da tela final",
        relative_to_capture=False,
    )
    updated = replace(calibration, continue_button=continue_button)
    path = save_calibration(updated)
    print(f"Continue/OK atualizado em: {path}")
    print(f"Novo ponto absoluto: ({continue_button.x}, {continue_button.y})")
    return path


class _SelectionCancelled(Exception):
    pass


class _ImageSelector:
    max_display_width = 1400
    max_display_height = 900

    def __init__(self, captured: CapturedImage, title: str):
        self.captured = captured
        self.title = title
        self.scale = min(
            1.0,
            self.max_display_width / captured.image.width,
            self.max_display_height / captured.image.height,
        )
        self.display_width = max(1, int(captured.image.width * self.scale))
        self.display_height = max(1, int(captured.image.height * self.scale))
        self.start: tuple[int, int] | None = None
        self.result: Region | Point | None = None
        self.rect_id: int | None = None

        self.root = tk.Tk()
        self.root.title(title)
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)

        from PIL import ImageTk

        self.image = captured.image.resize((self.display_width, self.display_height))
        self.photo = ImageTk.PhotoImage(self.image, master=self.root)

        header = tk.Label(
            self.root,
            text=f"{title} | Enter confirma, ESC cancela",
            anchor="w",
            padx=8,
            pady=6,
        )
        header.pack(fill="x")
        self.canvas = tk.Canvas(self.root, width=self.display_width, height=self.display_height, cursor="crosshair")
        self.canvas.pack()
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")

        self.root.bind("<Escape>", self._cancel)
        self.root.bind("<Return>", self._confirm)

    def select_region(self) -> Region:
        self.canvas.bind("<ButtonPress-1>", self._start_region)
        self.canvas.bind("<B1-Motion>", self._drag_region)
        self.canvas.bind("<ButtonRelease-1>", self._finish_region)
        self.root.mainloop()
        if self.result is None:
            raise _SelectionCancelled("Selecao cancelada.")
        if not isinstance(self.result, Region):
            raise CalibrationError("Selecao invalida.")
        return self.result

    def select_point(self) -> Point:
        self.canvas.bind("<ButtonPress-1>", self._finish_point)
        self.root.mainloop()
        if self.result is None:
            raise _SelectionCancelled("Selecao cancelada.")
        if not isinstance(self.result, Point):
            raise CalibrationError("Selecao invalida.")
        return self.result

    def _start_region(self, event) -> None:
        self.start = (event.x, event.y)
        if self.rect_id is not None:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="red", width=2)

    def _drag_region(self, event) -> None:
        if self.start is None or self.rect_id is None:
            return
        self.canvas.coords(self.rect_id, self.start[0], self.start[1], event.x, event.y)

    def _finish_region(self, event) -> None:
        if self.start is None:
            return
        x1, y1 = self.start
        x2, y2 = event.x, event.y
        left = self._to_image_coord(min(x1, x2))
        top = self._to_image_coord(min(y1, y2))
        right = self._to_image_coord(max(x1, x2))
        bottom = self._to_image_coord(max(y1, y2))
        self.result = Region(
            x=self.captured.region.x + left,
            y=self.captured.region.y + top,
            width=max(1, right - left),
            height=max(1, bottom - top),
        )

    def _finish_point(self, event) -> None:
        x = self._to_image_coord(event.x)
        y = self._to_image_coord(event.y)
        self.result = Point(x=self.captured.region.x + x, y=self.captured.region.y + y)
        marker = 5
        self.canvas.create_oval(
            event.x - marker,
            event.y - marker,
            event.x + marker,
            event.y + marker,
            outline="red",
            width=2,
        )

    def _to_image_coord(self, display_coord: int) -> int:
        return int(round(display_coord / self.scale))

    def _confirm(self, _event=None) -> None:
        if self.result is None:
            return
        self.root.quit()
        self.root.destroy()

    def _cancel(self, _event=None) -> None:
        self.result = None
        self.root.quit()
        self.root.destroy()


def select_region(captured: CapturedImage, title: str, relative_to_capture: bool = True) -> Region:
    try:
        selected = _ImageSelector(captured, title).select_region()
    except _SelectionCancelled as exc:
        raise CalibrationError("Calibracao cancelada pelo usuario.") from exc
    if not relative_to_capture:
        return selected
    return Region(
        x=selected.x - captured.region.x,
        y=selected.y - captured.region.y,
        width=selected.width,
        height=selected.height,
    )


def select_point(captured: CapturedImage, title: str, relative_to_capture: bool = True) -> Point:
    try:
        selected = _ImageSelector(captured, title).select_point()
    except _SelectionCancelled as exc:
        raise CalibrationError("Calibracao cancelada pelo usuario.") from exc
    if not relative_to_capture:
        return selected
    return Point(x=selected.x - captured.region.x, y=selected.y - captured.region.y)
