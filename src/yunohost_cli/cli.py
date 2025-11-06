#!/usr/bin/env python3

import argparse
import datetime
import logging
import os
from json.encoder import JSONEncoder
from typing import Any

from httpx import Response
from rich._log_render import LogRender
from rich.console import Console
from rich.style import Style
from rich.table import Table
from rich.text import Text

from .server import SSEEvent

CONSOLE = Console()

LOGGER = LogRender(
    show_time=True,
    show_level=True,
    show_path=False,
)


def level_str(level: str) -> Text:
    """Display a message"""
    styles = {
        "success": Style(color="green"),
        "info": Style(color="blue"),
        "warning": Style(color="yellow"),
        "error": Style(color="red", bold=True),
    }
    style = styles[level]
    text = Text.styled(f"[{level}]".ljust(10), style)
    return text


def pretty_date(date: float) -> Text:
    timestamp = datetime.datetime.fromtimestamp(date, tz=datetime.timezone.utc)
    return Text.styled(timestamp.strftime("[%Y-%m-%d %H:%M:%S]"), "log.time")


def safe_quote(string: str | None) -> str:
    return f"[repr.str]'{string}'[reset]"


OPERATIONS: dict[str, SSEEvent] = {}


def show_sse_log(event: SSEEvent, history: bool = False) -> None:
    if logging.DEBUG >= logging.getLogger().getEffectiveLevel():
        CONSOLE.log(event.__dict__)

    if event.type in [event.Type.heartbeat]:
        return

    dateprint = pretty_date(event.timestamp)

    if event.type in [event.Type.recent_history]:
        if not history:
            return
        assert event.operation is not None
        levelprint = level_str("running" if event.success == "?" else "success" if event.success else "error")
        msg = f"Operation {safe_quote(event.title)}"
        CONSOLE.print("Recent history", dateprint, levelprint, msg, f"(started by {event.started_by})")
        return

    if event.type in [event.Type.start]:
        assert event.operation is not None
        OPERATIONS[event.operation] = event
        CONSOLE.print(dateprint, level_str("info"), f"{event.title}... (Started by {event.started_by})")
        return

    if event.type in [event.Type.end]:
        start_event: SSEEvent | None = OPERATIONS.pop(event.operation or "", None)

        verb = "finished" if event.success else "failed"

        if start_event:
            msg = f"Operation {safe_quote(start_event.title)} started by {start_event.started_by} {verb}!"
        else:
            msg = f"Operation {safe_quote(event.operation)} {verb} (sorry, no more info available)!"

        levelprint = level_str("success" if event.success else "error")

        CONSOLE.print(dateprint, levelprint, msg)
        if not event.success:
            CONSOLE.print(dateprint, levelprint, event.msg)
        return

    if event.type in [event.Type.msg, event.Type.toast]:
        assert event.level is not None
        CONSOLE.print(dateprint, level_str(event.level), event.msg)
        return

    logging.error(f"Unknown SSE log kind {event.type}")


async def prompt(
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

    session: prompt_toolkit.PromptSession[str] = prompt_toolkit.PromptSession()
    value = await session.prompt_async(
        colored_message,
        bottom_toolbar=help_bottom_toolbar if helptext else None,
        style=style,
        default=prefill,
        completer=completer,
        complete_while_typing=True,
        is_password=not visible,
    )

    if confirm:
        confirm_value = await prompt(
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

    elif isinstance(data, (int, float)):
        strepr = str(data)

    elif data is None:
        strepr = "null"

    else:
        raise ValueError(f"repr_simple can't take values of type {type(data)}")

    return strepr


def print_data_simpleyaml(data: Any, depth: int = 0, parent: str = "") -> None:
    """Print in a pretty way a dictionary recursively

    Print a dictionary recursively with colors to the standard output.

    Keyword arguments:
        - data -- The dictionary to print
        - depth -- The recursive depth of the dictionary

    """

    _depth = 0

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
            print("  " * _depth, end="")
            CONSOLE.print(Text.styled(repr_simple(key), Style(color="magenta")), end="")
            print(":", end="")
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


def print_smart_table(result: dict[str, Any]) -> None:
    values = next(iter(result.values()))
    table = Table(show_header=True, header_style="bold green")

    if isinstance(values, dict):
        table.add_column("id")
        columns = list(next(iter(values.values())))
        for column in columns:
            table.add_column(column)

        for id, row in values.items():
            row_data = [id] + [str(row.get(column, "")) for column in columns]
            table.add_row(*row_data)

    elif isinstance(values, list):
        columns = values[0].keys()
        for column in columns:
            table.add_column(column)

        for row in values:
            row_data = [str(row.get(column, "")) for column in columns]
            table.add_row(*row_data)

    CONSOLE.print(table)


def print_smart_table_2d(result: dict[str, Any]) -> None:
    values = next(iter(result.values()))
    assert isinstance(values, dict)

    table = Table(show_header=True, header_style="bold green")

    rows = list(next(iter(values.values())).keys())
    table.add_column("", justify="right", vertical="middle", style="bold green", no_wrap=True)
    for name in values.keys():
        table.add_column(name)

    for row in rows:
        row_data = [row]
        for name, valuedict in values.items():
            value = valuedict.get(row, None)
            if isinstance(value, list):
                row_data.append("\n".join(sorted(value)))
            elif isinstance(value, str):
                row_data.append(value)
            elif value is None:
                row_data.append("'None'")
            else:
                raise RuntimeError(f"Unsupported value type {type(value)}")
        table.add_row(*row_data)

    CONSOLE.print(table)


def print_result(result: Response | None, mode: str, args: argparse.Namespace) -> None:
    if result is None:
        return

    if result.is_error:
        print(result, result.text)
        result.raise_for_status()

    data = result.json()

    # Format and print result
    if data is None:
        return

    if mode == "human":
        if isinstance(data, dict):
            if next(iter(data.keys())) in ["users", "apps", "permissions"]:
                print_smart_table(data)
            elif args.category == "settings" and args.action == "list":
                print_smart_table(
                    {
                        "settings": {
                            id: {"value": values.get("value", ""), "ask": values["ask"]} for id, values in data.items()
                        }
                    }
                )
            elif next(iter(data.keys())) in ["groups"]:
                print_smart_table_2d(data)
            else:
                print_data_simpleyaml(data)
        else:
            print(data)

    elif mode == "json":
        import json

        print(json.dumps(data, cls=JSONExtendedEncoder, ensure_ascii=False))

    elif mode == "plain":
        print_data_plain(data)

    elif mode == "yaml":
        if isinstance(data, dict):
            print_data_simpleyaml(data)
        else:
            print(data)
