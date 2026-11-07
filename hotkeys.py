from __future__ import annotations

import ctypes


class BotCancelledError(RuntimeError):
    pass


VK_ESCAPE = 0x1B


def is_escape_pressed() -> bool:
    try:
        return bool(ctypes.windll.user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000)
    except AttributeError:
        return False


def raise_if_escape_pressed() -> None:
    if is_escape_pressed():
        raise BotCancelledError("Interrompido por ESC.")
