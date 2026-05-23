from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from dataclasses import dataclass
from random import Random
from threading import Event
from typing import Callable


DelayProvider = Callable[[], float]


INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_RETURN = 0x0D

INPUT_MODE_UNICODE = "unicode"
INPUT_MODE_KEYBOARD = "keyboard"
INPUT_MODES = (
    INPUT_MODE_UNICODE,
    INPUT_MODE_KEYBOARD,
)

NEWLINE_ENTER = "enter"
NEWLINE_SHIFT_ENTER = "shift_enter"
NEWLINE_CTRL_ENTER = "ctrl_enter"
NEWLINE_UNICODE = "unicode"
NEWLINE_MODES = (
    NEWLINE_ENTER,
    NEWLINE_SHIFT_ENTER,
    NEWLINE_CTRL_ENTER,
    NEWLINE_UNICODE,
)


ULONG_PTR = wintypes.WPARAM


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUTUNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


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


class UnsupportedKeyboardCharacter(ValueError):
    def __init__(self, char: str) -> None:
        self.char = char
        super().__init__(f"Unsupported keyboard-mode character: {char!r}")


@dataclass(frozen=True)
class KeyStroke:
    scan: int
    shift: bool = False


SCANCODE_SHIFT = 0x2A
SCANCODE_CONTROL = 0x1D
SCANCODE_ENTER = 0x1C

_VK_TO_SCANCODE = {
    VK_SHIFT: SCANCODE_SHIFT,
    VK_CONTROL: SCANCODE_CONTROL,
    VK_RETURN: SCANCODE_ENTER,
}

_LETTER_SCANCODES = {
    "a": 0x1E,
    "b": 0x30,
    "c": 0x2E,
    "d": 0x20,
    "e": 0x12,
    "f": 0x21,
    "g": 0x22,
    "h": 0x23,
    "i": 0x17,
    "j": 0x24,
    "k": 0x25,
    "l": 0x26,
    "m": 0x32,
    "n": 0x31,
    "o": 0x18,
    "p": 0x19,
    "q": 0x10,
    "r": 0x13,
    "s": 0x1F,
    "t": 0x14,
    "u": 0x16,
    "v": 0x2F,
    "w": 0x11,
    "x": 0x2D,
    "y": 0x15,
    "z": 0x2C,
}

_US_KEYSTROKES = {
    "1": KeyStroke(0x02),
    "2": KeyStroke(0x03),
    "3": KeyStroke(0x04),
    "4": KeyStroke(0x05),
    "5": KeyStroke(0x06),
    "6": KeyStroke(0x07),
    "7": KeyStroke(0x08),
    "8": KeyStroke(0x09),
    "9": KeyStroke(0x0A),
    "0": KeyStroke(0x0B),
    "!": KeyStroke(0x02, True),
    "@": KeyStroke(0x03, True),
    "#": KeyStroke(0x04, True),
    "$": KeyStroke(0x05, True),
    "%": KeyStroke(0x06, True),
    "^": KeyStroke(0x07, True),
    "&": KeyStroke(0x08, True),
    "*": KeyStroke(0x09, True),
    "(": KeyStroke(0x0A, True),
    ")": KeyStroke(0x0B, True),
    "-": KeyStroke(0x0C),
    "_": KeyStroke(0x0C, True),
    "=": KeyStroke(0x0D),
    "+": KeyStroke(0x0D, True),
    "\t": KeyStroke(0x0F),
    "[": KeyStroke(0x1A),
    "{": KeyStroke(0x1A, True),
    "]": KeyStroke(0x1B),
    "}": KeyStroke(0x1B, True),
    "\\": KeyStroke(0x2B),
    "|": KeyStroke(0x2B, True),
    ";": KeyStroke(0x27),
    ":": KeyStroke(0x27, True),
    "'": KeyStroke(0x28),
    '"': KeyStroke(0x28, True),
    "`": KeyStroke(0x29),
    "~": KeyStroke(0x29, True),
    ",": KeyStroke(0x33),
    "<": KeyStroke(0x33, True),
    ".": KeyStroke(0x34),
    ">": KeyStroke(0x34, True),
    "/": KeyStroke(0x35),
    "?": KeyStroke(0x35, True),
    " ": KeyStroke(0x39),
}


def fixed_delay(seconds: float) -> DelayProvider:
    seconds = max(0.0, seconds)
    return lambda: seconds


def random_delay(min_seconds: float, max_seconds: float, rng: Random | None = None) -> DelayProvider:
    rng = rng or Random()
    min_seconds = max(0.0, min_seconds)
    max_seconds = max(min_seconds, max_seconds)
    return lambda: rng.uniform(min_seconds, max_seconds)


def type_text(
    text: str,
    delay_provider: DelayProvider,
    cancel_event: Event,
    newline_mode: str = NEWLINE_ENTER,
    input_mode: str = INPUT_MODE_UNICODE,
) -> int:
    if newline_mode not in NEWLINE_MODES:
        raise ValueError(f"Unsupported newline mode: {newline_mode}")
    if input_mode not in INPUT_MODES:
        raise ValueError(f"Unsupported input mode: {input_mode}")

    typed = 0
    previous_was_cr = False

    for char in text:
        if cancel_event.is_set():
            raise InputCancelled

        if char == "\n" and previous_was_cr:
            previous_was_cr = False
            continue

        if char in ("\r", "\n"):
            _send_newline(newline_mode, input_mode)
            previous_was_cr = char == "\r"
        else:
            previous_was_cr = False
            _send_char(char, input_mode)

        typed += 1
        _sleep_interruptibly(delay_provider(), cancel_event)

    return typed


def find_unsupported_keyboard_char(text: str) -> str | None:
    for char in text:
        if char in ("\r", "\n"):
            continue
        if not _is_supported_keyboard_char(char):
            return char
    return None


def _send_char(char: str, input_mode: str) -> None:
    if input_mode == INPUT_MODE_UNICODE:
        _send_unicode_char(char)
    elif input_mode == INPUT_MODE_KEYBOARD:
        _send_keyboard_mode_char(char)
    else:
        raise ValueError(f"Unsupported input mode: {input_mode}")


def _send_unicode_char(char: str) -> None:
    for unit in _utf16_units(char):
        _send_keyboard_input(0, unit, KEYEVENTF_UNICODE)
        _send_keyboard_input(0, unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)


def _send_keyboard_mode_char(char: str) -> None:
    keystroke = _keyboard_keystroke(char)
    if keystroke.shift:
        _send_key_down(VK_SHIFT, INPUT_MODE_KEYBOARD)
    try:
        _press_scancode(keystroke.scan)
    finally:
        if keystroke.shift:
            _send_key_up(VK_SHIFT, INPUT_MODE_KEYBOARD)


def _send_newline(newline_mode: str, input_mode: str) -> None:
    if newline_mode == NEWLINE_ENTER:
        _press_enter(input_mode)
    elif newline_mode == NEWLINE_SHIFT_ENTER:
        _press_modified_enter(VK_SHIFT, input_mode)
    elif newline_mode == NEWLINE_CTRL_ENTER:
        _press_modified_enter(VK_CONTROL, input_mode)
    elif newline_mode == NEWLINE_UNICODE:
        if input_mode != INPUT_MODE_UNICODE:
            raise ValueError("Unicode newline is not supported in keyboard input mode")
        _send_unicode_char("\n")
    else:
        raise ValueError(f"Unsupported newline mode: {newline_mode}")


def _press_enter(input_mode: str = INPUT_MODE_UNICODE) -> None:
    _press_key(VK_RETURN, input_mode)


def _press_key(vk: int, input_mode: str = INPUT_MODE_UNICODE) -> None:
    _send_key_down(vk, input_mode)
    _send_key_up(vk, input_mode)


def _press_scancode(scan: int) -> None:
    _send_keyboard_input(0, scan, KEYEVENTF_SCANCODE)
    _send_keyboard_input(0, scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP)


def _press_modified_enter(modifier_vk: int, input_mode: str = INPUT_MODE_UNICODE) -> None:
    _send_key_down(modifier_vk, input_mode)
    try:
        _press_enter(input_mode)
    finally:
        _send_key_up(modifier_vk, input_mode)


def _send_key_down(vk: int, input_mode: str) -> None:
    _send_key_event(vk, input_mode, key_up=False)


def _send_key_up(vk: int, input_mode: str) -> None:
    _send_key_event(vk, input_mode, key_up=True)


def _send_key_event(vk: int, input_mode: str, key_up: bool) -> None:
    if input_mode == INPUT_MODE_KEYBOARD and vk in _VK_TO_SCANCODE:
        flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if key_up else 0)
        _send_keyboard_input(0, _VK_TO_SCANCODE[vk], flags)
        return

    flags = KEYEVENTF_KEYUP if key_up else 0
    _send_keyboard_input(vk, 0, flags)


def _keyboard_keystroke(char: str) -> KeyStroke:
    lowered = char.lower()
    if len(char) == 1 and char.isascii() and lowered in _LETTER_SCANCODES:
        return KeyStroke(_LETTER_SCANCODES[lowered], char.isupper())

    keystroke = _US_KEYSTROKES.get(char)
    if keystroke is None:
        raise UnsupportedKeyboardCharacter(char)
    return keystroke


def _is_supported_keyboard_char(char: str) -> bool:
    lowered = char.lower()
    return (len(char) == 1 and char.isascii() and lowered in _LETTER_SCANCODES) or char in _US_KEYSTROKES


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
