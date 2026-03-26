"""Integration tests for LSP MCP tools."""

import os
import shutil
import pytest

from cpp_debug_mcp.lsp.session import LspSessionManager

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
HAS_CLANGD = shutil.which("clangd") is not None
skip_no_clangd = pytest.mark.skipif(not HAS_CLANGD, reason="clangd not found")
from cpp_debug_mcp.lsp.protocol import make_did_open, make_text_document_position, file_uri


@skip_no_clangd
class TestLspSessionManager:
    """Test LSP session lifecycle."""

    @pytest.mark.asyncio
    async def test_create_and_destroy(self):
        mgr = LspSessionManager()
        session_id, caps = await mgr.create_session(FIXTURES_DIR)
        assert session_id in mgr.list_sessions()
        await mgr.destroy_session(session_id)
        assert session_id not in mgr.list_sessions()

    @pytest.mark.asyncio
    async def test_max_sessions(self):
        mgr = LspSessionManager(max_sessions=1)
        s1, _ = await mgr.create_session(FIXTURES_DIR)
        with pytest.raises(Exception, match="Maximum"):
            await mgr.create_session(FIXTURES_DIR)
        await mgr.destroy_all()

    @pytest.mark.asyncio
    async def test_document_symbols(self):
        """Test getting document symbols from clangd."""
        mgr = LspSessionManager()
        session_id, _ = await mgr.create_session(FIXTURES_DIR)
        client = mgr.get_session(session_id)

        sample_path = os.path.join(FIXTURES_DIR, "sample.cpp")
        content = open(sample_path).read()
        await client.send_notification(
            "textDocument/didOpen",
            make_did_open(sample_path, content),
        )

        result = await client.send_request(
            "textDocument/documentSymbol",
            {"textDocument": {"uri": file_uri(sample_path)}},
            timeout=10.0,
        )
        assert isinstance(result, list)
        # Should find at least main, add, greet, sum_vector
        names = [s.get("name", "") for s in result]
        assert "main" in names

        await mgr.destroy_all()

    @pytest.mark.asyncio
    async def test_goto_definition(self):
        """Test go-to-definition on a function call."""
        mgr = LspSessionManager()
        session_id, _ = await mgr.create_session(FIXTURES_DIR)
        client = mgr.get_session(session_id)

        sample_path = os.path.join(FIXTURES_DIR, "sample.cpp")
        content = open(sample_path).read()
        await client.send_notification(
            "textDocument/didOpen",
            make_did_open(sample_path, content),
        )

        # Go to definition of "add" call in main (around line 23)
        result = await client.send_request(
            "textDocument/definition",
            make_text_document_position(sample_path, 23, 18),
            timeout=10.0,
        )
        assert result is not None

        await mgr.destroy_all()
