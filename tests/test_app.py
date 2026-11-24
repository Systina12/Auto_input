from __future__ import annotations

import unittest
from unittest.mock import Mock, call, patch

from auto_input import app
from auto_input.hotkey import DEFAULT_HOTKEY, parse_hotkey
from auto_input.win_input import INPUT_MODE_UNICODE, NEWLINE_ENTER, InputWindow


class RunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = app.AutoInputApp.__new__(app.AutoInputApp)
        self.app._language_code = "en"
        self.settings = app.RunSettings(
            text="ab",
            start_delay=0,
            randomize=False,
            fixed_char_delay=0,
            min_char_delay=0,
            max_char_delay=0,
            minimize_on_start=True,
            emergency_hotkey=parse_hotkey(DEFAULT_HOTKEY),
            newline_mode=NEWLINE_ENTER,
            input_mode=INPUT_MODE_UNICODE,
        )
        self.target = InputWindow(10, 11, 12)
        self.other = InputWindow(20, 21, 22)

    def test_focus_change_pauses_until_the_same_window_returns(self) -> None:
        run = app.RunState()
        with (
            patch.object(app, "foreground_window", side_effect=[self.target, self.target, self.other, self.target]),
            patch.object(app, "input_window", return_value=self.target),
            patch.object(run.cancel_event, "wait", return_value=False) as wait,
            patch("auto_input.win_input._send_char") as send_char,
        ):
            self.app._run_worker(self.settings, run)

        wait.assert_called_once()
        self.assertEqual(send_char.call_args_list, [call("a", INPUT_MODE_UNICODE), call("b", INPUT_MODE_UNICODE)])
        self.assertEqual([run.updates.get_nowait().key for _ in range(4)], [
            "typing", "target_paused", "typing", "input_done",
        ])

    def test_target_closing_stops_input(self) -> None:
        run = app.RunState()
        with (
            patch.object(app, "foreground_window", side_effect=[self.target, self.target, self.other]),
            patch.object(app, "input_window", return_value=None),
            patch("auto_input.win_input._send_char") as send_char,
        ):
            self.app._run_worker(self.settings, run)

        send_char.assert_called_once_with("a", INPUT_MODE_UNICODE)
        self.assertEqual(run.updates.get_nowait().key, "typing")
        self.assertEqual(run.updates.get_nowait().key, "target_closed")

    def test_emergency_stop_while_paused_prevents_more_input(self) -> None:
        run = app.RunState()
        with (
            patch.object(app, "foreground_window", side_effect=[self.target, self.target, self.other]),
            patch.object(app, "input_window", return_value=self.target),
            patch.object(run.cancel_event, "wait", side_effect=lambda _: run.cancel("source_hotkey")),
            patch("auto_input.win_input._send_char") as send_char,
        ):
            self.app._run_worker(self.settings, run)

        send_char.assert_called_once_with("a", INPUT_MODE_UNICODE)
        self.assertEqual([run.updates.get_nowait().key for _ in range(3)], ["typing", "target_paused", "cancelled"])
        self.assertEqual(run.stop_source, "source_hotkey")

    def test_hotkey_conflict_blocks_the_first_character(self) -> None:
        run = app.RunState()
        with (
            patch.object(app, "foreground_window", return_value=self.target),
            patch.object(app, "hotkey_conflicts_with_input", return_value=True),
            patch.object(app, "type_text") as type_text,
        ):
            self.app._run_worker(self.settings, run)

        type_text.assert_not_called()
        self.assertEqual(run.updates.get_nowait(), app.RunUpdate("hotkey_input_conflict", {"hotkey": "F8"}, True))

    def test_start_minimizes_before_starting_the_worker(self) -> None:
        ui_calls = Mock()
        self.app._run = None
        self.app._read_settings = Mock(return_value=self.settings)
        self.app._set_status_message = Mock()
        self.app.start_button = Mock()
        self.app.cancel_button = Mock()
        self.app.emergency_button = Mock()
        self.app.hotkey_widgets = self.app.input_mode_widgets = self.app.newline_widgets = ()
        self.app.iconify = ui_calls.iconify
        self.app.after = ui_calls.after

        with patch.object(app, "HotkeyListener"), patch.object(app.threading, "Thread", return_value=ui_calls.worker):
            self.app._start()

        self.assertEqual(ui_calls.mock_calls, [
            call.iconify(), call.worker.start(), call.after(25, self.app._poll_run_updates),
        ])

    def test_hotkey_stop_status_is_the_final_update(self) -> None:
        run = app.RunState()
        run.post("typing")
        run.cancel("source_hotkey")
        run.post("cancelled", finished=True)
        self.app._run = run
        self.app._finish_run = Mock()
        self.app._set_status_message = Mock()

        self.app._poll_run_updates()

        self.app._finish_run.assert_called_once()
        self.app._set_status_message.assert_called_once_with("emergency_done", source="emergency hotkey")

    def test_delay_values_must_be_finite_and_in_range(self) -> None:
        for raw in ("nan", "inf", "1e308"):
            with self.subTest(value=raw), self.assertRaises(ValueError):
                self.app._read_non_negative_float(raw, "Delay")

    def test_disabled_delay_fields_are_ignored(self) -> None:
        self.app._get_text = Mock(return_value="abc")
        self.app._delay_var = Mock()
        self.app._delay_var.get.return_value = "3"
        self.app._mode_var = Mock()
        self.app._minimize_var = Mock()
        self.app._minimize_var.get.return_value = True
        self.app._emergency_hotkey_var = Mock()
        self.app._emergency_hotkey_var.get.return_value = DEFAULT_HOTKEY
        self.app._selected_input_mode = Mock(return_value=INPUT_MODE_UNICODE)
        self.app._selected_newline_mode = Mock(return_value=NEWLINE_ENTER)

        for randomize, fixed, minimum, maximum in ((True, "", "20", "120"), (False, "30", "", "")):
            with self.subTest(randomize=randomize):
                self.app._mode_var.get.return_value = randomize
                self.app._fixed_char_delay_var = Mock()
                self.app._fixed_char_delay_var.get.return_value = fixed
                self.app._min_char_delay_var = Mock()
                self.app._min_char_delay_var.get.return_value = minimum
                self.app._max_char_delay_var = Mock()
                self.app._max_char_delay_var.get.return_value = maximum
                settings = self.app._read_settings()
                self.assertEqual(settings.randomize, randomize)
                self.assertEqual(settings.fixed_char_delay, 0.0 if randomize else 0.03)
                self.assertEqual(settings.min_char_delay, 0.02 if randomize else 0.0)
                self.assertEqual(settings.max_char_delay, 0.12 if randomize else 0.0)
