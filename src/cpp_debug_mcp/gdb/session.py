"""GDB session lifecycle manager."""

import asyncio
import logging
import time
import uuid

from .controller import GdbMiController, GdbError

logger = logging.getLogger(__name__)

MAX_SESSIONS = 4
INACTIVITY_TIMEOUT = 1800  # 30 minutes


class GdbSessionManager:
    """Manages multiple GDB debugging sessions."""

    def __init__(self, max_sessions: int = MAX_SESSIONS):
        self._sessions: dict[str, GdbMiController] = {}
        self._last_activity: dict[str, float] = {}
        self._max_sessions = max_sessions

    async def create_session(
        self,
        executable: str,
        args: list[str] | None = None,
        working_dir: str = ".",
    ) -> tuple[str, str]:
        """Create a new GDB session. Returns (session_id, init_output)."""
        await self._cleanup_stale()

        if len(self._sessions) >= self._max_sessions:
            raise GdbError(
                f"Maximum sessions ({self._max_sessions}) reached. "
                "End an existing session first."
            )

        session_id = str(uuid.uuid4())[:8]
        controller = GdbMiController()

        output = await controller.start(executable, args, working_dir)
        self._sessions[session_id] = controller
        self._last_activity[session_id] = time.time()

        return session_id, output

    def get_session(self, session_id: str) -> GdbMiController:
        """Get a session by ID, updating activity timestamp."""
        if session_id not in self._sessions:
            raise GdbError(f"Session not found: {session_id}")
        self._last_activity[session_id] = time.time()
        return self._sessions[session_id]

    async def destroy_session(self, session_id: str) -> None:
        """End and clean up a specific session."""
        controller = self._sessions.pop(session_id, None)
        self._last_activity.pop(session_id, None)
        if controller:
            await controller.stop()

    async def destroy_all(self) -> None:
        """End all sessions. Called during server shutdown."""
        session_ids = list(self._sessions.keys())
        for sid in session_ids:
            await self.destroy_session(sid)

    def list_sessions(self) -> list[str]:
        """Return list of active session IDs."""
        return list(self._sessions.keys())

    async def _cleanup_stale(self) -> None:
        """Remove sessions that have been inactive too long."""
        now = time.time()
        stale = [
            sid
            for sid, last in self._last_activity.items()
            if now - last > INACTIVITY_TIMEOUT
        ]
        for sid in stale:
            logger.info("Cleaning up stale session: %s", sid)
            await self.destroy_session(sid)
