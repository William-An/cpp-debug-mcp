"""GDB/MI subprocess controller wrapping pygdbmi with async execution."""

import asyncio
import logging
import os
import re
import sys
from typing import Any

from pygdbmi.gdbcontroller import GdbController

logger = logging.getLogger(__name__)

# Commands blocked in raw mode to prevent injection
BLOCKED_COMMANDS = re.compile(
    r"^\s*(shell\b|!|python\b|python-interactive\b|pi\b|pipe\b|source\b)",
    re.IGNORECASE,
)


class GdbError(Exception):
    """Error from GDB."""


class GdbTimeoutError(GdbError):
    """GDB command timed out."""


class GdbMiController:
    """Async wrapper around pygdbmi's GdbController for GDB/MI communication."""

    def __init__(self, gdb_path: str | None = None):
        self._gdb_path = gdb_path or os.environ.get("GDB_PATH", "gdb")
        self._controller: GdbController | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def is_running(self) -> bool:
        return self._controller is not None

    async def start(
        self,
        executable: str,
        args: list[str] | None = None,
        working_dir: str = ".",
    ) -> str:
        """Launch GDB and load the executable. Returns initialization output."""
        self._loop = asyncio.get_event_loop()
        gdb_args = [self._gdb_path, "--interpreter=mi3", "-q"]
        if working_dir and working_dir != ".":
            gdb_args.extend(["--cd", working_dir])

        def _start():
            ctrl = GdbController(command=gdb_args)
            return ctrl

        self._controller = await self._loop.run_in_executor(None, _start)

        # Load the executable
        result = await self.send_command(f"-file-exec-and-symbols {executable}")
        return self._format_responses(result)

    async def send_command(
        self,
        command: str,
        timeout: float = 30.0,
    ) -> list[dict[str, Any]]:
        """Send an MI command and return parsed responses."""
        if not self._controller:
            raise GdbError("GDB session not started")

        def _write():
            return self._controller.write(
                command,
                timeout_sec=int(timeout),
                raise_error_on_timeout=True,
            )

        try:
            return await self._loop.run_in_executor(None, _write)
        except Exception as e:
            if "timed out" in str(e).lower():
                raise GdbTimeoutError(f"Command timed out: {command}") from e
            raise GdbError(str(e)) from e

    async def send_raw_command(self, command: str, timeout: float = 30.0) -> list[dict[str, Any]]:
        """Send a raw GDB command with safety checks."""
        if BLOCKED_COMMANDS.match(command.strip()):
            raise GdbError(
                f"Command blocked for safety: {command.split()[0]}. "
                "Shell, python, pipe, and source commands are not allowed."
            )
        return await self.send_command(command, timeout)

    async def stop(self) -> None:
        """Terminate GDB process."""
        if self._controller:
            try:
                def _exit():
                    try:
                        self._controller.write("-gdb-exit", timeout_sec=5)
                    except Exception:
                        pass
                    self._controller.exit()

                await self._loop.run_in_executor(None, _exit)
            except Exception as e:
                logger.warning("Error stopping GDB: %s", e, file=sys.stderr)
            finally:
                self._controller = None

    @staticmethod
    def _format_responses(responses: list[dict[str, Any]]) -> str:
        """Format MI responses into a readable string."""
        parts = []
        for resp in responses:
            msg_type = resp.get("type", "")
            message = resp.get("message", "")
            payload = resp.get("payload", "")

            if msg_type == "result":
                if message == "error":
                    parts.append(f"ERROR: {payload}")
                elif payload:
                    parts.append(str(payload))
            elif msg_type == "console":
                if payload:
                    parts.append(payload.strip())
            elif msg_type == "notify" and payload:
                parts.append(f"[{message}] {payload}")

        return "\n".join(parts) if parts else "OK"

    def format(self, responses: list[dict[str, Any]]) -> str:
        """Public format method."""
        return self._format_responses(responses)
