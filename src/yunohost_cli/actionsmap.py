#!/usr/bin/env python3

from pathlib import Path

import yaml


def find_actionsmap() -> Path:
    # First search for local server
    server_copy = Path("/usr/share/yunohost/actionsmap.yml")
    package_copy = Path(__file__).resolve().parent / "actionsmap.yml"

    if server_copy.exists():
        return server_copy
    else:
        return package_copy


class ActionsMap:
    def __init__(self) -> None:
        self.map = yaml.safe_load(find_actionsmap().open("r"))
