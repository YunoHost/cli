#!/usr/bin/env python3

import json
import logging
import ssl
from enum import Enum
from typing import Any, Callable

import httpx
from httpx_sse import aconnect_sse
from packaging.version import Version

from .config import Config


class SSEEvent:
    class Type(Enum):
        recent_history = 1
        heartbeat = 2
        msg = 10
        toast = 11
        start = 20
        end = 21

    def __init__(self, type: str, data: dict[str, Any]):
        self.type = SSEEvent.Type[type]
        self.timestamp: float = data.get("timestamp", data.get("started_at", 0.0))
        self.operation: str | None = data.get("operation_id", data.get("current_operation", None))
        self.level: str | None = None
        self.msg: str = ""
        self.title: str = ""
        self.started_by: str | None = None
        self.success: bool | None = None
        self.cmdline: str | None = None

        if self.type in [self.Type.msg, self.Type.toast]:
            self.as_msg(data)
        if self.type == self.Type.start:
            self.as_start(data)
        if self.type == self.Type.end:
            self.as_end(data)
        if self.type == self.Type.recent_history:
            self.as_end(data)
        if self.type == self.Type.heartbeat:
            self.as_heartbeat(data)

    def as_msg(self, data: dict[str, Any]) -> None:
        self.level = data["level"]
        self.msg = data["msg"]

    def as_start(self, data: dict[str, Any]) -> None:
        self.title = data["title"]
        self.started_by = data["started_by"]

    def as_end(self, data: dict[str, Any]) -> None:
        self.success = data["success"]
        self.msg = data["errormsg"]

    def as_heartbeat(self, data: dict[str, Any]) -> None:
        self.cmdline = data["cmdline"]


class Server:
    def __init__(self, name: str, secure: bool) -> None:
        self.name = name
        self.sse_handler: Callable[[SSEEvent], None] | None = None

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
            del self.session.cookies["yunohost.admin"]
        if server_cache_file.exists():
            self.session.cookies["yunohost.admin"] = server_cache_file.read_text().strip()
            return True

        data = {
            "username": server_config["username"],
            "password": server_config["password"],
        }
        try:
            logging.info("Logging in...")
            result = await self.post("/login", data=data)
            if result.is_error:
                return False
            server_cache_file.write_text(result.cookies["yunohost.admin"])
            return True
        except httpx.RequestError as err:
            logging.error(err)
            return False

    async def assert_version(self) -> bool:
        result = await self.get("/versions")
        result.raise_for_status()
        version = result.json()["yunohost"]["version"]
        if Version(version) < Version("12.1.0"):
            logging.error(f"Your server is too old! (server version={version}, required>=12.1)")
            return False
        return True

    def real_url(self, url: str) -> str:
        base = Config().config["servers"][self.name]["hostname"]
        api_path = "/yunohost/api/"
        return "https://" + f"{base}{api_path}{url}".replace("//", "/")

    async def request(self, method: str, url: str, retry_auth: bool = True, **kwargs: Any) -> httpx.Response:
        result = await self.session.request(method, self.real_url(url), **kwargs)
        if result.status_code == httpx.codes.UNAUTHORIZED and retry_auth:
            logging.warning("Authentification seems expired, trying to log in again...")
            await self.login(force=True)
            result = await self.session.request(method, self.real_url(url), **kwargs)
        return result

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", url, **kwargs)

    def set_sse_log_handler(self, handler: Callable[[SSEEvent], None]) -> None:
        self.sse_handler = handler

    async def sse_logs(self) -> None:
        sse_uri = self.real_url("/sse")

        try:
            async with aconnect_sse(self.session, "GET", sse_uri) as event_source:
                async for sse in event_source.aiter_sse():
                    if not self.sse_handler:
                        continue
                    if not sse.data:
                        continue
                    data = json.loads(sse.data)
                    try:
                        if self.sse_handler:
                            self.sse_handler(SSEEvent(sse.event, data))
                    except Exception as err:
                        print(f"Error while parsing the sse logs: {err}")
        except Exception as err:
            logging.debug(f"SSE failed with {err}")
