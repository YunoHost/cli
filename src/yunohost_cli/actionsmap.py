#!/usr/bin/env python3

import platformdirs
import argparse
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any
import json

from .server import Server

if TYPE_CHECKING:
    _SubparserType = argparse._SubParsersAction[argparse.ArgumentParser]
else:
    _SubparserType = Any


def find_actionsmap() -> Path:
    # First search for local server
    server_copy = Path("/usr/share/yunohost/actionsmap.yml")
    package_copy = Path(__file__).resolve().parent / "actionsmap.yml"

    if server_copy.exists():
        return server_copy
    else:
        return package_copy


class MapActionArg:
    def __init__(self, name: str | int, config: dict[Any, Any]) -> None:
        self.help: str = config.get("help", "")
        self.config = config

        # workaround for -4, -6
        name = f"-{-name}" if isinstance(name, int) else name

        self.args = [name]
        if "full" in config:
            self.args.append(config["full"])

        if len(self.args) == 2:
            self.varname = self.args[1].removeprefix("--")
        else:
            self.varname = self.args[0].removeprefix("-").removeprefix("-")

    def fill_parser(self, subparser: argparse.ArgumentParser) -> None:
        kwargs = {}
        if action := self.config.get("action"):
            kwargs["action"] = action
        if nargs := self.config.get("nargs"):
            kwargs["nargs"] = nargs

        subparser.add_argument(
            *self.args,
            help=self.help,
            **kwargs,
        )

    def value(self, args: argparse.Namespace) -> Any:
        value = vars(args)[self.varname]

        return value


class MapAction:
    def __init__(self, path: list[str], config: dict[str, Any]) -> None:
        self.path = path
        self.name = path[-1]
        self.help = config.get("action_help")
        self.no_help = config.get("hide_in_help", False)
        self.config = config
        self.args = [
            MapActionArg(name, config)
            for name, config in config.get("arguments", {}).items()
        ]

    def fill_parser(self, subparser: _SubparserType) -> None:
        if self.config.get("deprecated", False):
            return
        if self.no_help:
            parser = subparser.add_parser(self.name)
        else:
            parser = subparser.add_parser(self.name, help=self.help)

        for arg in self.args:
            arg.fill_parser(parser)
        parser.set_defaults(func=self.run)

    def run(self, args: argparse.Namespace, server: Server) -> None:
        logging.debug(f"Running '{' '.join(self.path)}' ({self.help})")

        uris = self.config["api"]
        params = {}

        def handle_arg(arg: MapActionArg) -> None:
            nonlocal uris
            value = arg.value(args)
            if value is None or value == []:
                return

            replacestring = f"<{arg.varname}>"
            if isinstance(value, list):
                valuestring = "%20".join(value)
            else:
                valuestring = str(value)

            if isinstance(uris, str):
                if replacestring in uris:
                    uris = uris.replace(replacestring, valuestring)
                    return

            # choose between uriss
            if isinstance(uris, list):
                if replacestring in uris[0] and replacestring not in uris[1]:
                    uris = uris[0].replace(replacestring, valuestring)
                    return
                elif replacestring in uris[1] and replacestring not in uris[0]:
                    uris = uris[1].replace(replacestring, valuestring)
                    return

            params[arg.varname] = value

        for arg in self.args:
            handle_arg(arg)

        if isinstance(uris, list):
            if "<" in uris[0]:
                uris = uris[1]
            else:
                uris = uris[0]

        method, uri = uris.split(" ")
        result = server.request(method, uri, params=params)
        result.raise_for_status()

        import ryaml
        print(ryaml.dumps(result.json()))


class MapCategory:
    def __init__(self, path: list[str], config: dict[str, Any]) -> None:
        self.path = path
        self.help: str = (
            config.get("category_help") or config.get("subcategory_help") or ""
        )
        self.subcategories = {
            name: MapCategory([*path, name], config)
            for name, config in config.get("subcategories", {}).items()
        }
        self.actions = {
            name: MapAction([*path, name], config)
            for name, config in config.get("actions", {}).items()
        }

    def fill_parser(self, subparser: _SubparserType) -> None:
        self.parser: argparse.ArgumentParser = subparser.add_parser(
            self.path[-1], help=self.help
        )
        subparsers = self.parser.add_subparsers(required=True)
        for action in self.actions.values():
            action.fill_parser(subparsers)
        for subcat in self.subcategories.values():
            subcat.fill_parser(subparsers)


class ActionsMap:
    def __init__(self) -> None:
        self.cached_read()

        self.categories = {
            name: MapCategory([name], config)
            for name, config in self.map.items()
            if not name.startswith("_")
        }

    def cached_read(self) -> None:
        actionsmap = find_actionsmap()
        map_cache = Path(platformdirs.user_cache_dir("yunohost")) / "actionsmap.json"

        if map_cache.exists() and map_cache.stat().st_mtime > actionsmap.stat().st_mtime:
            self.map = json.load(map_cache.open("r"))
        else:
            import yaml
            self.map = yaml.safe_load(find_actionsmap().open("r"))
            map_cache.parent.mkdir(parents=True, exist_ok=True)
            json.dump(self.map, map_cache.open("w"), indent=0)


    def fill_parser(self, subparser: _SubparserType) -> None:
        for category in self.categories.values():
            category.fill_parser(subparser)
