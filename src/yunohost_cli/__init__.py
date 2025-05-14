#!/usr/bin/env python3

import argparse
import asyncio
import logging
import sys

from .actionsmap import ActionsMap
from .config import Config
from .server import Server


def set_logging_level_from_int(value: int) -> None:
    levels = [logging.WARNING, logging.INFO, logging.DEBUG]
    level = levels[max(0, min(value, len(levels) - 1))]
    logging.getLogger().setLevel(level)


async def cli_auth(args: argparse.Namespace, config: Config, server: Server) -> None:
    if args.server_name in config.config.get("servers", {}):
        logging.error(f"Server {args.server_name} already present in config!")
        sys.exit(1)

    config.server_add(args.server_name, args.host, args.login, args.password)
    if await server.login(force=True):
        print("Authentication successful")
    else:
        logging.error("Could not authenticate!")
        config.server_remove(args.server_name)
        sys.exit(1)


async def cli_test(args: argparse.Namespace, config: Config, server: Server) -> None:
    if await server.login():
        logging.info("Authentication successful")
    else:
        logging.error("Could not authenticate!")
        sys.exit(1)


async def async_main() -> None:
    parser = argparse.ArgumentParser("ynh")
    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument("-s", "--server-name", type=str, default="default")
    parser.add_argument(
        "-o",
        "--output-as",
        type=str,
        help="Output format",
        choices=["json", "plain", "yaml"],
        default="yaml",
    )
    parser.add_argument("-k", "--insecure", action="store_true", default=False, help="Insecure https")

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

    mainsub.add_parser("sse", help="dump logs via SSE")

    args = parser.parse_args()

    set_logging_level_from_int(args.verbose)

    config = Config()

    server = Server(args.server_name, not args.insecure)

    if args.category == "cli":
        if args.action == "auth":
            await cli_auth(args, config, server)
        if args.action == "test":
            await cli_test(args, config, server)
        return

    await server.login()

    if not await server.assert_version():
        return

    if args.category == "sse":
        await server.sse_logs()
        return

    method, uri, params = args.func(args)

    # Start SSE
    request = server.request(method, uri, params=params)
    sse_task = asyncio.create_task(server.sse_logs())
    result = await request
    try:
        sse_task.cancel()
        await sse_task
    except asyncio.CancelledError:
        pass

    if result.is_error:
        print(result, result.text)
        result.raise_for_status()

    # Format and print result
    if args.output_as == "json":
        import json

        from .cli import JSONExtendedEncoder

        print(json.dumps(result.json(), cls=JSONExtendedEncoder, ensure_ascii=False))

    elif args.output_as == "plain":
        from .cli import print_data_plain

        print_data_plain(result.json())

    elif args.output_as == "yaml":
        from .cli import print_data_simpleyaml

        if isinstance(data := result.json(), dict):
            print_data_simpleyaml(result.json())
        else:
            print(data)


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(async_main())
