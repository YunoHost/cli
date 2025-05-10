#!/usr/bin/env python3

from pathlib import Path

import yaml


def find_actionsmap() -> Path:
    # First search for local server
    local_server = Path("/usr/share/yunohost/actionsmap.yml")
    fallback = Path(__file__).resolve().parent / "actionsmap.yml"

    if local_server.exists():
        return local_server
    else:
        return fallback


class ActionsMap:
    def __init__(self) -> None:
        self.map = yaml.safe_load(find_actionsmap().open("r"))
