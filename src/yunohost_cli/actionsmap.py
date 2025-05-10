#!/usr/bin/env python3

import yaml
from pathlib import Path


class ActionsMap():
    def __init__(self) -> None:
        map_path = Path(__file__).resolve().parent / "actionsmap.yml"
        self.map = yaml.safe_load(map_path.open("r"))
