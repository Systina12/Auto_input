from __future__ import annotations

import platform
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

from .hotkey import DEFAULT_HOTKEY, HotkeyError, HotkeyListener, HotkeySpec, parse_hotkey
from .win_input import (
    NEWLINE_CTRL_ENTER,
    NEWLINE_ENTER,
    NEWLINE_SHIFT_ENTER,
    NEWLINE_UNICODE,
    InputCancelled,
    fixed_delay,
    random_delay,
    type_text,
)


NEWLINE_MODE_OPTIONS = {
    "Enter": NEWLINE_ENTER,
    "Shift+Enter": NEWLINE_SHIFT_ENTER,
    "Ctrl+Enter": NEWLINE_CTRL_ENTER,
    "Unicode 换行": NEWLINE_UNICODE,
}


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


class AutoInputApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Auto Input")
        self.minsize(760, 520)
        self.geometry("900x640")

        self._cancel_event = threading.Event()
        self._hotkey_listener = HotkeyListener(lambda: self._emergency_stop("急停热键"))
        self._worker: threading.Thread | None = None
        self._running = False
        self._cancel_reason = "已取消。"
        self._status_var = tk.StringVar(value="就绪")
        self._count_var = tk.StringVar(value="0 字符")
        self._mode_var = tk.BooleanVar(value=False)
        self._minimize_var = tk.BooleanVar(value=True)

        self._delay_var = tk.StringVar(value="3")
        self._fixed_char_delay_var = tk.StringVar(value="30")
        self._min_char_delay_var = tk.StringVar(value="20")
        self._max_char_delay_var = tk.StringVar(value="120")
        self._emergency_hotkey_var = tk.StringVar(value=DEFAULT_HOTKEY)
        self._newline_mode_var = tk.StringVar(value="Enter")

        self._build_style()
        self._build_layout()
        self._refresh_delay_fields()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if platform.system() != "Windows":
            self._set_status("此工具的自动输入功能只支持 Windows。")
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

        ttk.Label(header, text="延时自动输入", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="粘贴文字，设置延时，开始后切到目标窗口即可。", style="Subtle.TLabel").grid(
            row=1, column=0, sticky="w", pady=(4, 0)
        )

        main = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        main.grid(row=1, column=0, sticky="nsew")

        text_panel = ttk.Frame(main, padding=14, style="Panel.TFrame")
        text_panel.columnconfigure(0, weight=1)
        text_panel.rowconfigure(1, weight=1)
        main.add(text_panel, weight=3)

        ttk.Label(text_panel, text="输入内容", style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
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
        ttk.Button(footer, text="清空", command=self._clear_text).grid(row=0, column=2, sticky="e")

        settings_panel = ttk.Frame(main, padding=14, style="Panel.TFrame")
        settings_panel.columnconfigure(0, weight=1)
        main.add(settings_panel, weight=2)

        ttk.Label(settings_panel, text="运行设置", style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w")
        form = ttk.Frame(settings_panel, style="Panel.TFrame")
        form.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        form.columnconfigure(1, weight=1)

        self._field(form, "开始延时", self._delay_var, "秒", 0)
        ttk.Separator(form).grid(row=1, column=0, columnspan=3, sticky="ew", pady=12)

        ttk.Checkbutton(
            form,
            text="随机字间延迟",
            variable=self._mode_var,
            command=self._refresh_delay_fields,
        ).grid(row=2, column=0, columnspan=3, sticky="w")

        self.fixed_widgets = self._field(form, "固定字间延迟", self._fixed_char_delay_var, "毫秒", 3)
        self.min_widgets = self._field(form, "最小字间延迟", self._min_char_delay_var, "毫秒", 4)
        self.max_widgets = self._field(form, "最大字间延迟", self._max_char_delay_var, "毫秒", 5)
        self.newline_widgets = self._combo_field(form, "换行方式", self._newline_mode_var, tuple(NEWLINE_MODE_OPTIONS), 6)

        ttk.Separator(form).grid(row=7, column=0, columnspan=3, sticky="ew", pady=12)
        ttk.Checkbutton(form, text="开始后最小化窗口", variable=self._minimize_var).grid(row=8, column=0, columnspan=3, sticky="w")
        self.hotkey_widgets = self._field(form, "急停热键", self._emergency_hotkey_var, "全局", 9)

        guide = ttk.Frame(settings_panel, padding=(0, 12, 0, 0), style="Panel.TFrame")
        guide.grid(row=2, column=0, sticky="ew")
        ttk.Label(
            guide,
            text="运行时可按“取消”、 “急停”或全局急停热键停止。若目标程序以管理员权限运行，本工具也需要同等权限才能输入。",
            wraplength=300,
            style="PanelText.TLabel",
        ).grid(row=0, column=0, sticky="ew")

        actions = ttk.Frame(settings_panel, style="Panel.TFrame")
        actions.grid(row=3, column=0, sticky="ew", pady=(18, 0))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        actions.columnconfigure(2, weight=1)

        self.start_button = ttk.Button(actions, text="开始", command=self._start, style="Accent.TButton")
        self.start_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.cancel_button = ttk.Button(actions, text="取消", command=self._cancel, style="Danger.TButton")
        self.cancel_button.grid(row=0, column=1, sticky="ew", padx=6)
        self.cancel_button.state(["disabled"])
        self.emergency_button = ttk.Button(actions, text="急停", command=self._emergency_stop_from_button, style="Danger.TButton")
        self.emergency_button.grid(row=0, column=2, sticky="ew", padx=(6, 0))
        self.emergency_button.state(["disabled"])

        status = ttk.Frame(root, style="Root.TFrame")
        status.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        status.columnconfigure(0, weight=1)
        ttk.Label(status, textvariable=self._status_var, style="Status.TLabel").grid(row=0, column=0, sticky="ew")

    def _field(self, parent: ttk.Frame, label: str, variable: tk.StringVar, unit: str, row: int) -> tuple[ttk.Widget, ...]:
        label_widget = ttk.Label(parent, text=label, style="PanelText.TLabel")
        entry = ttk.Entry(parent, textvariable=variable, width=10, justify="right")
        unit_widget = ttk.Label(parent, text=unit, style="PanelText.TLabel")

        label_widget.grid(row=row, column=0, sticky="w", pady=4)
        entry.grid(row=row, column=1, sticky="ew", padx=(10, 8), pady=4)
        unit_widget.grid(row=row, column=2, sticky="e", pady=4)
        return label_widget, entry, unit_widget

    def _combo_field(
        self,
        parent: ttk.Frame,
        label: str,
        variable: tk.StringVar,
        values: tuple[str, ...],
        row: int,
    ) -> tuple[ttk.Widget, ...]:
        label_widget = ttk.Label(parent, text=label, style="PanelText.TLabel")
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

    def _on_text_modified(self, _event: tk.Event) -> None:
        self.text_box.edit_modified(False)
        text = self._get_text()
        self._count_var.set(f"{len(text)} 字符")

    def _clear_text(self) -> None:
        self.text_box.delete("1.0", "end")
        self._count_var.set("0 字符")

    def _start(self) -> None:
        if self._running:
            return

        try:
            settings = self._read_settings()
        except ValueError as exc:
            self._set_status(str(exc))
            return

        try:
            self._hotkey_listener.start(settings.emergency_hotkey)
        except HotkeyError as exc:
            self._set_status(str(exc))
            return

        self._running = True
        self._cancel_reason = "已取消。"
        self._cancel_event.clear()
        self.start_button.state(["disabled"])
        self.cancel_button.state(["!disabled"])
        self.emergency_button.state(["!disabled"])
        self._set_widgets_enabled(self.hotkey_widgets, False)
        self._set_widgets_enabled(self.newline_widgets, False)
        self._set_status(f"将在 {settings.start_delay:g} 秒后开始输入，请切换到目标窗口。急停热键：{settings.emergency_hotkey.display}")

        if settings.minimize_on_start:
            self.after(250, self.iconify)

        self._worker = threading.Thread(target=self._run_worker, args=(settings,), daemon=True)
        self._worker.start()

    def _cancel(self) -> None:
        if self._running:
            self._cancel_reason = "已取消。"
            self._cancel_event.set()
            self._set_status("正在取消...")

    def _emergency_stop_from_button(self) -> None:
        self._emergency_stop("急停按钮")

    def _emergency_stop(self, source: str) -> None:
        if self._running:
            self._cancel_reason = f"已急停（{source}）。"
            self._cancel_event.set()
            self._post_status(f"急停已触发（{source}），正在停止...")

    def _run_worker(self, settings: RunSettings) -> None:
        try:
            self._countdown(settings.start_delay)
            delay_provider = (
                random_delay(settings.min_char_delay, settings.max_char_delay)
                if settings.randomize
                else fixed_delay(settings.fixed_char_delay)
            )
            self._post_status("正在输入...")
            typed = type_text(settings.text, delay_provider, self._cancel_event, settings.newline_mode)
        except InputCancelled:
            self._post_done(self._cancel_reason)
        except Exception as exc:
            self._post_done(f"输入失败：{exc}")
        else:
            self._post_done(f"完成，已输入 {typed} 个字符。")

    def _countdown(self, seconds: float) -> None:
        end_time = time.monotonic() + seconds
        while True:
            if self._cancel_event.is_set():
                raise InputCancelled
            remaining = end_time - time.monotonic()
            if remaining <= 0:
                return
            self._post_status(f"将在 {remaining:.1f} 秒后开始输入，请切换到目标窗口。")
            if self._cancel_event.wait(min(0.1, remaining)):
                raise InputCancelled

    def _post_status(self, text: str) -> None:
        self.after(0, self._set_status, text)

    def _post_done(self, text: str) -> None:
        self.after(0, self._finish_run, text)

    def _finish_run(self, text: str) -> None:
        self._hotkey_listener.stop()
        self._running = False
        self.start_button.state(["!disabled"])
        self.cancel_button.state(["disabled"])
        self.emergency_button.state(["disabled"])
        self._set_widgets_enabled(self.hotkey_widgets, True)
        self._set_widgets_enabled(self.newline_widgets, True)
        self._set_status(text)
        if self.state() == "iconic":
            self.deiconify()
            self.lift()

    def _read_settings(self) -> RunSettings:
        text = self._get_text()
        if not text:
            raise ValueError("请先粘贴要输入的文字。")

        start_delay = self._read_non_negative_float(self._delay_var.get(), "开始延时")
        fixed_char_delay = self._read_milliseconds(self._fixed_char_delay_var.get(), "固定字间延迟")
        min_char_delay = self._read_milliseconds(self._min_char_delay_var.get(), "最小字间延迟")
        max_char_delay = self._read_milliseconds(self._max_char_delay_var.get(), "最大字间延迟")

        if self._mode_var.get() and min_char_delay > max_char_delay:
            raise ValueError("随机字间延迟的最小值不能大于最大值。")
        newline_mode = NEWLINE_MODE_OPTIONS.get(self._newline_mode_var.get())
        if newline_mode is None:
            raise ValueError("请选择有效的换行方式。")
        try:
            emergency_hotkey = parse_hotkey(self._emergency_hotkey_var.get())
        except HotkeyError as exc:
            raise ValueError(str(exc)) from None

        return RunSettings(
            text=text,
            start_delay=start_delay,
            randomize=self._mode_var.get(),
            fixed_char_delay=fixed_char_delay,
            min_char_delay=min_char_delay,
            max_char_delay=max_char_delay,
            minimize_on_start=self._minimize_var.get(),
            emergency_hotkey=emergency_hotkey,
            newline_mode=newline_mode,
        )

    def _get_text(self) -> str:
        return self.text_box.get("1.0", "end-1c")

    def _read_non_negative_float(self, raw: str, name: str) -> float:
        try:
            value = float(raw.strip())
        except ValueError:
            raise ValueError(f"{name}必须是数字。") from None
        if value < 0:
            raise ValueError(f"{name}不能小于 0。")
        return value

    def _read_milliseconds(self, raw: str, name: str) -> float:
        return self._read_non_negative_float(raw, name) / 1000

    def _set_status(self, text: str) -> None:
        self._status_var.set(text)

    def _on_close(self) -> None:
        self._cancel_event.set()
        self._hotkey_listener.stop()
        self.destroy()


def main() -> None:
    app = AutoInputApp()
    app.mainloop()
