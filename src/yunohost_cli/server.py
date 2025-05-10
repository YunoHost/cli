#!/usr/bin/env python3

import logging
from typing import Any

import requests

from .config import Config


class Server:
    def __init__(self, name: str) -> None:
        self.name = name
        self.session = requests.Session()

    def login(self) -> bool:
        server_config = Config().config["servers"][self.name]
        data = {
            "username": server_config["username"],
            "password": server_config["password"],
        }
        try:
            result = self.post("/login", data=data)
            return result.status_code == 200
        except requests.RequestException as err:
            logging.error(err)
            return False

    def real_url(self, url: str) -> str:
        base = Config().config["servers"][self.name]["hostname"]
        api_path = "/yunohost/api/"
        return "https://" + f"{base}{api_path}{url}".replace("//", "/")

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        return self.session.request(method, self.real_url(url), **kwargs)

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        return self.session.get(self.real_url(url), **kwargs)

    def post(self, url: str, **kwargs: Any) -> requests.Response:
        return self.session.post(self.real_url(url), **kwargs)
