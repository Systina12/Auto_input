from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes
from dataclasses import dataclass
from typing import Callable


MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
PM_NOREMOVE = 0x0000

DEFAULT_HOTKEY = "`"

_ERROR_MESSAGES = {
    "zh": {
        "empty": "急停热键不能为空。",
        "multiple_keys": "急停热键只能包含一个普通按键。",
        "missing_key": "急停热键缺少普通按键。",
        "unsupported": "不支持的急停热键：{token}",
        "windows_only": "全局急停热键只支持 Windows。",
        "timeout": "急停热键监听启动超时。",
        "register_failed": "注册急停热键失败，可能已被其他程序占用。",
    },
    "en": {
        "empty": "Emergency hotkey cannot be empty.",
        "multiple_keys": "Emergency hotkey can contain only one non-modifier key.",
        "missing_key": "Emergency hotkey is missing a non-modifier key.",
        "unsupported": "Unsupported emergency hotkey: {token}",
        "windows_only": "The global emergency hotkey is only supported on Windows.",
        "timeout": "Emergency hotkey listener timed out while starting.",
        "register_failed": "Failed to register the emergency hotkey. It may already be used by another program.",
    },
}

_MODIFIER_ALIASES = {
    "alt": MOD_ALT,
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
    "windows": MOD_WIN,
}

_MODIFIER_NAMES = {
    MOD_CONTROL: "Ctrl",
    MOD_SHIFT: "Shift",
    MOD_ALT: "Alt",
    MOD_WIN: "Win",
}

_KEY_ALIASES = {
    "`": (0xC0, "`"),
    "~": (0xC0, "`"),
    "tilde": (0xC0, "`"),
    "backtick": (0xC0, "`"),
    "grave": (0xC0, "`"),
    "波浪号": (0xC0, "`"),
    "飘号": (0xC0, "`"),
    "反引号": (0xC0, "`"),
    "esc": (0x1B, "Esc"),
    "escape": (0x1B, "Esc"),
    "tab": (0x09, "Tab"),
    "enter": (0x0D, "Enter"),
    "return": (0x0D, "Enter"),
    "space": (0x20, "Space"),
    "backspace": (0x08, "Backspace"),
    "delete": (0x2E, "Delete"),
    "del": (0x2E, "Delete"),
    "insert": (0x2D, "Insert"),
    "ins": (0x2D, "Insert"),
    "home": (0x24, "Home"),
    "end": (0x23, "End"),
    "pageup": (0x21, "PageUp"),
    "pagedown": (0x22, "PageDown"),
    "up": (0x26, "Up"),
    "down": (0x28, "Down"),
    "left": (0x25, "Left"),
    "right": (0x27, "Right"),
    "-": (0xBD, "-"),
    "_": (0xBD, "-"),
    "=": (0xBB, "="),
    "+": (0xBB, "="),
    "[": (0xDB, "["),
    "{": (0xDB, "["),
    "]": (0xDD, "]"),
    "}": (0xDD, "]"),
    "\\": (0xDC, "\\"),
    "|": (0xDC, "\\"),
    ";": (0xBA, ";"),
    ":": (0xBA, ";"),
    "'": (0xDE, "'"),
    '"': (0xDE, "'"),
    ",": (0xBC, ","),
    "<": (0xBC, ","),
    ".": (0xBE, "."),
    ">": (0xBE, "."),
    "/": (0xBF, "/"),
    "?": (0xBF, "/"),
}


@dataclass(frozen=True)
class HotkeySpec:
    modifiers: int
    vk: int
    display: str


class HotkeyError(RuntimeError):
    pass


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


if hasattr(ctypes, "WinDLL"):
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    RegisterHotKey = _user32.RegisterHotKey
    RegisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT)
    RegisterHotKey.restype = wintypes.BOOL

    UnregisterHotKey = _user32.UnregisterHotKey
    UnregisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int)
    UnregisterHotKey.restype = wintypes.BOOL

    GetMessage = _user32.GetMessageW
    GetMessage.argtypes = (ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT)
    GetMessage.restype = wintypes.BOOL

    PeekMessage = _user32.PeekMessageW
    PeekMessage.argtypes = (ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT)
    PeekMessage.restype = wintypes.BOOL

    PostThreadMessage = _user32.PostThreadMessageW
    PostThreadMessage.argtypes = (wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    PostThreadMessage.restype = wintypes.BOOL

    GetCurrentThreadId = _kernel32.GetCurrentThreadId
    GetCurrentThreadId.argtypes = ()
    GetCurrentThreadId.restype = wintypes.DWORD
else:
    RegisterHotKey = None
    UnregisterHotKey = None
    GetMessage = None
    PeekMessage = None
    PostThreadMessage = None
    GetCurrentThreadId = None


def parse_hotkey(raw: str, language: str = "zh") -> HotkeySpec:
    normalized = raw.strip()
    if not normalized:
        raise HotkeyError(_message(language, "empty"))

    tokens = [token.strip() for token in normalized.replace("＋", "+").split("+") if token.strip()]
    modifiers = 0
    key: tuple[int, str] | None = None

    for token in tokens:
        lowered = token.lower()
        modifier = _MODIFIER_ALIASES.get(lowered)
        if modifier is not None:
            modifiers |= modifier
            continue
        if key is not None:
            raise HotkeyError(_message(language, "multiple_keys"))
        key = _parse_key(token, language)

    if key is None:
        raise HotkeyError(_message(language, "missing_key"))

    display = _format_display(modifiers, key[1])
    return HotkeySpec(modifiers=modifiers, vk=key[0], display=display)


def _parse_key(token: str, language: str) -> tuple[int, str]:
    lowered = token.lower()
    alias = _KEY_ALIASES.get(lowered)
    if alias is not None:
        return alias

    if lowered.startswith("f") and lowered[1:].isdigit():
        number = int(lowered[1:])
        if 1 <= number <= 24:
            return 0x70 + number - 1, f"F{number}"

    if len(token) == 1 and token.isascii() and token.isalnum():
        char = token.upper()
        return ord(char), char

    raise HotkeyError(_message(language, "unsupported", token=token))


def _format_display(modifiers: int, key_name: str) -> str:
    names = [name for mask, name in _MODIFIER_NAMES.items() if modifiers & mask]
    names.append(key_name)
    return "+".join(names)


class HotkeyListener:
    def __init__(self, callback: Callable[[], None]) -> None:
        self._callback = callback
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._lock = threading.Lock()
        self._hotkey_id = 1

    def start(self, spec: HotkeySpec, language: str = "zh") -> None:
        if RegisterHotKey is None:
            raise HotkeyError(_message(language, "windows_only"))

        self.stop()
        ready = threading.Event()
        error: list[BaseException] = []

        thread = threading.Thread(target=self._run, args=(spec, ready, error, language), daemon=True)
        with self._lock:
            self._thread = thread
            self._thread_id = None
        thread.start()

        if not ready.wait(2):
            self.stop()
            raise HotkeyError(_message(language, "timeout"))
        if error:
            with self._lock:
                self._thread = None
                self._thread_id = None
            raise HotkeyError(str(error[0])) from error[0]

    def stop(self) -> None:
        with self._lock:
            thread = self._thread
            thread_id = self._thread_id
            self._thread = None
            self._thread_id = None

        if thread is None:
            return

        if thread.is_alive() and thread_id and PostThreadMessage is not None:
            PostThreadMessage(thread_id, WM_QUIT, 0, 0)
            thread.join(timeout=1)

    def _run(self, spec: HotkeySpec, ready: threading.Event, error: list[BaseException], language: str) -> None:
        assert RegisterHotKey is not None
        assert UnregisterHotKey is not None
        assert GetMessage is not None
        assert PeekMessage is not None
        assert GetCurrentThreadId is not None

        thread_id = int(GetCurrentThreadId())
        with self._lock:
            self._thread_id = thread_id

        message = MSG()
        PeekMessage(ctypes.byref(message), None, 0, 0, PM_NOREMOVE)

        if not RegisterHotKey(None, self._hotkey_id, spec.modifiers | MOD_NOREPEAT, spec.vk):
            error.append(_last_error(_message(language, "register_failed")))
            ready.set()
            return

        ready.set()
        try:
            while GetMessage(ctypes.byref(message), None, 0, 0):
                if message.message == WM_HOTKEY and message.wParam == self._hotkey_id:
                    self._callback()
        finally:
            UnregisterHotKey(None, self._hotkey_id)


def _last_error(default_message: str) -> OSError:
    error = ctypes.get_last_error()
    return OSError(error, default_message)


def _message(language: str, key: str, **kwargs: object) -> str:
    messages = _ERROR_MESSAGES.get(language, _ERROR_MESSAGES["zh"])
    return messages[key].format(**kwargs)
