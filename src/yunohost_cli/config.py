#!/usr/bin/env python3

from pathlib import Path
from typing import Any

import platformdirs
import toml

from .utils import Singleton


class Config(metaclass=Singleton["Config"]):  # type: ignore  # see https://github.com/python/mypy/issues/11672
    def __init__(self) -> None:
        self.config_dir = Path(platformdirs.user_config_dir("yunohost"))
        self.cache_dir = Path(platformdirs.user_cache_dir("yunohost"))
        self.config_path = self.config_dir / "cli.toml"
        self.config: dict[str, Any] = {"version": 1}
        self._init()
        self._read()

    def server_add(self, name: str, hostname: str, username: str, password: str) -> None:
        if "servers" not in self.config:
            self.config["servers"] = {}

        self.config["servers"][name] = {
            "hostname": hostname,
            "username": username,
            "password": password,
        }

        self._save()

    def server_remove(self, name: str) -> None:
        if name in self.config["servers"]:
            del self.config["servers"][name]
        self._save()

    def _init(self) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        if not self.config_path.exists():
            self._save()

    def _read(self) -> None:
        self.config = toml.load(self.config_path.open("r"))

    def _save(self) -> None:
        toml.dump(self.config, self.config_path.open("w"))
