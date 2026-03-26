"""Integration tests for combined GDB + LSP tools."""

import os
import shutil
import pytest

from cpp_debug_mcp.gdb.session import GdbSessionManager

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
HAS_GDB = shutil.which("gdb") is not None
HAS_CLANGD = shutil.which("clangd") is not None
from cpp_debug_mcp.lsp.session import LspSessionManager
from cpp_debug_mcp.lsp.protocol import make_did_open
from cpp_debug_mcp.analysis.correlator import (
    get_crash_report,
    get_variable_info,
    analyze_function_info,
)

skip_no_both = pytest.mark.skipif(
    not (HAS_GDB and HAS_CLANGD),
    reason="requires both gdb and clangd",
)


@skip_no_both
class TestCombinedAnalysis:
    """Integration tests requiring both GDB and clangd."""

    @pytest.mark.asyncio
    async def test_crash_report(self, segfault_executable):
        gdb_mgr = GdbSessionManager()
        lsp_mgr = LspSessionManager()

        gdb_sid, _ = await gdb_mgr.create_session(segfault_executable)
        lsp_sid, _ = await lsp_mgr.create_session(FIXTURES_DIR)

        gdb_ctrl = gdb_mgr.get_session(gdb_sid)
        lsp_client = lsp_mgr.get_session(lsp_sid)
        opened_files = lsp_mgr.get_opened_files(lsp_sid)

        # Run until crash
        await gdb_ctrl.send_command("-exec-run")

        report = await get_crash_report(gdb_ctrl, lsp_client, opened_files)

        assert "backtrace" in report
        assert len(report["backtrace"]) > 0
        assert "local_variables" in report

        await gdb_mgr.destroy_all()
        await lsp_mgr.destroy_all()

    @pytest.mark.asyncio
    async def test_variable_info(self, sample_executable):
        gdb_mgr = GdbSessionManager()
        lsp_mgr = LspSessionManager()

        gdb_sid, _ = await gdb_mgr.create_session(sample_executable)
        lsp_sid, _ = await lsp_mgr.create_session(FIXTURES_DIR)

        gdb_ctrl = gdb_mgr.get_session(gdb_sid)
        lsp_client = lsp_mgr.get_session(lsp_sid)
        opened_files = lsp_mgr.get_opened_files(lsp_sid)

        # Break at main and step past variable init
        await gdb_ctrl.send_command("-break-insert main")
        await gdb_ctrl.send_command("-exec-run")
        await gdb_ctrl.send_command("-exec-next")
        await gdb_ctrl.send_command("-exec-next")

        sample_path = os.path.join(FIXTURES_DIR, "sample.cpp")
        result = await get_variable_info(
            gdb_ctrl, lsp_client, opened_files,
            "x", sample_path, 22,
        )

        assert result["variable"] == "x"
        assert "runtime_value" in result

        await gdb_mgr.destroy_all()
        await lsp_mgr.destroy_all()

    @pytest.mark.asyncio
    async def test_analyze_function(self, sample_executable):
        gdb_mgr = GdbSessionManager()
        lsp_mgr = LspSessionManager()

        gdb_sid, _ = await gdb_mgr.create_session(sample_executable)
        lsp_sid, _ = await lsp_mgr.create_session(FIXTURES_DIR)

        gdb_ctrl = gdb_mgr.get_session(gdb_sid)
        lsp_client = lsp_mgr.get_session(lsp_sid)
        opened_files = lsp_mgr.get_opened_files(lsp_sid)

        result = await analyze_function_info(
            gdb_ctrl, lsp_client, opened_files, "add",
        )

        assert result["function"] == "add"
        assert "breakpoint" in result

        await gdb_mgr.destroy_all()
        await lsp_mgr.destroy_all()
