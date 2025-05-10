#!/usr/bin/env python3

import argparse
import json
import logging
import sys
from typing import Any

import yaml

from .actionsmap import ActionsMap
from .config import Config
from .server import Server

__all__ = ["Config"]


def set_logging_level_from_int(value: int):
    levels = [logging.WARNING, logging.INFO, logging.DEBUG]
    level = levels[max(0, min(value, len(levels) - 1))]
    logging.getLogger().setLevel(level)


def add_args_from_actionsmap(subparsers, actionsmap: dict[Any, Any]) -> None:
    for category, category_descr in actionsmap.items():
        if category.startswith("_"):
            continue
        catpars = subparsers.add_parser(category, help=category_descr["category_help"])
        catsubpars = catpars.add_subparsers(dest="action", required=True)
        for action, action_descr in category_descr.get("actions", {}).items():
            argpars = catsubpars.add_parser(action, help=action_descr["action_help"])
            for argument, arg_descr in action_descr.get("arguments", {}).items():
                full_arg = arg_descr.get("full")
                if isinstance(argument, int) and argument < 0:
                    argument = f"-{-argument}"
                args = [argument, full_arg] if full_arg else [argument]
                argpars.add_argument(
                    *args,
                    help=arg_descr.get("help"),
                    action=arg_descr.get("action"),
                    # nargs=arg_descr.get("nargs")
                )


def main() -> None:
    parser = argparse.ArgumentParser("ynh")
    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument("-s", "--server-name", type=str, default="default")
    mainsub = parser.add_subparsers(dest="category", required=True)

    actions = ActionsMap()
    add_args_from_actionsmap(mainsub, actions.map)

    cli = mainsub.add_parser("cli", help="CLI specific stuff")
    clisub = cli.add_subparsers(dest="action", required=True)
    auth = clisub.add_parser("auth", help="Authenticate against a YunoHost server")
    auth.add_argument("host", type=str)
    auth.add_argument("login", type=str)
    auth.add_argument("password", type=str)
    clisub.add_parser("test", help="Check authentication")

    args = parser.parse_args()

    set_logging_level_from_int(args.verbose)

    config = Config()

    server = Server(args.server_name)

    if args.category == "cli":
        if args.action == "auth":
            if args.server_name in config.config.get("servers", {}):
                logging.error(f"Server {args.server_name} already present in config!")
                sys.exit(1)

            config.server_add(args.server_name, args.host, args.login, args.password)
            if server.login():
                logging.info("Authentication successful")
            else:
                logging.error("Could not authenticate!")
                config.server_remove(args.server_name)
                sys.exit(1)

        if args.action == "test":
            if server.login():
                logging.info("Authentication successful")
            else:
                logging.error("Could not authenticate!")
                sys.exit(1)

        return

    action = actions.map[args.category]["actions"][args.action]
    logging.debug(f"Running {action}")

    uri = action["api"].split(" ")[1]

    server.login()
    result = server.get(uri)
    result.raise_for_status()

    print(yaml.dump(json.loads(result.text)))
