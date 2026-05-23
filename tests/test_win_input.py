from __future__ import annotations

import threading
import unittest
from unittest.mock import patch

from auto_input import win_input


class DelayTests(unittest.TestCase):
    def test_fixed_delay_clamps_negative_values(self) -> None:
        self.assertEqual(win_input.fixed_delay(-1)(), 0.0)

    def test_random_delay_stays_in_range(self) -> None:
        provider = win_input.random_delay(0.01, 0.02)

        for _ in range(50):
            value = provider()
            self.assertGreaterEqual(value, 0.01)
            self.assertLessEqual(value, 0.02)


class InputEncodingTests(unittest.TestCase):
    def test_input_structure_size_matches_windows_api_contract(self) -> None:
        expected_size = 40 if win_input.ctypes.sizeof(win_input.ctypes.c_void_p) == 8 else 28

        self.assertEqual(win_input.ctypes.sizeof(win_input.INPUT), expected_size)

    def test_utf16_units_supports_bmp_and_surrogate_pairs(self) -> None:
        self.assertEqual(win_input._utf16_units("中"), [0x4E2D])
        self.assertEqual(win_input._utf16_units("🙂"), [0xD83D, 0xDE42])

    def test_type_text_treats_crlf_as_one_enter(self) -> None:
        events: list[tuple[int, int, int]] = []

        with (
            patch.object(win_input, "_send_keyboard_input", side_effect=lambda vk, scan, flags: events.append((vk, scan, flags))),
            patch.object(win_input, "_sleep_interruptibly", return_value=None),
        ):
            typed = win_input.type_text("A\r\nB", win_input.fixed_delay(0), threading.Event())

        self.assertEqual(typed, 3)
        self.assertEqual(events[0][1], ord("A"))
        self.assertEqual(events[2][0], win_input.VK_RETURN)
        self.assertEqual(events[4][1], ord("B"))

    def test_type_text_supports_shift_enter_newlines(self) -> None:
        events: list[tuple[int, int, int]] = []

        with (
            patch.object(win_input, "_send_keyboard_input", side_effect=lambda vk, scan, flags: events.append((vk, scan, flags))),
            patch.object(win_input, "_sleep_interruptibly", return_value=None),
        ):
            typed = win_input.type_text(
                "A\nB",
                win_input.fixed_delay(0),
                threading.Event(),
                win_input.NEWLINE_SHIFT_ENTER,
            )

        self.assertEqual(typed, 3)
        self.assertEqual(events[2], (win_input.VK_SHIFT, 0, 0))
        self.assertEqual(events[3], (win_input.VK_RETURN, 0, 0))
        self.assertEqual(events[4], (win_input.VK_RETURN, 0, win_input.KEYEVENTF_KEYUP))
        self.assertEqual(events[5], (win_input.VK_SHIFT, 0, win_input.KEYEVENTF_KEYUP))

    def test_type_text_supports_ctrl_enter_newlines(self) -> None:
        events: list[tuple[int, int, int]] = []

        with (
            patch.object(win_input, "_send_keyboard_input", side_effect=lambda vk, scan, flags: events.append((vk, scan, flags))),
            patch.object(win_input, "_sleep_interruptibly", return_value=None),
        ):
            win_input.type_text(
                "A\nB",
                win_input.fixed_delay(0),
                threading.Event(),
                win_input.NEWLINE_CTRL_ENTER,
            )

        self.assertEqual(events[2], (win_input.VK_CONTROL, 0, 0))
        self.assertEqual(events[3], (win_input.VK_RETURN, 0, 0))
        self.assertEqual(events[4], (win_input.VK_RETURN, 0, win_input.KEYEVENTF_KEYUP))
        self.assertEqual(events[5], (win_input.VK_CONTROL, 0, win_input.KEYEVENTF_KEYUP))

    def test_type_text_supports_unicode_newlines(self) -> None:
        events: list[tuple[int, int, int]] = []

        with (
            patch.object(win_input, "_send_keyboard_input", side_effect=lambda vk, scan, flags: events.append((vk, scan, flags))),
            patch.object(win_input, "_sleep_interruptibly", return_value=None),
        ):
            typed = win_input.type_text(
                "A\r\nB",
                win_input.fixed_delay(0),
                threading.Event(),
                win_input.NEWLINE_UNICODE,
            )

        self.assertEqual(typed, 3)
        self.assertEqual(events[2], (0, ord("\n"), win_input.KEYEVENTF_UNICODE))
        self.assertEqual(events[3], (0, ord("\n"), win_input.KEYEVENTF_UNICODE | win_input.KEYEVENTF_KEYUP))

    def test_type_text_rejects_unknown_newline_mode(self) -> None:
        with self.assertRaises(ValueError):
            win_input.type_text("A", win_input.fixed_delay(0), threading.Event(), "bad-mode")

    def test_type_text_supports_keyboard_input_mode_with_us_scan_codes(self) -> None:
        events: list[tuple[int, int, int]] = []

        with (
            patch.object(win_input, "_send_keyboard_input", side_effect=lambda vk, scan, flags: events.append((vk, scan, flags))),
            patch.object(win_input, "_sleep_interruptibly", return_value=None),
        ):
            typed = win_input.type_text(
                "aA!",
                win_input.fixed_delay(0),
                threading.Event(),
                win_input.NEWLINE_ENTER,
                win_input.INPUT_MODE_KEYBOARD,
            )

        self.assertEqual(typed, 3)
        self.assertEqual(events[0], (0, 0x1E, win_input.KEYEVENTF_SCANCODE))
        self.assertEqual(events[1], (0, 0x1E, win_input.KEYEVENTF_SCANCODE | win_input.KEYEVENTF_KEYUP))
        self.assertEqual(events[2], (0, win_input.SCANCODE_SHIFT, win_input.KEYEVENTF_SCANCODE))
        self.assertEqual(events[3], (0, 0x1E, win_input.KEYEVENTF_SCANCODE))
        self.assertEqual(events[4], (0, 0x1E, win_input.KEYEVENTF_SCANCODE | win_input.KEYEVENTF_KEYUP))
        self.assertEqual(events[5], (0, win_input.SCANCODE_SHIFT, win_input.KEYEVENTF_SCANCODE | win_input.KEYEVENTF_KEYUP))
        self.assertEqual(events[6], (0, win_input.SCANCODE_SHIFT, win_input.KEYEVENTF_SCANCODE))
        self.assertEqual(events[7], (0, 0x02, win_input.KEYEVENTF_SCANCODE))

    def test_keyboard_input_mode_letter_case_does_not_depend_on_caps_lock(self) -> None:
        self.assertEqual(win_input._keyboard_keystroke("a"), win_input.KeyStroke(0x1E, False))
        self.assertEqual(win_input._keyboard_keystroke("A"), win_input.KeyStroke(0x1E, True))

    def test_type_text_uses_keyboard_enter_in_keyboard_input_mode(self) -> None:
        events: list[tuple[int, int, int]] = []

        with (
            patch.object(win_input, "_send_keyboard_input", side_effect=lambda vk, scan, flags: events.append((vk, scan, flags))),
            patch.object(win_input, "_sleep_interruptibly", return_value=None),
        ):
            typed = win_input.type_text(
                "a\r\nb",
                win_input.fixed_delay(0),
                threading.Event(),
                win_input.NEWLINE_ENTER,
                win_input.INPUT_MODE_KEYBOARD,
            )

        self.assertEqual(typed, 3)
        self.assertEqual(events[2], (0, win_input.SCANCODE_ENTER, win_input.KEYEVENTF_SCANCODE))
        self.assertEqual(events[3], (0, win_input.SCANCODE_ENTER, win_input.KEYEVENTF_SCANCODE | win_input.KEYEVENTF_KEYUP))

    def test_keyboard_input_mode_rejects_unsupported_characters(self) -> None:
        self.assertEqual(win_input.find_unsupported_keyboard_char("abc中"), "中")

        with self.assertRaises(win_input.UnsupportedKeyboardCharacter):
            win_input.type_text(
                "中",
                win_input.fixed_delay(0),
                threading.Event(),
                win_input.NEWLINE_ENTER,
                win_input.INPUT_MODE_KEYBOARD,
            )

    def test_keyboard_input_mode_rejects_unicode_newline(self) -> None:
        with self.assertRaises(ValueError):
            win_input.type_text(
                "\n",
                win_input.fixed_delay(0),
                threading.Event(),
                win_input.NEWLINE_UNICODE,
                win_input.INPUT_MODE_KEYBOARD,
            )

    def test_type_text_rejects_unknown_input_mode(self) -> None:
        with self.assertRaises(ValueError):
            win_input.type_text("A", win_input.fixed_delay(0), threading.Event(), win_input.NEWLINE_ENTER, "bad-mode")


if __name__ == "__main__":
    unittest.main()
