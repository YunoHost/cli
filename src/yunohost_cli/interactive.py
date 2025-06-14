#!/usr/bin/env python3

import argparse
import json
import logging
from typing import Any

from .cli import prompt
from .server import Server

async def ask_until_valid(arg: dict[str, Any]):
    # Not yet implemented
    value = await prompt(
        arg["ask"], helptext=arg["help"], completions=arg.get("choices"), visible=not arg["redact"]
    )
    return value

async def app_install(server: Server, cli_args: argparse.Namespace) -> None:
    # method, uri, params = cli_args.func(cli_args)
    logging.debug(cli_args)
    app: str = cli_args.app

    install_args: dict[str, str] = {}
    install_args_str: str = cli_args.args or ""
    for arg in install_args_str.removeprefix("?").split("&"):
        if not arg:
            continue
        key, value = arg.split("=", maxsplit=1)
        install_args[key] = value

    # First retrieve args
    manifest_req = await server.get("/apps/manifest", params={"app": app})
    manifest_req.raise_for_status()
    manifest = manifest_req.json()
    manifest_args: list[dict[str, Any]] = manifest["install"]

    for arg in manifest_args:
        if arg["id"] not in install_args:
            install_args[arg["id"]] = await ask_until_valid(arg)

    print("would run install with:")
    print(json.dumps(install_args, indent=4))
