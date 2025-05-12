#!/usr/bin/env python3

import logging
import ssl
from typing import Any
import datetime
from packaging.version import Version
import json
import httpx
from httpx_sse import aconnect_sse

from .config import Config

from .prints import pretty_date


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
            logging.error(f"Your server is too old! (server version={version}, required>=12.1)")
            return False
        return True

    def real_url(self, url: str) -> str:
        base = Config().config["servers"][self.name]["hostname"]
        api_path = "/yunohost/api/"
        return "https://" + f"{base}{api_path}{url}".replace("//", "/")

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        result = await self.session.request(method, self.real_url(url), **kwargs)
        await self.session.aclose()
        return result

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        result = await self.session.get(self.real_url(url), **kwargs)
        await self.session.aclose()
        return result

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        result = await self.session.post(self.real_url(url), **kwargs)
        await self.session.aclose()
        return result

    async def sse_logs(self) -> None:
        sse_uri = self.real_url("/sse")

        try:
            async with aconnect_sse(self.session, "GET", sse_uri) as event_source:
                async for sse in event_source.aiter_sse():
                    if not sse.data:
                        continue
                    data = json.loads(sse.data)
                    timestamp = datetime.datetime.utcfromtimestamp(data.get("timestamp") or 0)
                    title = data.get("title")
                    msg = data.get("msg")
                    started_by = data.get("started_by")

                    if sse.event ==  "start":
                        print(f"[{pretty_date(timestamp)}] {title}... (Started by {started_by})")
                    if sse.event == "msg":
                        print(f"[{pretty_date(timestamp)}] {msg}")

        except:
            pass
