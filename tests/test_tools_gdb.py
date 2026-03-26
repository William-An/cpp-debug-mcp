"""Integration tests for GDB MCP tools."""

import json
import shutil
import pytest

from cpp_debug_mcp.gdb.session import GdbSessionManager

HAS_GDB = shutil.which("gdb") is not None
skip_no_gdb = pytest.mark.skipif(not HAS_GDB, reason="gdb not found")


@skip_no_gdb
class TestGdbSessionManager:
    """Test GDB session lifecycle."""

    @pytest.mark.asyncio
    async def test_create_and_destroy(self, sample_executable):
        mgr = GdbSessionManager()
        session_id, output = await mgr.create_session(sample_executable)
        assert session_id in mgr.list_sessions()
        await mgr.destroy_session(session_id)
        assert session_id not in mgr.list_sessions()

    @pytest.mark.asyncio
    async def test_max_sessions(self, sample_executable):
        mgr = GdbSessionManager(max_sessions=2)
        s1, _ = await mgr.create_session(sample_executable)
        s2, _ = await mgr.create_session(sample_executable)
        with pytest.raises(Exception, match="Maximum"):
            await mgr.create_session(sample_executable)
        await mgr.destroy_all()

    @pytest.mark.asyncio
    async def test_full_debug_workflow(self, sample_executable):
        """Test start -> breakpoint -> run -> backtrace -> evaluate -> end."""
        mgr = GdbSessionManager()
        session_id, _ = await mgr.create_session(sample_executable)
        ctrl = mgr.get_session(session_id)

        # Set breakpoint at main
        responses = await ctrl.send_command("-break-insert main")
        payload = None
        for r in responses:
            if r.get("type") == "result":
                payload = r.get("payload")
        assert payload is not None

        # Run
        await ctrl.send_command("-exec-run")

        # Backtrace
        responses = await ctrl.send_command("-stack-list-frames 0 5")
        for r in responses:
            if r.get("type") == "result":
                stack = r.get("payload", {})
                assert "stack" in stack

        # Step
        await ctrl.send_command("-exec-next")
        await ctrl.send_command("-exec-next")

        # List variables
        responses = await ctrl.send_command("-stack-list-variables --simple-values")
        for r in responses:
            if r.get("type") == "result":
                payload = r.get("payload", {})
                assert "variables" in payload

        await mgr.destroy_session(session_id)

    @pytest.mark.asyncio
    async def test_segfault_detection(self, segfault_executable):
        """Test that we can detect a segfault."""
        mgr = GdbSessionManager()
        session_id, _ = await mgr.create_session(segfault_executable)
        ctrl = mgr.get_session(session_id)

        # Run without breakpoint — should stop on SIGSEGV
        await ctrl.send_command("-exec-run")

        # Get backtrace after crash
        responses = await ctrl.send_command("-stack-list-frames 0 10")
        has_stack = False
        for r in responses:
            if r.get("type") == "result":
                payload = r.get("payload", {})
                if "stack" in payload:
                    has_stack = True
        assert has_stack

        await mgr.destroy_session(session_id)
