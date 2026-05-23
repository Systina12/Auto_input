from __future__ import annotations

import platform
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

from .hotkey import DEFAULT_HOTKEY, HotkeyError, HotkeyListener, HotkeySpec, parse_hotkey
from .i18n import (
    DEFAULT_LANGUAGE,
    LANGUAGE_CHOICES,
    input_mode_from_label,
    input_mode_label,
    input_mode_labels,
    language_code,
    language_display,
    newline_label,
    newline_labels,
    newline_mode_from_label,
    text,
)
from .win_input import (
    INPUT_MODE_KEYBOARD,
    INPUT_MODE_UNICODE,
    NEWLINE_ENTER,
    NEWLINE_UNICODE,
    InputCancelled,
    find_unsupported_keyboard_char,
    fixed_delay,
    random_delay,
    type_text,
)


@dataclass(frozen=True)
class RunSettings:
    text: str
    start_delay: float
    randomize: bool
    fixed_char_delay: float
    min_char_delay: float
    max_char_delay: float
    minimize_on_start: bool
    emergency_hotkey: HotkeySpec
    newline_mode: str
    input_mode: str


class AutoInputApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Auto Input")
        self.minsize(760, 520)
        self.geometry("900x640")

        self._language_code = DEFAULT_LANGUAGE
        self._language_var = tk.StringVar(value=language_display(self._language_code))
        self._translatable: list[tuple[tk.Widget, str]] = []
        self._status_key: str | None = "ready"
        self._status_kwargs: dict[str, object] = {}
        self._last_count = 0

        self._cancel_event = threading.Event()
        self._hotkey_listener = HotkeyListener(lambda: self._emergency_stop(self._t("source_hotkey")))
        self._worker: threading.Thread | None = None
        self._running = False
        self._cancel_result: tuple[str, dict[str, object]] = ("cancelled", {})
        self._status_var = tk.StringVar(value=self._t("ready"))
        self._count_var = tk.StringVar(value=self._t("count", count=0))
        self._mode_var = tk.BooleanVar(value=False)
        self._minimize_var = tk.BooleanVar(value=True)

        self._delay_var = tk.StringVar(value="3")
        self._fixed_char_delay_var = tk.StringVar(value="30")
        self._min_char_delay_var = tk.StringVar(value="20")
        self._max_char_delay_var = tk.StringVar(value="120")
        self._emergency_hotkey_var = tk.StringVar(value=DEFAULT_HOTKEY)
        self._input_mode_var = tk.StringVar(value=input_mode_label(self._language_code, INPUT_MODE_UNICODE))
        self._newline_mode_var = tk.StringVar(value=newline_label(self._language_code, NEWLINE_ENTER))

        self._build_style()
        self._build_layout()
        self._refresh_delay_fields()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if platform.system() != "Windows":
            self._set_status_message("windows_only")
            self.start_button.state(["disabled"])

    def _build_style(self) -> None:
        self.configure(bg="#f5f6f8")
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")

        style.configure("Root.TFrame", background="#f5f6f8")
        style.configure("Panel.TFrame", background="#ffffff", relief="flat")
        style.configure("Header.TLabel", background="#f5f6f8", foreground="#182230", font=("Microsoft YaHei UI", 16, "bold"))
        style.configure("Subtle.TLabel", background="#f5f6f8", foreground="#667085", font=("Microsoft YaHei UI", 9))
        style.configure("PanelTitle.TLabel", background="#ffffff", foreground="#182230", font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("PanelText.TLabel", background="#ffffff", foreground="#475467", font=("Microsoft YaHei UI", 9))
        style.configure("Status.TLabel", background="#eef4ff", foreground="#194185", padding=(10, 7), font=("Microsoft YaHei UI", 9))
        style.configure("Danger.TButton", foreground="#b42318")
        style.configure("Accent.TButton", font=("Microsoft YaHei UI", 10, "bold"))

    def _build_layout(self) -> None:
        root = ttk.Frame(self, padding=18, style="Root.TFrame")
        root.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        header = ttk.Frame(root, style="Root.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        header.columnconfigure(0, weight=1)
        header.columnconfigure(1, weight=0)

        self._translated_label(header, "header_title", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        self._translated_label(header, "subtitle", style="Subtle.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 0))

        language_frame = ttk.Frame(header, style="Root.TFrame")
        language_frame.grid(row=0, column=1, rowspan=2, sticky="ne", padx=(16, 0))
        self._translated_label(language_frame, "language", style="Subtle.TLabel").grid(row=0, column=0, sticky="e", padx=(0, 8))
        self.language_combo = ttk.Combobox(
            language_frame,
            textvariable=self._language_var,
            values=LANGUAGE_CHOICES,
            state="readonly",
            width=10,
        )
        self.language_combo.grid(row=0, column=1, sticky="e")
        self.language_combo.bind("<<ComboboxSelected>>", self._on_language_changed)

        main = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        main.grid(row=1, column=0, sticky="nsew")

        text_panel = ttk.Frame(main, padding=14, style="Panel.TFrame")
        text_panel.columnconfigure(0, weight=1)
        text_panel.rowconfigure(1, weight=1)
        main.add(text_panel, weight=3)

        self._translated_label(text_panel, "text_title", style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        text_box_frame = ttk.Frame(text_panel)
        text_box_frame.grid(row=1, column=0, sticky="nsew")
        text_box_frame.columnconfigure(0, weight=1)
        text_box_frame.rowconfigure(0, weight=1)

        self.text_box = tk.Text(
            text_box_frame,
            wrap="word",
            undo=True,
            borderwidth=1,
            relief="solid",
            padx=12,
            pady=10,
            font=("Microsoft YaHei UI", 10),
            foreground="#182230",
            background="#ffffff",
            insertbackground="#182230",
            selectbackground="#b2ddff",
        )
        self.text_box.grid(row=0, column=0, sticky="nsew")
        self.text_box.bind("<<Modified>>", self._on_text_modified)

        scrollbar = ttk.Scrollbar(text_box_frame, command=self.text_box.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.text_box.configure(yscrollcommand=scrollbar.set)

        footer = ttk.Frame(text_panel, style="Panel.TFrame")
        footer.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        footer.columnconfigure(1, weight=1)
        ttk.Label(footer, textvariable=self._count_var, style="PanelText.TLabel").grid(row=0, column=0, sticky="w")
        self._translated_button(footer, "clear", command=self._clear_text).grid(row=0, column=2, sticky="e")

        settings_panel = ttk.Frame(main, padding=14, style="Panel.TFrame")
        settings_panel.columnconfigure(0, weight=1)
        main.add(settings_panel, weight=2)

        self._translated_label(settings_panel, "settings_title", style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w")
        form = ttk.Frame(settings_panel, style="Panel.TFrame")
        form.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        form.columnconfigure(1, weight=1)

        self._field(form, "start_delay", self._delay_var, "seconds", 0)
        ttk.Separator(form).grid(row=1, column=0, columnspan=3, sticky="ew", pady=12)

        self.random_delay_check = self._translated_checkbutton(
            form,
            "random_char_delay",
            variable=self._mode_var,
            command=self._refresh_delay_fields,
        )
        self.random_delay_check.grid(row=2, column=0, columnspan=3, sticky="w")

        self.fixed_widgets = self._field(form, "fixed_char_delay", self._fixed_char_delay_var, "milliseconds", 3)
        self.min_widgets = self._field(form, "min_char_delay", self._min_char_delay_var, "milliseconds", 4)
        self.max_widgets = self._field(form, "max_char_delay", self._max_char_delay_var, "milliseconds", 5)
        self.input_mode_widgets = self._combo_field(form, "input_mode", self._input_mode_var, input_mode_labels(self._language_code), 6)
        self.input_mode_combo = self.input_mode_widgets[1]
        self.newline_widgets = self._combo_field(form, "newline_mode", self._newline_mode_var, newline_labels(self._language_code), 7)
        self.newline_combo = self.newline_widgets[1]

        ttk.Separator(form).grid(row=8, column=0, columnspan=3, sticky="ew", pady=12)
        self._translated_checkbutton(form, "minimize_on_start", variable=self._minimize_var).grid(
            row=9, column=0, columnspan=3, sticky="w"
        )
        self.hotkey_widgets = self._field(form, "emergency_hotkey", self._emergency_hotkey_var, "global_hotkey", 10)

        guide = ttk.Frame(settings_panel, padding=(0, 12, 0, 0), style="Panel.TFrame")
        guide.grid(row=2, column=0, sticky="ew")
        self._translated_label(guide, "guide", wraplength=300, style="PanelText.TLabel").grid(row=0, column=0, sticky="ew")

        actions = ttk.Frame(settings_panel, style="Panel.TFrame")
        actions.grid(row=3, column=0, sticky="ew", pady=(18, 0))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        actions.columnconfigure(2, weight=1)

        self.start_button = self._translated_button(actions, "start", command=self._start, style="Accent.TButton")
        self.start_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.cancel_button = self._translated_button(actions, "cancel", command=self._cancel, style="Danger.TButton")
        self.cancel_button.grid(row=0, column=1, sticky="ew", padx=6)
        self.cancel_button.state(["disabled"])
        self.emergency_button = self._translated_button(
            actions,
            "emergency_stop",
            command=self._emergency_stop_from_button,
            style="Danger.TButton",
        )
        self.emergency_button.grid(row=0, column=2, sticky="ew", padx=(6, 0))
        self.emergency_button.state(["disabled"])

        status = ttk.Frame(root, style="Root.TFrame")
        status.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        status.columnconfigure(0, weight=1)
        ttk.Label(status, textvariable=self._status_var, style="Status.TLabel").grid(row=0, column=0, sticky="ew")

    def _translated_label(self, parent: tk.Widget, key: str, **kwargs: object) -> ttk.Label:
        label = ttk.Label(parent, text=self._t(key), **kwargs)
        self._translatable.append((label, key))
        return label

    def _translated_button(self, parent: tk.Widget, key: str, **kwargs: object) -> ttk.Button:
        button = ttk.Button(parent, text=self._t(key), **kwargs)
        self._translatable.append((button, key))
        return button

    def _translated_checkbutton(self, parent: tk.Widget, key: str, **kwargs: object) -> ttk.Checkbutton:
        checkbutton = ttk.Checkbutton(parent, text=self._t(key), **kwargs)
        self._translatable.append((checkbutton, key))
        return checkbutton

    def _field(
        self,
        parent: ttk.Frame,
        label_key: str,
        variable: tk.StringVar,
        unit_key: str,
        row: int,
    ) -> tuple[ttk.Widget, ...]:
        label_widget = self._translated_label(parent, label_key, style="PanelText.TLabel")
        entry = ttk.Entry(parent, textvariable=variable, width=10, justify="right")
        unit_widget = self._translated_label(parent, unit_key, style="PanelText.TLabel")

        label_widget.grid(row=row, column=0, sticky="w", pady=4)
        entry.grid(row=row, column=1, sticky="ew", padx=(10, 8), pady=4)
        unit_widget.grid(row=row, column=2, sticky="e", pady=4)
        return label_widget, entry, unit_widget

    def _combo_field(
        self,
        parent: ttk.Frame,
        label_key: str,
        variable: tk.StringVar,
        values: tuple[str, ...],
        row: int,
    ) -> tuple[ttk.Widget, ...]:
        label_widget = self._translated_label(parent, label_key, style="PanelText.TLabel")
        combo = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", width=12)

        label_widget.grid(row=row, column=0, sticky="w", pady=4)
        combo.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(10, 0), pady=4)
        return label_widget, combo

    def _refresh_delay_fields(self) -> None:
        random_mode = self._mode_var.get()
        self._set_widgets_enabled(self.fixed_widgets, not random_mode)
        self._set_widgets_enabled(self.min_widgets, random_mode)
        self._set_widgets_enabled(self.max_widgets, random_mode)

    def _set_widgets_enabled(self, widgets: tuple[ttk.Widget, ...], enabled: bool) -> None:
        for widget in widgets:
            if isinstance(widget, ttk.Entry):
                widget.state(["!disabled"] if enabled else ["disabled"])
            elif isinstance(widget, ttk.Combobox):
                widget.state(["!disabled", "readonly"] if enabled else ["disabled"])

    def _on_language_changed(self, _event: tk.Event) -> None:
        selected_input_mode = self._selected_input_mode()
        selected_newline_mode = self._selected_newline_mode()
        self._language_code = language_code(self._language_var.get())
        self._language_var.set(language_display(self._language_code))
        self._sync_input_mode_options(selected_input_mode)
        self._sync_newline_options(selected_newline_mode)
        self._apply_language()

    def _apply_language(self) -> None:
        for widget, key in self._translatable:
            widget.configure(text=self._t(key))
        self._update_count()
        if self._status_key is not None:
            self._status_var.set(self._t(self._status_key, **self._status_kwargs))

    def _sync_newline_options(self, selected_mode: str) -> None:
        self.newline_combo.configure(values=newline_labels(self._language_code))
        self._newline_mode_var.set(newline_label(self._language_code, selected_mode))

    def _sync_input_mode_options(self, selected_mode: str) -> None:
        self.input_mode_combo.configure(values=input_mode_labels(self._language_code))
        self._input_mode_var.set(input_mode_label(self._language_code, selected_mode))

    def _selected_input_mode(self) -> str:
        return input_mode_from_label(self._language_code, self._input_mode_var.get()) or INPUT_MODE_UNICODE

    def _selected_newline_mode(self) -> str:
        return newline_mode_from_label(self._language_code, self._newline_mode_var.get()) or NEWLINE_ENTER

    def _on_text_modified(self, _event: tk.Event) -> None:
        self.text_box.edit_modified(False)
        self._last_count = len(self._get_text())
        self._update_count()

    def _update_count(self) -> None:
        self._count_var.set(self._t("count", count=self._last_count))

    def _clear_text(self) -> None:
        self.text_box.delete("1.0", "end")
        self._last_count = 0
        self._update_count()

    def _start(self) -> None:
        if self._running:
            return

        try:
            settings = self._read_settings()
        except ValueError as exc:
            self._set_status_text(str(exc))
            return

        try:
            self._hotkey_listener.start(settings.emergency_hotkey, self._language_code)
        except HotkeyError as exc:
            self._set_status_text(str(exc))
            return

        self._running = True
        self._cancel_result = ("cancelled", {})
        self._cancel_event.clear()
        self.start_button.state(["disabled"])
        self.cancel_button.state(["!disabled"])
        self.emergency_button.state(["!disabled"])
        self._set_widgets_enabled(self.hotkey_widgets, False)
        self._set_widgets_enabled(self.input_mode_widgets, False)
        self._set_widgets_enabled(self.newline_widgets, False)
        self._set_status_message("start_pending", delay=settings.start_delay, hotkey=settings.emergency_hotkey.display)

        if settings.minimize_on_start:
            self.after(250, self.iconify)

        self._worker = threading.Thread(target=self._run_worker, args=(settings,), daemon=True)
        self._worker.start()

    def _cancel(self) -> None:
        if self._running:
            self._cancel_result = ("cancelled", {})
            self._cancel_event.set()
            self._set_status_message("canceling")

    def _emergency_stop_from_button(self) -> None:
        self._emergency_stop(self._t("source_button"))

    def _emergency_stop(self, source: str) -> None:
        if self._running:
            self._cancel_result = ("emergency_done", {"source": source})
            self._cancel_event.set()
            self._post_status_message("emergency_triggered", source=source)

    def _run_worker(self, settings: RunSettings) -> None:
        try:
            self._countdown(settings.start_delay)
            delay_provider = (
                random_delay(settings.min_char_delay, settings.max_char_delay)
                if settings.randomize
                else fixed_delay(settings.fixed_char_delay)
            )
            self._post_status_message("typing")
            typed = type_text(settings.text, delay_provider, self._cancel_event, settings.newline_mode, settings.input_mode)
        except InputCancelled:
            key, kwargs = self._cancel_result
            self._post_done_message(key, **kwargs)
        except Exception as exc:
            self._post_done_message("input_failed", error=exc)
        else:
            self._post_done_message("input_done", count=typed)

    def _countdown(self, seconds: float) -> None:
        end_time = time.monotonic() + seconds
        while True:
            if self._cancel_event.is_set():
                raise InputCancelled
            remaining = end_time - time.monotonic()
            if remaining <= 0:
                return
            self._post_status_message("countdown", remaining=remaining)
            if self._cancel_event.wait(min(0.1, remaining)):
                raise InputCancelled

    def _post_status_message(self, key: str, **kwargs: object) -> None:
        self.after(0, lambda: self._set_status_message(key, **kwargs))

    def _post_done_message(self, key: str, **kwargs: object) -> None:
        self.after(0, lambda: self._finish_run_message(key, kwargs))

    def _finish_run_message(self, key: str, kwargs: dict[str, object]) -> None:
        self._finish_run()
        self._set_status_message(key, **kwargs)

    def _finish_run(self) -> None:
        self._hotkey_listener.stop()
        self._running = False
        self.start_button.state(["!disabled"])
        self.cancel_button.state(["disabled"])
        self.emergency_button.state(["disabled"])
        self._set_widgets_enabled(self.hotkey_widgets, True)
        self._set_widgets_enabled(self.input_mode_widgets, True)
        self._set_widgets_enabled(self.newline_widgets, True)
        if self.state() == "iconic":
            self.deiconify()
            self.lift()

    def _read_settings(self) -> RunSettings:
        input_text = self._get_text()
        if not input_text:
            raise ValueError(self._t("error_no_text"))

        start_delay = self._read_non_negative_float(self._delay_var.get(), self._t("start_delay"))
        fixed_char_delay = self._read_milliseconds(self._fixed_char_delay_var.get(), self._t("fixed_char_delay"))
        min_char_delay = self._read_milliseconds(self._min_char_delay_var.get(), self._t("min_char_delay"))
        max_char_delay = self._read_milliseconds(self._max_char_delay_var.get(), self._t("max_char_delay"))

        if self._mode_var.get() and min_char_delay > max_char_delay:
            raise ValueError(self._t("error_random_range"))
        input_mode = self._selected_input_mode()
        if input_mode is None:
            raise ValueError(self._t("error_invalid_input_mode"))
        newline_mode = self._selected_newline_mode()
        if newline_mode is None:
            raise ValueError(self._t("error_invalid_newline"))
        if input_mode == INPUT_MODE_KEYBOARD and newline_mode == NEWLINE_UNICODE:
            raise ValueError(self._t("error_keyboard_unicode_newline"))
        if input_mode == INPUT_MODE_KEYBOARD:
            unsupported_char = find_unsupported_keyboard_char(input_text)
            if unsupported_char is not None:
                raise ValueError(self._t("error_unsupported_keyboard_char", char=repr(unsupported_char)))
        try:
            emergency_hotkey = parse_hotkey(self._emergency_hotkey_var.get(), self._language_code)
        except HotkeyError as exc:
            raise ValueError(str(exc)) from None

        return RunSettings(
            text=input_text,
            start_delay=start_delay,
            randomize=self._mode_var.get(),
            fixed_char_delay=fixed_char_delay,
            min_char_delay=min_char_delay,
            max_char_delay=max_char_delay,
            minimize_on_start=self._minimize_var.get(),
            emergency_hotkey=emergency_hotkey,
            newline_mode=newline_mode,
            input_mode=input_mode,
        )

    def _get_text(self) -> str:
        return self.text_box.get("1.0", "end-1c")

    def _read_non_negative_float(self, raw: str, name: str) -> float:
        try:
            value = float(raw.strip())
        except ValueError:
            raise ValueError(self._t("error_numeric", name=name)) from None
        if value < 0:
            raise ValueError(self._t("error_non_negative", name=name))
        return value

    def _read_milliseconds(self, raw: str, name: str) -> float:
        return self._read_non_negative_float(raw, name) / 1000

    def _set_status_message(self, key: str, **kwargs: object) -> None:
        self._status_key = key
        self._status_kwargs = dict(kwargs)
        self._status_var.set(self._t(key, **kwargs))

    def _set_status_text(self, value: str) -> None:
        self._status_key = None
        self._status_kwargs = {}
        self._status_var.set(value)

    def _t(self, key: str, **kwargs: object) -> str:
        return text(self._language_code, key, **kwargs)

    def _on_close(self) -> None:
        self._cancel_event.set()
        self._hotkey_listener.stop()
        self.destroy()


def main() -> None:
    app = AutoInputApp()
    app.mainloop()
