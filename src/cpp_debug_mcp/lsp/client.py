"""Async JSON-RPC client for clangd over STDIO."""

import asyncio
import json
import logging
import os
import sys
from typing import Any

logger = logging.getLogger(__name__)


class LspError(Exception):
    """Error from LSP server."""


class ClangdClient:
    """Async client that communicates with clangd via STDIO using LSP protocol."""

    def __init__(self, clangd_path: str | None = None):
        self._clangd_path = clangd_path or os.environ.get("CLANGD_PATH", "clangd")
        self._process: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._notifications: dict[str, list[dict]] = {}
        self._notification_events: dict[str, asyncio.Event] = {}
        self._reader_task: asyncio.Task | None = None
        self._initialized = False

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    async def start(
        self,
        project_root: str,
        compile_commands_dir: str = "",
    ) -> dict:
        """Launch clangd and perform LSP initialization handshake."""
        cmd = [self._clangd_path, "--log=error"]
        if compile_commands_dir:
            cmd.append(f"--compile-commands-dir={compile_commands_dir}")

        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        self._reader_task = asyncio.create_task(self._read_loop())

        from .protocol import make_initialize_params
        result = await self.send_request("initialize", make_initialize_params(project_root))
        await self.send_notification("initialized", {})
        self._initialized = True
        return result

    async def send_request(self, method: str, params: dict, timeout: float = 30.0) -> dict:
        """Send a JSON-RPC request and wait for the response."""
        if not self._process or not self._process.stdin:
            raise LspError("clangd not started")

        self._request_id += 1
        req_id = self._request_id

        message = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }

        future = asyncio.get_event_loop().create_future()
        self._pending[req_id] = future

        self._write_message(message)

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise LspError(f"Request timed out: {method}")

    async def send_notification(self, method: str, params: dict) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        if not self._process or not self._process.stdin:
            raise LspError("clangd not started")

        message = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        self._write_message(message)

    async def wait_for_notification(
        self, method: str, timeout: float = 15.0
    ) -> dict | None:
        """Wait for a specific notification from clangd."""
        if method in self._notifications and self._notifications[method]:
            return self._notifications[method].pop(0)

        event = self._notification_events.setdefault(method, asyncio.Event())
        event.clear()

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            if method in self._notifications and self._notifications[method]:
                return self._notifications[method].pop(0)
        except asyncio.TimeoutError:
            pass
        return None

    async def stop(self) -> None:
        """Shutdown clangd gracefully."""
        if not self._process:
            return

        try:
            if self._initialized:
                await self.send_request("shutdown", {}, timeout=5.0)
                await self.send_notification("exit", {})
        except Exception:
            pass

        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass

        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()

        self._process = None
        self._initialized = False
        self._pending.clear()
        self._notifications.clear()

    def _write_message(self, message: dict) -> None:
        """Write an LSP message with Content-Length header."""
        body = json.dumps(message)
        header = f"Content-Length: {len(body)}\r\n\r\n"
        data = (header + body).encode("utf-8")
        self._process.stdin.write(data)

    async def _read_loop(self) -> None:
        """Background task that reads and dispatches messages from clangd."""
        try:
            while self._process and self._process.returncode is None:
                message = await self._read_message()
                if message is None:
                    break
                self._dispatch(message)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("LSP read loop error: %s", e)

    async def _read_message(self) -> dict | None:
        """Read one LSP message from clangd stdout."""
        stdout = self._process.stdout
        if not stdout:
            return None

        # Read headers
        content_length = 0
        while True:
            line = await stdout.readline()
            if not line:
                return None
            line_str = line.decode("utf-8").strip()
            if not line_str:
                break
            if line_str.startswith("Content-Length:"):
                content_length = int(line_str.split(":")[1].strip())

        if content_length == 0:
            return None

        body = await stdout.readexactly(content_length)
        return json.loads(body.decode("utf-8"))

    def _dispatch(self, message: dict) -> None:
        """Route a received message to the appropriate handler."""
        if "id" in message and "id" in message:
            # Response to a request
            req_id = message["id"]
            future = self._pending.pop(req_id, None)
            if future and not future.done():
                if "error" in message:
                    future.set_exception(
                        LspError(f"LSP error: {message['error'].get('message', '')}")
                    )
                else:
                    future.set_result(message.get("result", {}))
        elif "method" in message and "id" not in message:
            # Notification from server
            method = message["method"]
            params = message.get("params", {})
            self._notifications.setdefault(method, []).append(params)
            event = self._notification_events.get(method)
            if event:
                event.set()
