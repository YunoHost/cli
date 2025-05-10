#!/usr/bin/env python3

import toml
from pathlib import Path
import platformdirs

from .utils import Singleton

APP_NAME = "yunohost-cli"


class Config(metaclass=Singleton):
    def __init__(self) -> None:
        self.config_dir = Path(platformdirs.user_config_dir(APP_NAME))
        self.config_path = self.config_dir / "config.toml"
        self.config: dict = {"version": 1}
        self._init()
        self._read()

    def server_add(self, name: str, hostname: str, username: str, password: str):
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
            del self.config["servers"]


    def _init(self) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        if not self.config_path.exists():
            self._save()

    def _read(self) -> None:
        self.config = toml.load(self.config_path.open("r"))

    def _save(self) -> None:
        toml.dump(self.config, self.config_path.open("w"))
