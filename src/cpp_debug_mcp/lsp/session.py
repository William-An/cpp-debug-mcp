"""LSP/clangd session lifecycle manager."""

import logging
import time
import uuid

from .client import ClangdClient, LspError

logger = logging.getLogger(__name__)

MAX_SESSIONS = 2
INACTIVITY_TIMEOUT = 1800  # 30 minutes


class LspSessionManager:
    """Manages multiple clangd LSP sessions."""

    def __init__(self, max_sessions: int = MAX_SESSIONS):
        self._sessions: dict[str, ClangdClient] = {}
        self._last_activity: dict[str, float] = {}
        self._opened_files: dict[str, set[str]] = {}  # session_id -> set of opened URIs
        self._max_sessions = max_sessions

    async def create_session(
        self,
        project_root: str,
        compile_commands_dir: str = "",
    ) -> tuple[str, dict]:
        """Create a new clangd session. Returns (session_id, server_capabilities)."""
        await self._cleanup_stale()

        if len(self._sessions) >= self._max_sessions:
            raise LspError(
                f"Maximum LSP sessions ({self._max_sessions}) reached. "
                "End an existing session first."
            )

        session_id = str(uuid.uuid4())[:8]
        client = ClangdClient()

        capabilities = await client.start(project_root, compile_commands_dir)
        self._sessions[session_id] = client
        self._last_activity[session_id] = time.time()
        self._opened_files[session_id] = set()

        return session_id, capabilities

    def get_session(self, session_id: str) -> ClangdClient:
        """Get a session by ID."""
        if session_id not in self._sessions:
            raise LspError(f"LSP session not found: {session_id}")
        self._last_activity[session_id] = time.time()
        return self._sessions[session_id]

    def get_opened_files(self, session_id: str) -> set[str]:
        """Get the set of file URIs opened in a session."""
        return self._opened_files.get(session_id, set())

    def mark_file_opened(self, session_id: str, uri: str) -> None:
        """Mark a file URI as opened in a session."""
        self._opened_files.setdefault(session_id, set()).add(uri)

    async def destroy_session(self, session_id: str) -> None:
        """End and clean up a specific session."""
        client = self._sessions.pop(session_id, None)
        self._last_activity.pop(session_id, None)
        self._opened_files.pop(session_id, None)
        if client:
            await client.stop()

    async def destroy_all(self) -> None:
        """End all sessions."""
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
            logger.info("Cleaning up stale LSP session: %s", sid)
            await self.destroy_session(sid)
