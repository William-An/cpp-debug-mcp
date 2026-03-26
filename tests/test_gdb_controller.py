"""Tests for GDB/MI controller."""

import os
import shutil
import pytest

from cpp_debug_mcp.gdb.controller import GdbMiController, GdbError, BLOCKED_COMMANDS

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
HAS_GDB = shutil.which("gdb") is not None
skip_no_gdb = pytest.mark.skipif(not HAS_GDB, reason="gdb not found")


class TestCommandSanitization:
    """Test that dangerous commands are blocked."""

    def test_blocks_shell(self):
        assert BLOCKED_COMMANDS.match("shell ls")

    def test_blocks_bang(self):
        assert BLOCKED_COMMANDS.match("! ls")

    def test_blocks_python(self):
        assert BLOCKED_COMMANDS.match("python print('hi')")

    def test_blocks_pipe(self):
        assert BLOCKED_COMMANDS.match("pipe info threads | grep main")

    def test_blocks_source(self):
        assert BLOCKED_COMMANDS.match("source /tmp/evil.gdb")

    def test_allows_break(self):
        assert not BLOCKED_COMMANDS.match("-break-insert main")

    def test_allows_exec_run(self):
        assert not BLOCKED_COMMANDS.match("-exec-run")

    def test_allows_print(self):
        assert not BLOCKED_COMMANDS.match("print x")


@skip_no_gdb
class TestGdbController:
    """Integration tests requiring GDB."""

    @pytest.mark.asyncio
    async def test_start_and_stop(self, sample_executable):
        ctrl = GdbMiController()
        output = await ctrl.start(sample_executable)
        assert ctrl.is_running
        await ctrl.stop()
        assert not ctrl.is_running

    @pytest.mark.asyncio
    async def test_set_breakpoint(self, sample_executable):
        ctrl = GdbMiController()
        await ctrl.start(sample_executable)
        try:
            responses = await ctrl.send_command("-break-insert main")
            payload = None
            for r in responses:
                if r.get("type") == "result":
                    payload = r.get("payload")
            assert payload is not None
            assert "bkpt" in payload
        finally:
            await ctrl.stop()

    @pytest.mark.asyncio
    async def test_run_and_backtrace(self, sample_executable):
        ctrl = GdbMiController()
        await ctrl.start(sample_executable)
        try:
            await ctrl.send_command("-break-insert main")
            await ctrl.send_command("-exec-run")
            responses = await ctrl.send_command("-stack-list-frames 0 5")
            payload = None
            for r in responses:
                if r.get("type") == "result":
                    payload = r.get("payload")
            assert payload is not None
            assert "stack" in payload
        finally:
            await ctrl.stop()

    @pytest.mark.asyncio
    async def test_evaluate_expression(self, sample_executable):
        ctrl = GdbMiController()
        await ctrl.start(sample_executable)
        try:
            # Break at a point where x is defined
            await ctrl.send_command("-break-insert main")
            await ctrl.send_command("-exec-run")
            # Step past variable initialization
            await ctrl.send_command("-exec-next")
            await ctrl.send_command("-exec-next")
            responses = await ctrl.send_command('-data-evaluate-expression "x"')
            result = None
            for r in responses:
                if r.get("type") == "result":
                    result = r.get("payload")
            assert result is not None
        finally:
            await ctrl.stop()

    @pytest.mark.asyncio
    async def test_raw_command_blocked(self, sample_executable):
        ctrl = GdbMiController()
        await ctrl.start(sample_executable)
        try:
            with pytest.raises(GdbError, match="blocked"):
                await ctrl.send_raw_command("shell ls")
        finally:
            await ctrl.stop()
