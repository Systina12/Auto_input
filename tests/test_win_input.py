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


if __name__ == "__main__":
    unittest.main()
