#!/usr/bin/env python3

import argparse
import json
import logging
import sys

import yaml

from .actionsmap import ActionsMap
from .config import Config
from .server import Server

__all__ = ["Config"]


def set_logging_level_from_int(value: int):
    levels = [logging.WARNING, logging.INFO, logging.DEBUG]
    level = levels[max(0, min(value, len(levels) - 1))]
    logging.getLogger().setLevel(level)


def cli_auth(args: argparse.Namespace, config: Config, server: Server) -> None:
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


def cli_test(args: argparse.Namespace, config: Config, server: Server) -> None:
    if server.login():
        logging.info("Authentication successful")
    else:
        logging.error("Could not authenticate!")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser("ynh")
    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument("-s", "--server-name", type=str, default="default")
    mainsub = parser.add_subparsers(dest="category", required=True)

    actions = ActionsMap()
    actions.fill_parser(mainsub)

    # add_args_from_actionsmap(mainsub, actions.map)

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
            cli_auth(args, config, server)
        if args.action == "test":
            cli_test(args, config, server)
        return

    server.login()
    args.func(args, server)
