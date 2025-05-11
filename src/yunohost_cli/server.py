#!/usr/bin/env python3

import logging
from typing import Any

import httpx

from .config import Config


class Server:
    def __init__(self, name: str) -> None:
        self.name = name
        self.session = httpx.Client()

    def login(self) -> bool:
        server_config = Config().config["servers"][self.name]
        server_cache_file = Config().cache_dir / self.name
        if server_cache_file.exists():
            self.session.cookies["yunohost.admin"] = (
                server_cache_file.read_text().strip()
            )
            return True

        data = {
            "username": server_config["username"],
            "password": server_config["password"],
        }
        try:
            logging.info("Logging in...")
            result = self.post("/login", data=data)
            if result.status_code != 200:
                return False
            server_cache_file.write_text(result.cookies["yunohost.admin"])
            return True
        except httpx.RequestError as err:
            logging.error(err)
            return False

    def real_url(self, url: str) -> str:
        base = Config().config["servers"][self.name]["hostname"]
        api_path = "/yunohost/api/"
        return "https://" + f"{base}{api_path}{url}".replace("//", "/")

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        return self.session.request(method, self.real_url(url), **kwargs)

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.session.get(self.real_url(url), **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.session.post(self.real_url(url), **kwargs)
