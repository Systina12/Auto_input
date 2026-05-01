from __future__ import annotations

import unittest

from auto_input import i18n
from auto_input.win_input import NEWLINE_ENTER, NEWLINE_UNICODE


class I18nTests(unittest.TestCase):
    def test_language_display_round_trip(self) -> None:
        self.assertEqual(i18n.language_code("中文"), "zh")
        self.assertEqual(i18n.language_code("English"), "en")
        self.assertEqual(i18n.language_display("en"), "English")

    def test_newline_labels_are_language_specific(self) -> None:
        self.assertEqual(i18n.newline_label("zh", NEWLINE_UNICODE), "Unicode 换行")
        self.assertEqual(i18n.newline_label("en", NEWLINE_UNICODE), "Unicode newline")
        self.assertEqual(i18n.newline_mode_from_label("en", "Enter"), NEWLINE_ENTER)

    def test_text_formats_current_language(self) -> None:
        self.assertEqual(i18n.text("en", "ready"), "Ready")
        self.assertEqual(i18n.text("en", "count", count=3), "3 chars")


if __name__ == "__main__":
    unittest.main()
