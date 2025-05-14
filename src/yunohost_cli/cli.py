#!/usr/bin/env python3

import datetime
import logging
import os
from collections import OrderedDict
from typing import Any, Callable
from json.encoder import JSONEncoder

from colored import Fore, Back, Style


def level_str(level: str) -> str:
    """Display a message"""
    length = len(Fore.green) + len(Style.reset) + 10
    if level == "success":
        return f"{Fore.green}[{level}]{Style.reset}".ljust(length)
    if level == "info":
        return f"{Fore.blue}[{level}]{Style.reset}".ljust(length)
    elif level == "warning":
        return f"{Fore.yellow}[{level}]{Style.reset}".ljust(length)
    elif level == "error":
        return f"{Fore.red}[{level}]{Style.reset}".ljust(length)
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


def print_data_plain(data: Any, depth: int = 0) -> None:
    """Print in a plain way a dictionary recursively

    Print a dictionary recursively for scripting usage to the standard output.

    Output formatting:
      >>> d = {'key': 'value', 'list': [1,2], 'dict': {'key2': 'value2'}}
      >>> print_data_plain(data)
      #key
      value
      #list
      1
      2
      #dict
      ##key2
      value2

    Keyword arguments:
        - data -- The dictionary to print
        - depth -- The recursive depth of the dictionary

    """
    # skip first key printing
    if depth == 0 and (isinstance(data, dict) and len(data) == 1):
        _, data = data.popitem()
    if isinstance(data, (tuple, set)):
        data = list(data)
    if isinstance(data, list):
        for value in data:
            print_data_plain(value, depth + 1)
    elif isinstance(data, dict):
        for key, value in data.items():
            print(f"{'#' * (depth + 1)}{key}")
            print_data_plain(value, depth + 1)
    else:
        print(data)


def print_data_simpleyaml(data: Any, depth: int = 0, parent: str = "") -> None:
    """Print in a pretty way a dictionary recursively

    Print a dictionary recursively with colors to the standard output.

    Keyword arguments:
        - data -- The dictionary to print
        - depth -- The recursive depth of the dictionary

    """

    _depth = 0

    def repr_simple(data) -> str:
        if isinstance(data, str):
            if data == "":
                return "''"
            if ":" in data:
                return f'"{data.replace('"', '\\"')}"'
            if data.isdigit():
                return f"'{data}'"
            if data in ["yes", "no"]:
                return f"'{data}'"

        if isinstance(data, bool):
            return "true" if data else "false"

        if data is None:
            return "null"

        return data

    if isinstance(data, list):
        if len(data) == 0:
            print(" []")
            return
        if parent == "dict":
            print()
            _depth = depth
        if parent == "list":
            print(" ", end="")
        for value in data:
            print(f"{'  ' * (_depth)}-", end="")
            _depth = depth
            print_data_simpleyaml(value, depth + 1, parent="list")
        return

    if isinstance(data, dict):
        if parent == "dict":
            print()
            _depth = depth
        if parent == "list":
            print(" ", end="")
        for key, value in sorted(data.items()):
            print(f"{'  ' * _depth}{Fore.magenta}{repr_simple(key)}{Style.reset}:", end="")
            _depth = depth
            print_data_simpleyaml(value, depth + 1, parent="dict")
        return

    if isinstance(data, str):
        if "\n" in data:
            if parent == "dict":
                print("|")
                _depth = depth
            for index, line in enumerate(data.split("\n")):
                print(f"{'  ' * depth}{repr_simple(line)}")
                depth = depth
            return

    print(f" {repr_simple(data)}")


class JSONExtendedEncoder(JSONEncoder):
    """Extended JSON encoder

    Extend default JSON encoder to recognize more types and classes. It will
    never raise an exception if the object can't be encoded and return its repr
    instead.

    The following objects and types are supported:
        - set: converted into list

    """

    def default(self, o):
        """Return a serializable object"""

        import pytz  # Lazy loading, this takes like 3+ sec on a RPi2 ?!

        # Convert compatible containers into list
        if isinstance(o, set) or (hasattr(o, "__iter__") and hasattr(o, "next")):
            return list(o)

        # Return the repr for object that json can't encode
        logging.warning(f"cannot properly encode in JSON the object {type(o)}, returned repr is: {o}")
        return repr(o)
