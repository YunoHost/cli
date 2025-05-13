#!/usr/bin/env python3

import datetime
import logging
import os
from typing import Any


class Color:
    # FIXME use python lib like colored?
    START = "\033[{:d}m\033[1m"
    END = "\033[m"

    _COLORS: dict[str, int] = {
        "red": 31,
        "green": 32,
        "yellow": 33,
        "blue": 34,
        "purple": 35,
        "cyan": 36,
        "white": 37,
    }

    for _color, _code in _COLORS.items():
        vars()[_color] = lambda text, code=_code: Color.colorize(text, code)
        vars()[_color.upper()] = lambda text, code=_code: Color.colorize(text, code)

    @classmethod
    def colorize(cls, text: str, color: int) -> str:
        if os.isatty(1):
            return f"{cls.START.format(color)}{text}{cls.END}"
        return text


def level_str(level: str) -> str:
    """Display a message"""
    if level == "success":
        return Color.green(f"[{level}]\t")
    if level == "info":
        return Color.blue(f"[{level}]\t")
    elif level == "warning":
        return Color.yellow(f"[{level}]\t")
    elif level == "error":
        return Color.red(f"[{level}]\t")
    return ""


def pretty_date(date: float) -> str:
    timestamp = datetime.datetime.utcfromtimestamp(date)
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


def show_sse_log(type: str, data: dict[str, Any]) -> None:
    logging.debug(f"{type=}, {data=}")

    if type in ["recent_history", "heartbeat"]:
        return

    if type in ["start"]:
        date = float(data.get("timestamp", 0))
        title = data["title"]
        author = data["started_by"]
        print(f"[{pretty_date(date)}] {title}... (Started by {author})")
        return

    if type in ["msg"]:
        level: str = data["level"]
        msg: str = data["msg"]
        print(f"{level_str(level)}{msg}")
        return

    logging.error(f"Unknown SSE log type {type}")


def prompt(
    message: str,
    color: str = "blue",
    prefill: str = "",
    multiline: bool = False,
    help: str = "",
    completions: list[str] = [],
    visible: bool = True,
    confirm: bool = False,
) -> str:
    """Prompt for a value"""

    # TODO: multiline

    if not os.isatty(1):
        raise RuntimeError("Not a tty, can't do interactive prompts")

    import prompt_toolkit
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.formatted_text import OneStyleAndTextTuple
    from prompt_toolkit.styles import Style

    completer = WordCompleter(completions)

    style = Style.from_dict(
        {
            "": "",
            "message": f"#ansi{color} bold",
        }
    )

    def help_bottom_toolbar():
        return [("class:", help)]

    colored_message: list[OneStyleAndTextTuple] = [
        ("class:message", message),
        ("class:", ": "),
    ]

    value = prompt_toolkit.prompt(
        colored_message,
        bottom_toolbar=help_bottom_toolbar if help else None,
        style=style,
        default=prefill,
        completer=completer,
        complete_while_typing=True,
        is_password=not visible,
    )

    if confirm:
        confirm_value = prompt(
            message,
            color=color,
            prefill=prefill,
            multiline=multiline,
            help=help,
            completions=completions,
            visible=visible,
            confirm=False,
        )

        if confirm_value != value:
            raise ValueError("values_mismatch")

    return value
