#!/usr/bin/env python3

import json
import logging
import ssl
from typing import Any

import httpx
from httpx_sse import aconnect_sse
from packaging.version import Version

from .cli import show_sse_log
from .config import Config


class Server:
    def __init__(self, name: str, secure: bool) -> None:
        self.name = name

        ssl_ctx = ssl.create_default_context()
        timeout = httpx.Timeout(
            10.0,
            connect=10,
            read=1000,
            write=10,
        )
        self.session = httpx.AsyncClient(
            timeout=timeout,
            verify=ssl_ctx if secure else False,
            follow_redirects=True,
        )

    async def login(self, force: bool = False) -> bool:
        server_config = Config().config["servers"][self.name]
        server_cache_file = Config().cache_dir / self.name
        if force:
            server_cache_file.unlink(missing_ok=True)
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
            result = await self.post("/login", data=data)
            if result.status_code != 200:
                return False
            server_cache_file.write_text(result.cookies["yunohost.admin"])
            return True
        except httpx.RequestError as err:
            logging.error(err)
            return False

    async def assert_version(self) -> bool:
        version = (await self.get("/versions")).json()["yunohost"]["version"]
        if Version(version) < Version("12.1.0"):
            logging.error(
                f"Your server is too old! (server version={version}, required>=12.1)"
            )
            return False
        return True

    def real_url(self, url: str) -> str:
        base = Config().config["servers"][self.name]["hostname"]
        api_path = "/yunohost/api/"
        return "https://" + f"{base}{api_path}{url}".replace("//", "/")

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        return await self.session.request(method, self.real_url(url), **kwargs)

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.session.get(self.real_url(url), **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.session.post(self.real_url(url), **kwargs)

    async def sse_logs(self) -> None:
        sse_uri = self.real_url("/sse")

        try:
            async with aconnect_sse(self.session, "GET", sse_uri) as event_source:
                async for sse in event_source.aiter_sse():
                    if not sse.data:
                        continue
                    data = json.loads(sse.data)
                    try:
                        show_sse_log(sse.event, data)
                    except Exception as err:
                        print(f"Error while parsing the sse logs: {err}")
        except:
            pass
