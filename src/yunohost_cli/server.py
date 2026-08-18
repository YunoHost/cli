#!/usr/bin/env python3

import asyncio
import json
import logging
from enum import Enum
from typing import Any, Protocol

import niquests
import niquests.typing
import urllib3
from packaging.version import Version

from .config import get_config

PrimitiveData = str | int | float | bool | None


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

        timeout = urllib3.Timeout(
            total=10000.0,
            connect=10,
            read=1000,
        )
        self.session = niquests.AsyncSession(
            timeout=timeout,
            verify=secure,
        )

    async def login(self, *, force: bool = False) -> bool:
        server_config = get_config().config["servers"][self.name]
        server_cache_file = get_config().cache_dir / self.name
        if force:
            server_cache_file.unlink(missing_ok=True)
            self.session.cookies.clear(name="yunohost.admin")
        if server_cache_file.exists():
            cookie = server_cache_file.read_text().strip()
            self.session.cookies.set(name="yunohost.admin", value=cookie)
            return True

        data = {
            "username": server_config["username"],
            "password": server_config["password"],
        }
        try:
            logging.info("Logging in...")
            result = await self.post("/login", data=data)
            if not result.ok:
                return False
            server_cache_file.write_text(result.cookies["yunohost.admin"])
            return True
        except niquests.exceptions.RequestException as err:
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
        base = get_config().config["servers"][self.name]["hostname"]
        api_path = "/yunohost/api/"
        return "https://" + f"{base}{api_path}{url}".replace("//", "/")

    async def request(
        self,
        method: niquests.typing.HttpMethodType,
        url: str,
        *,
        retry_auth: bool = True,
        data: niquests.typing.BodyType | None = None,
        params: niquests.typing.QueryParameterType | None = None,
    ) -> niquests.Response:
        result = await self.session.request(method, self.real_url(url), params=params, data=data)
        # ty: ignore[unresolved-attribute]
        if result.status_code == niquests.codes.unauthorized and retry_auth:
            logging.warning("Authentification seems expired, trying to log in again...")
            await self.login(force=True)
            result = await self.session.request(method, self.real_url(url), params=params, data=data)
        return result

    async def get(
        self,
        url: str,
        data: niquests.typing.BodyType | None = None,
        params: niquests.typing.QueryParameterType | None = None,
    ) -> niquests.Response:
        return await self.request("GET", url, params=params, data=data)

    async def post(
        self,
        url: str,
        data: niquests.typing.BodyType | None = None,
        params: niquests.typing.QueryParameterType | None = None,
    ) -> niquests.Response:
        return await self.request("POST", url, params=params, data=data)

    def set_sse_log_handler(self, handler: SSELogHandler) -> None:
        self.sse_handler = handler

    async def sse_logs(self, *, history: bool = False) -> None:
        sse_uri = self.real_url("/sse").replace("https", "sse")

        result = await self.session.get(sse_uri)
        sse = result.extension
        assert isinstance(sse, niquests.models.AsyncServerSideEventExtensionFromHTTP)

        while sse.closed is False:
            event = await sse.next_payload()

            # The remote peer closed the stream.
            if event is None:
                continue

            if not event.data:
                continue

            try:
                data = json.loads(event.data)
                if self.sse_handler:
                    self.sse_handler(SSEEvent(event.event, data), history=history)
            except (KeyboardInterrupt, SystemExit):
                raise
            except (json.JSONDecodeError, Exception) as err:  # noqa: BLE001
                print(f"Error while parsing the sse logs: {err}")


        print("toto")
