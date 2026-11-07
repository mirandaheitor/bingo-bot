from __future__ import annotations

import ctypes
import time
from dataclasses import dataclass

import config
from models import PlayerCalibration, Point, Region


WM_MOUSEMOVE = 0x0200
WM_SETCURSOR = 0x0020
WM_MOUSEACTIVATE = 0x0021
WM_NCHITTEST = 0x0084
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
HTCLIENT = 1
MK_LBUTTON = 0x0001
MK_RBUTTON = 0x0002
SW_RESTORE = 9


class WindowMessageError(RuntimeError):
    pass


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class WinPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


@dataclass(frozen=True)
class WindowCandidate:
    hwnd: int
    title: str
    region: Region

    @property
    def area(self) -> int:
        return self.region.width * self.region.height


@dataclass(frozen=True)
class WindowMessageClickResult:
    target: WindowCandidate
    client_point: Point
    method: str


def make_lparam(x: int, y: int) -> int:
    return (y & 0xFFFF) << 16 | (x & 0xFFFF)


def region_center(region: Region) -> Point:
    return Point(x=region.x + region.width // 2, y=region.y + region.height // 2)


def contains_point(region: Region, point: Point) -> bool:
    return region.x <= point.x < region.x + region.width and region.y <= point.y < region.y + region.height


def overlap_area(first: Region, second: Region) -> int:
    left = max(first.x, second.x)
    top = max(first.y, second.y)
    right = min(first.x + first.width, second.x + second.width)
    bottom = min(first.y + first.height, second.y + second.height)
    if right <= left or bottom <= top:
        return 0
    return (right - left) * (bottom - top)


def choose_window_for_region(calibrated_region: Region, candidates: list[WindowCandidate]) -> WindowCandidate:
    center = region_center(calibrated_region)
    valid = [
        candidate
        for candidate in candidates
        if contains_point(candidate.region, center) or overlap_area(candidate.region, calibrated_region) > 0
    ]
    if not valid:
        raise WindowMessageError("Nenhuma janela encontrada para a regiao calibrada.")
    return sorted(
        valid,
        key=lambda candidate: (
            0 if contains_point(candidate.region, center) else 1,
            candidate.area,
            -overlap_area(candidate.region, calibrated_region),
        ),
    )[0]


def enum_visible_windows() -> list[WindowCandidate]:
    user32 = ctypes.windll.user32
    candidates: list[WindowCandidate] = []

    enum_proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        rect = RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True
        width = int(rect.right - rect.left)
        height = int(rect.bottom - rect.top)
        if width <= 0 or height <= 0:
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value
        candidates.append(
            WindowCandidate(
                hwnd=int(hwnd),
                title=title,
                region=Region(x=int(rect.left), y=int(rect.top), width=width, height=height),
            )
        )
        return True

    user32.EnumWindows(enum_proc_type(callback), 0)
    return candidates


def find_hwnd_for_region(region: Region) -> WindowCandidate:
    return choose_window_for_region(region, enum_visible_windows())


def activate_window_for_region(region: Region) -> WindowCandidate:
    user32 = ctypes.windll.user32
    candidate = find_hwnd_for_region(region)
    hwnd = ctypes.c_void_p(candidate.hwnd)
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    user32.SetActiveWindow(hwnd)
    user32.SetFocus(hwnd)
    return candidate


def window_from_screen_point(point: Point) -> WindowCandidate:
    user32 = ctypes.windll.user32
    hwnd = int(user32.WindowFromPoint(WinPoint(x=point.x, y=point.y)))
    if not hwnd:
        raise WindowMessageError("WindowFromPoint nao encontrou uma janela no ponto alvo.")
    rect = RECT()
    if not user32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(rect)):
        raise WindowMessageError("GetWindowRect falhou para o hwnd alvo.")
    length = user32.GetWindowTextLengthW(ctypes.c_void_p(hwnd))
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(ctypes.c_void_p(hwnd), buffer, length + 1)
    return WindowCandidate(
        hwnd=hwnd,
        title=buffer.value,
        region=Region(
            x=int(rect.left),
            y=int(rect.top),
            width=int(rect.right - rect.left),
            height=int(rect.bottom - rect.top),
        ),
    )


def screen_to_client(hwnd: int, point: Point) -> Point:
    user32 = ctypes.windll.user32
    client_point = WinPoint(x=point.x, y=point.y)
    if not user32.ScreenToClient(ctypes.c_void_p(hwnd), ctypes.byref(client_point)):
        raise WindowMessageError("ScreenToClient falhou.")
    return Point(x=int(client_point.x), y=int(client_point.y))


def _button_messages(button: str) -> tuple[int, int, int]:
    if button == "left":
        return WM_LBUTTONDOWN, WM_LBUTTONUP, MK_LBUTTON
    if button == "right":
        return WM_RBUTTONDOWN, WM_RBUTTONUP, MK_RBUTTON
    raise WindowMessageError(f"Botao nao suportado: {button}")


def post_mouse_click(hwnd: int, client_point: Point, button: str = "left", hold_seconds: float | None = None) -> None:
    user32 = ctypes.windll.user32
    down_message, up_message, key_state = _button_messages(button)
    lparam = make_lparam(client_point.x, client_point.y)
    user32.PostMessageW(ctypes.c_void_p(hwnd), WM_MOUSEMOVE, 0, lparam)
    user32.PostMessageW(ctypes.c_void_p(hwnd), down_message, key_state, lparam)
    time.sleep(config.CLICK_HOLD if hold_seconds is None else hold_seconds)
    user32.PostMessageW(ctypes.c_void_p(hwnd), up_message, 0, lparam)


def post_hover_click(hwnd: int, screen_point: Point, client_point: Point, button: str = "left") -> None:
    user32 = ctypes.windll.user32
    down_message, up_message, key_state = _button_messages(button)
    client_lparam = make_lparam(client_point.x, client_point.y)
    screen_lparam = make_lparam(screen_point.x, screen_point.y)
    setcursor_lparam = (WM_MOUSEMOVE << 16) | HTCLIENT

    user32.PostMessageW(ctypes.c_void_p(hwnd), WM_NCHITTEST, 0, screen_lparam)
    user32.PostMessageW(ctypes.c_void_p(hwnd), WM_SETCURSOR, ctypes.c_void_p(hwnd), setcursor_lparam)
    user32.PostMessageW(ctypes.c_void_p(hwnd), WM_MOUSEACTIVATE, ctypes.c_void_p(hwnd), 0)
    _post_mouse_moves(user32, hwnd, client_point)
    user32.PostMessageW(ctypes.c_void_p(hwnd), down_message, key_state, client_lparam)
    time.sleep(config.CLICK_HOLD)
    user32.PostMessageW(ctypes.c_void_p(hwnd), up_message, 0, client_lparam)


def send_mouse_click(hwnd: int, client_point: Point, button: str = "left", hold_seconds: float | None = None) -> None:
    user32 = ctypes.windll.user32
    down_message, up_message, key_state = _button_messages(button)
    lparam = make_lparam(client_point.x, client_point.y)
    user32.SendMessageW(ctypes.c_void_p(hwnd), WM_MOUSEMOVE, 0, lparam)
    user32.SendMessageW(ctypes.c_void_p(hwnd), down_message, key_state, lparam)
    time.sleep(config.CLICK_HOLD if hold_seconds is None else hold_seconds)
    user32.SendMessageW(ctypes.c_void_p(hwnd), up_message, 0, lparam)


def send_hover_click(hwnd: int, screen_point: Point, client_point: Point, button: str = "left") -> None:
    user32 = ctypes.windll.user32
    down_message, up_message, key_state = _button_messages(button)
    client_lparam = make_lparam(client_point.x, client_point.y)
    screen_lparam = make_lparam(screen_point.x, screen_point.y)
    setcursor_lparam = (WM_MOUSEMOVE << 16) | HTCLIENT

    user32.SendMessageW(ctypes.c_void_p(hwnd), WM_NCHITTEST, 0, screen_lparam)
    user32.SendMessageW(ctypes.c_void_p(hwnd), WM_SETCURSOR, ctypes.c_void_p(hwnd), setcursor_lparam)
    user32.SendMessageW(ctypes.c_void_p(hwnd), WM_MOUSEACTIVATE, ctypes.c_void_p(hwnd), 0)
    _send_mouse_moves(user32, hwnd, client_point)
    user32.SendMessageW(ctypes.c_void_p(hwnd), down_message, key_state, client_lparam)
    time.sleep(config.CLICK_HOLD)
    user32.SendMessageW(ctypes.c_void_p(hwnd), up_message, 0, client_lparam)


def _move_points(point: Point) -> list[Point]:
    return [
        Point(x=max(0, point.x - 2), y=point.y),
        Point(x=point.x, y=max(0, point.y - 2)),
        point,
        point,
    ]


def _post_mouse_moves(user32, hwnd: int, point: Point) -> None:
    for move_point in _move_points(point):
        user32.PostMessageW(ctypes.c_void_p(hwnd), WM_MOUSEMOVE, 0, make_lparam(move_point.x, move_point.y))
        time.sleep(0.01)


def _send_mouse_moves(user32, hwnd: int, point: Point) -> None:
    for move_point in _move_points(point):
        user32.SendMessageW(ctypes.c_void_p(hwnd), WM_MOUSEMOVE, 0, make_lparam(move_point.x, move_point.y))
        time.sleep(0.01)


def post_click_absolute(calibration: PlayerCalibration, point: Point, button: str = "left") -> WindowMessageClickResult:
    candidate = find_hwnd_for_region(calibration.window_region)
    client_point = screen_to_client(candidate.hwnd, point)
    post_mouse_click(candidate.hwnd, client_point, button=button)
    return WindowMessageClickResult(target=candidate, client_point=client_point, method="post_top_window")


def message_click_at_point(point: Point, button: str = "left", method: str = "post_child") -> WindowMessageClickResult:
    candidate = window_from_screen_point(point)
    client_point = screen_to_client(candidate.hwnd, point)
    if method == "post_child":
        post_mouse_click(candidate.hwnd, client_point, button=button)
    elif method == "send_child":
        send_mouse_click(candidate.hwnd, client_point, button=button)
    elif method == "post_hover_child":
        post_hover_click(candidate.hwnd, point, client_point, button=button)
    elif method == "send_hover_child":
        send_hover_click(candidate.hwnd, point, client_point, button=button)
    else:
        raise WindowMessageError(f"Metodo nao suportado: {method}")
    return WindowMessageClickResult(target=candidate, client_point=client_point, method=method)
