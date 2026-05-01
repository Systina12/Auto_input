from __future__ import annotations

import unittest

from auto_input.hotkey import MOD_CONTROL, MOD_SHIFT, HotkeyError, parse_hotkey


class HotkeyParsingTests(unittest.TestCase):
    def test_default_backtick_aliases(self) -> None:
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

    def test_function_key(self) -> None:
        spec = parse_hotkey("F12")

        self.assertEqual(spec.vk, 0x7B)
        self.assertEqual(spec.display, "F12")

    def test_rejects_empty_value(self) -> None:
        with self.assertRaises(HotkeyError):
            parse_hotkey(" ")


if __name__ == "__main__":
    unittest.main()
