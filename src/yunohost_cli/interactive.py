#!/usr/bin/env python3

import logging
from typing import Any
import argparse
from .server import Server
from .cli import prompt

import json


async def ask_until_valid()


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
        if arg["id"] in install_args:
            pass

        value = await prompt(
            arg["ask"],
            helptext=arg["help"],
            completions=arg.get("choices"),
            visible=not arg["redact"]
        )
        install_args[arg["id"]] = value


    print("would run install with:")
    print(json.dumps(install_args, indent=4))
