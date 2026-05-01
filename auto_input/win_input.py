from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from random import Random
from threading import Event
from typing import Callable


DelayProvider = Callable[[], float]


INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_RETURN = 0x0D


ULONG_PTR = wintypes.WPARAM


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", INPUTUNION),
    ]


if hasattr(ctypes, "WinDLL"):
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    SendInput = _user32.SendInput
    SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    SendInput.restype = wintypes.UINT
else:
    SendInput = None


class InputCancelled(Exception):
    """Raised when an input operation is cancelled."""


def fixed_delay(seconds: float) -> DelayProvider:
    seconds = max(0.0, seconds)
    return lambda: seconds


def random_delay(min_seconds: float, max_seconds: float, rng: Random | None = None) -> DelayProvider:
    rng = rng or Random()
    min_seconds = max(0.0, min_seconds)
    max_seconds = max(min_seconds, max_seconds)
    return lambda: rng.uniform(min_seconds, max_seconds)


def type_text(text: str, delay_provider: DelayProvider, cancel_event: Event) -> int:
    typed = 0
    previous_was_cr = False

    for char in text:
        if cancel_event.is_set():
            raise InputCancelled

        if char == "\n" and previous_was_cr:
            previous_was_cr = False
            continue

        if char in ("\r", "\n"):
            _press_enter()
            previous_was_cr = char == "\r"
        else:
            previous_was_cr = False
            _send_unicode_char(char)

        typed += 1
        _sleep_interruptibly(delay_provider(), cancel_event)

    return typed


def _send_unicode_char(char: str) -> None:
    for unit in _utf16_units(char):
        _send_keyboard_input(0, unit, KEYEVENTF_UNICODE)
        _send_keyboard_input(0, unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)


def _press_enter() -> None:
    _send_keyboard_input(VK_RETURN, 0, 0)
    _send_keyboard_input(VK_RETURN, 0, KEYEVENTF_KEYUP)


def _send_keyboard_input(vk: int, scan: int, flags: int) -> None:
    if SendInput is None:
        raise RuntimeError("SendInput is only available on Windows.")

    event = INPUT(
        type=INPUT_KEYBOARD,
        union=INPUTUNION(
            ki=KEYBDINPUT(
                wVk=vk,
                wScan=scan,
                dwFlags=flags,
                time=0,
                dwExtraInfo=0,
            )
        ),
    )
    sent = SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT))
    if sent != 1:
        error = ctypes.get_last_error()
        if hasattr(ctypes, "WinError"):
            raise ctypes.WinError(error)
        raise OSError(error, "SendInput failed")


def _utf16_units(char: str) -> list[int]:
    data = char.encode("utf-16-le", "surrogatepass")
    return [data[index] | (data[index + 1] << 8) for index in range(0, len(data), 2)]


def _sleep_interruptibly(seconds: float, cancel_event: Event) -> None:
    if seconds <= 0:
        return
    if cancel_event.wait(seconds):
        raise InputCancelled
