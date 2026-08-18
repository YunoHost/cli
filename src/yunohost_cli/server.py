#!/usr/bin/env python3

import logging
import ssl
from enum import Enum
from typing import Any, Protocol

import httpx2
from packaging.version import Version

from .config import get_config

REQUIRED_SERVER_VERSION = Version("12.1.0")


class SSEEvent:
    class Type(Enum):
        recent_history = 1
        heartbeat = 2
        msg = 10
        toast = 11
        start = 20
        end = 21

    def __init__(self, _type: str, data: dict[str, Any]) -> None:
        self.type = SSEEvent.Type[_type]
        self.timestamp: float = data.get("timestamp", data.get("started_at", 0.0))
        self.operation: str | None = data.get("operation_id", data.get("current_operation"))
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
        # title and started_by are present when in recent_history
        self.title = data.get("title", "")
        self.started_by = data.get("started_by", "")
        # errormsg is ommited when in recent_history
        self.msg = data.get("errormsg", "")

    def as_heartbeat(self, data: dict[str, Any]) -> None:
        self.cmdline = data["cmdline"]


class SSELogHandler(Protocol):
    def __call__(self, event: SSEEvent, *, history: bool = False) -> None: ...


class Server:
    def __init__(self, name: str, *, secure: bool) -> None:
        self.name = name
        self.sse_handler: SSELogHandler | None = None

        ssl_ctx = ssl.create_default_context()
        timeout = httpx2.Timeout(
            10.0,
            connect=10,
            read=1000,
            write=10,
        )
        self.session = httpx2.AsyncClient(
            timeout=timeout,
            verify=ssl_ctx if secure else False,
            follow_redirects=True,
        )

    async def login(self, *, force: bool = False) -> bool:
        server_config = get_config().config["servers"][self.name]
        server_cache_file = get_config().cache_dir / self.name
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
        except httpx2.RequestError as err:
            logging.error(err)
            return False

    async def assert_version(self) -> bool:
        server_cache_file = get_config().cache_dir / f"{self.name}.version"

        # Early exit with cache if we know the server has a supported version
        # to avoid 1 costly request
        if server_cache_file.exists():
            server_version = server_cache_file.read_text().strip()
            logging.debug(f"Cached server version: {server_version}")
            if Version(server_version) >= REQUIRED_SERVER_VERSION:
                return True

        result = await self.get("/versions")
        result.raise_for_status()
        version = result.json()["yunohost"]["version"]
        server_cache_file.write_text(version)
        if Version(version) >= REQUIRED_SERVER_VERSION:
            return True
        logging.error(f"Your server is too old! (server version={version}, required>=12.1)")
        return False

    def real_url(self, url: str) -> str:
        base = get_config().config["servers"][self.name]["hostname"]
        api_path = "/yunohost/api/"
        return "https://" + f"{base}{api_path}{url}".replace("//", "/")

    async def request(
        self,
        method: str,
        url: str,
        *,
        retry_auth: bool = True,
        data: dict[str, str] | None = None,
        params: dict[str, str | list[str]] | None = None,
    ) -> httpx2.Response:
        result = await self.session.request(method, self.real_url(url), params=params, data=data)
        if result.status_code == httpx2.codes.UNAUTHORIZED and retry_auth:
            logging.warning("Authentification seems expired, trying to log in again...")
            await self.login(force=True)
            result = await self.session.request(method, self.real_url(url), params=params, data=data)
        return result

    async def get(
        self,
        url: str,
        data: dict[str, str] | None = None,
        params: dict[str, str | list[str]] | None = None,
    ) -> httpx2.Response:
        return await self.request("GET", url, params=params, data=data)

    async def post(
        self,
        url: str,
        data: dict[str, str] | None = None,
        params: dict[str, str | list[str]] | None = None,
    ) -> httpx2.Response:
        return await self.request("POST", url, params=params, data=data)

    def set_sse_log_handler(self, handler: SSELogHandler) -> None:
        self.sse_handler = handler

    async def sse_logs(self, *, history: bool = False) -> None:
        sse_uri = self.real_url("/sse")

        try:
            async with self.session.sse(sse_uri) as event_source:
                async for sse in event_source:
                    if not self.sse_handler:
                        continue
                    if not sse.data:
                        continue
                    try:
                        data = sse.json()
                        assert isinstance(data, dict)
                        self.sse_handler(SSEEvent(sse.event, data), history=history)
                    except (KeyboardInterrupt, SystemExit):
                        pass
                    except Exception as err:  # noqa: BLE001
                        print(f"Error while parsing the sse logs: {err}")
        except httpx2.SSEError as err:
            logging.error(f"SSE failed: {err}")
