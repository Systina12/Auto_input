from __future__ import annotations

from .win_input import NEWLINE_CTRL_ENTER, NEWLINE_ENTER, NEWLINE_SHIFT_ENTER, NEWLINE_UNICODE


DEFAULT_LANGUAGE = "zh"
LANGUAGE_DISPLAY = {
    "zh": "中文",
    "en": "English",
}
DISPLAY_TO_LANGUAGE = {display: code for code, display in LANGUAGE_DISPLAY.items()}
LANGUAGE_CHOICES = tuple(LANGUAGE_DISPLAY.values())

NEWLINE_LABELS = {
    "zh": {
        NEWLINE_ENTER: "Enter",
        NEWLINE_SHIFT_ENTER: "Shift+Enter",
        NEWLINE_CTRL_ENTER: "Ctrl+Enter",
        NEWLINE_UNICODE: "Unicode 换行",
    },
    "en": {
        NEWLINE_ENTER: "Enter",
        NEWLINE_SHIFT_ENTER: "Shift+Enter",
        NEWLINE_CTRL_ENTER: "Ctrl+Enter",
        NEWLINE_UNICODE: "Unicode newline",
    },
}

STRINGS = {
    "zh": {
        "header_title": "自动输入",
        "subtitle": "粘贴文字，设置延时，开始后切到目标窗口即可。",
        "language": "语言",
        "text_title": "输入内容",
        "clear": "清空",
        "settings_title": "运行设置",
        "start_delay": "开始延时",
        "seconds": "秒",
        "random_char_delay": "随机字间延迟",
        "fixed_char_delay": "固定字间延迟",
        "min_char_delay": "最小字间延迟",
        "max_char_delay": "最大字间延迟",
        "milliseconds": "毫秒",
        "newline_mode": "换行方式",
        "minimize_on_start": "开始后最小化窗口",
        "emergency_hotkey": "急停热键",
        "global_hotkey": "全局",
        "guide": "运行时可按“取消”、“急停”或全局急停热键停止。若目标程序以管理员权限运行，本工具也需要同等权限才能输入。",
        "start": "开始",
        "cancel": "取消",
        "emergency_stop": "急停",
        "ready": "就绪",
        "count": "{count} 字符",
        "windows_only": "此工具的自动输入功能只支持 Windows。",
        "start_pending": "将在 {delay:g} 秒后开始输入，请切换到目标窗口。急停热键：{hotkey}",
        "countdown": "将在 {remaining:.1f} 秒后开始输入，请切换到目标窗口。",
        "typing": "正在输入...",
        "canceling": "正在取消...",
        "cancelled": "已取消。",
        "source_hotkey": "急停热键",
        "source_button": "急停按钮",
        "emergency_triggered": "急停已触发（{source}），正在停止...",
        "emergency_done": "已急停（{source}）。",
        "input_failed": "输入失败：{error}",
        "input_done": "完成，已输入 {count} 个字符。",
        "error_no_text": "请先粘贴要输入的文字。",
        "error_numeric": "{name}必须是数字。",
        "error_non_negative": "{name}不能小于 0。",
        "error_random_range": "随机字间延迟的最小值不能大于最大值。",
        "error_invalid_newline": "请选择有效的换行方式。",
    },
    "en": {
        "header_title": "Auto Input",
        "subtitle": "Paste text, set delays, then switch to the target window after starting.",
        "language": "Language",
        "text_title": "Text",
        "clear": "Clear",
        "settings_title": "Settings",
        "start_delay": "Start delay",
        "seconds": "sec",
        "random_char_delay": "Random character delay",
        "fixed_char_delay": "Fixed character delay",
        "min_char_delay": "Minimum character delay",
        "max_char_delay": "Maximum character delay",
        "milliseconds": "ms",
        "newline_mode": "Newline mode",
        "minimize_on_start": "Minimize after start",
        "emergency_hotkey": "Emergency hotkey",
        "global_hotkey": "Global",
        "guide": "During a run, use Cancel, Emergency Stop, or the global emergency hotkey to stop. If the target runs as administrator, this tool needs the same privilege level.",
        "start": "Start",
        "cancel": "Cancel",
        "emergency_stop": "Stop",
        "ready": "Ready",
        "count": "{count} chars",
        "windows_only": "Automatic input is only supported on Windows.",
        "start_pending": "Typing starts in {delay:g} seconds. Switch to the target window. Emergency hotkey: {hotkey}",
        "countdown": "Typing starts in {remaining:.1f} seconds. Switch to the target window.",
        "typing": "Typing...",
        "canceling": "Canceling...",
        "cancelled": "Canceled.",
        "source_hotkey": "emergency hotkey",
        "source_button": "emergency button",
        "emergency_triggered": "Emergency stop triggered by {source}. Stopping...",
        "emergency_done": "Emergency-stopped by {source}.",
        "input_failed": "Input failed: {error}",
        "input_done": "Done. Typed {count} characters.",
        "error_no_text": "Paste the text to type first.",
        "error_numeric": "{name} must be a number.",
        "error_non_negative": "{name} cannot be less than 0.",
        "error_random_range": "The minimum random character delay cannot exceed the maximum.",
        "error_invalid_newline": "Choose a valid newline mode.",
    },
}


def language_code(display: str) -> str:
    return DISPLAY_TO_LANGUAGE.get(display, DEFAULT_LANGUAGE)


def language_display(code: str) -> str:
    return LANGUAGE_DISPLAY.get(code, LANGUAGE_DISPLAY[DEFAULT_LANGUAGE])


def text(language: str, key: str, **kwargs: object) -> str:
    template = STRINGS.get(language, STRINGS[DEFAULT_LANGUAGE]).get(key, STRINGS[DEFAULT_LANGUAGE][key])
    return template.format(**kwargs)


def newline_label(language: str, mode: str) -> str:
    labels = NEWLINE_LABELS.get(language, NEWLINE_LABELS[DEFAULT_LANGUAGE])
    return labels.get(mode, NEWLINE_LABELS[DEFAULT_LANGUAGE][NEWLINE_ENTER])


def newline_labels(language: str) -> tuple[str, ...]:
    labels = NEWLINE_LABELS.get(language, NEWLINE_LABELS[DEFAULT_LANGUAGE])
    return tuple(labels.values())


def newline_mode_from_label(language: str, label: str) -> str | None:
    labels = NEWLINE_LABELS.get(language, NEWLINE_LABELS[DEFAULT_LANGUAGE])
    for mode, display in labels.items():
        if display == label:
            return mode
    return None
