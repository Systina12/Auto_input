from __future__ import annotations

import unittest
from queue import Queue
from threading import Event
from unittest.mock import patch

from auto_input import hotkey
from auto_input.hotkey import DEFAULT_HOTKEY, MOD_CONTROL, MOD_SHIFT, HotkeyError, parse_hotkey


class HotkeyParsingTests(unittest.TestCase):
    def test_backtick_aliases(self) -> None:
        for raw in ("`", "~", "飘号", "波浪号", "反引号"):
            spec = parse_hotkey(raw)
            self.assertEqual(spec.vk, 0xC0)
            self.assertEqual(spec.modifiers, 0)
            self.assertEqual(spec.display, "`")

    def test_modifier_combo(self) -> None:
        spec = parse_hotkey("Ctrl+Shift+Q")

        self.assertEqual(spec.vk, ord("Q"))
        self.assertEqual(spec.modifiers, MOD_CONTROL | MOD_SHIFT)
        self.assertEqual(spec.display, "Ctrl+Shift+Q")

    def test_default_function_key(self) -> None:
        spec = parse_hotkey(DEFAULT_HOTKEY)

        self.assertEqual(spec.vk, 0x77)
        self.assertEqual(spec.display, "F8")

    def test_rejects_reserved_f12(self) -> None:
        with self.assertRaisesRegex(HotkeyError, "reserves F12"):
            parse_hotkey("Ctrl+F12", "en")

    def test_rejects_empty_value(self) -> None:
        with self.assertRaises(HotkeyError):
            parse_hotkey(" ")

    def test_english_errors_are_available(self) -> None:
        with self.assertRaisesRegex(HotkeyError, "cannot be empty"):
            parse_hotkey(" ", "en")


class HotkeyListenerTests(unittest.TestCase):
    def test_stop_releases_the_registered_hotkey(self) -> None:
        activated = Event()
        messages: Queue[int] = Queue()
        listener = hotkey.HotkeyListener(activated.set)

        def get_message(pointer, *_):
            message = messages.get(timeout=2)
            pointer._obj.message = message
            pointer._obj.wParam = 1
            return int(message != hotkey.WM_QUIT)

        with (
            patch.object(hotkey, "RegisterHotKey", return_value=True),
            patch.object(hotkey, "UnregisterHotKey", return_value=True) as unregister,
            patch.object(hotkey, "GetCurrentThreadId", return_value=42),
            patch.object(hotkey, "PeekMessage", return_value=False),
            patch.object(hotkey, "GetMessage", side_effect=get_message),
            patch.object(hotkey, "PostThreadMessage", side_effect=lambda _, message, *_args: messages.put(message)),
        ):
            listener.start(parse_hotkey(DEFAULT_HOTKEY))
            try:
                messages.put(hotkey.WM_HOTKEY)
                self.assertTrue(activated.wait(1))
            finally:
                listener.stop()

        unregister.assert_called_once_with(None, 1)


if __name__ == "__main__":
    unittest.main()
