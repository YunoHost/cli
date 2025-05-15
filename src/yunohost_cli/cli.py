#!/usr/bin/env python3

import datetime
import logging
import os
from json.encoder import JSONEncoder
from typing import Any
from httpx import Response

from colored import Fore, Style


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


def show_sse_log(kind: str, data: dict[str, Any]) -> None:
    logging.debug(f"{kind=}, {data=}")

    if kind in ["recent_history", "heartbeat"]:
        return

    if kind in ["start"]:
        date = float(data.get("timestamp", 0))
        title = data["title"]
        author = data["started_by"]
        print(f"[{pretty_date(date)}] {title}... (Started by {author})")
        return

    if kind in ["end"]:
        # print(data)
        success = data["success"]
        date = float(data.get("timestamp", 0))

        if success:
            author = data["started_by"]
            print(f"{level_str('success')}Operation finished (Started by {author})")
        else:
            errormsg = data["errormsg"]
            print(f"{level_str('error')}Operation failed!")
            print(f"{level_str('error')}{errormsg}")
        return

    if kind in ["msg"]:
        level: str = data["level"]
        msg: str = data["msg"]
        print(f"{level_str(level)}{msg}")
        return

    logging.error(f"Unknown SSE log kind {kind}")


def prompt(
    message: str,
    color: str = "blue",
    prefill: str = "",
    multiline: bool = False,
    helptext: str = "",
    completions: list[str] | None = None,
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

    completer = WordCompleter(completions or [])

    style = Style.from_dict(
        {
            "": "",
            "message": f"#ansi{color} bold",
        }
    )

    def help_bottom_toolbar() -> list[OneStyleAndTextTuple]:
        return [("class:", helptext)]

    colored_message: list[OneStyleAndTextTuple] = [
        ("class:message", message),
        ("class:", ": "),
    ]

    value = prompt_toolkit.prompt(
        colored_message,
        bottom_toolbar=help_bottom_toolbar if helptext else None,
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
            helptext=helptext,
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
    if isinstance(data, tuple | set):
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

    def repr_simple(data: str | bool | None) -> str:
        if isinstance(data, str):
            strepr = data
            if data == "":
                strepr = "''"
            if ":" in data:
                strepr = f'"{data.replace('"', '\\"')}"'
            if data.isdigit():
                strepr = f"'{data}'"
            if data in ["yes", "no"]:
                strepr = f"'{data}'"

        elif isinstance(data, bool):
            strepr = "true" if data else "false"

        elif data is None:
            strepr = "null"

        else:
            raise ValueError(f"repr_simple can't take values of type {type(data)}")

        return strepr

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

    if isinstance(data, str) and "\n" in data:
        if parent == "dict":
            print("|")
            _depth = depth
        for line in data.split("\n"):
            print(f"{'  ' * depth}{repr_simple(line)}")
            _depth = depth
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

    def default(self, o: Any) -> Any:
        """Return a serializable object"""

        # Convert compatible containers into list
        if isinstance(o, set):
            return list(o)

        try:
            iterable = iter(o)
        except TypeError:
            pass
        else:
            return list(iterable)

        # Return the repr for object that json can't encode
        logging.warning(f"cannot properly encode in JSON the object {type(o)}, returned repr is: {{o}}")
        return repr(o)


def print_result(result: Response, mode: str) -> None:
    if result.is_error:
        print(result, result.text)
        result.raise_for_status()

    data = result.json()

    # Format and print result
    if data is None:
        return

    if mode == "json":
        import json
        print(json.dumps(data, cls=JSONExtendedEncoder, ensure_ascii=False))

    elif mode == "plain":
        print_data_plain(data)

    elif mode == "yaml":
        if isinstance(data, dict):
            print_data_simpleyaml(data)
        else:
            print(data)
