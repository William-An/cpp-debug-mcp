"""Tests for LSP/clangd client."""

import os
import shutil
import pytest

from cpp_debug_mcp.lsp.client import ClangdClient

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
HAS_CLANGD = shutil.which("clangd") is not None
skip_no_clangd = pytest.mark.skipif(not HAS_CLANGD, reason="clangd not found")
from cpp_debug_mcp.lsp.protocol import (
    file_uri,
    uri_to_path,
    make_text_document_position,
    make_did_open,
    parse_diagnostic,
    parse_hover,
    parse_location,
    parse_document_symbol,
)


class TestProtocolHelpers:
    """Test LSP protocol message construction."""

    def test_file_uri(self):
        uri = file_uri("/tmp/test.cpp")
        assert uri.startswith("file:///")
        assert uri.endswith("test.cpp")

    def test_uri_to_path(self):
        path = uri_to_path("file:///tmp/test.cpp")
        assert path == "/tmp/test.cpp"

    def test_make_text_document_position(self):
        params = make_text_document_position("/tmp/test.cpp", 10, 5)
        assert params["position"]["line"] == 10
        assert params["position"]["character"] == 5
        assert "uri" in params["textDocument"]

    def test_make_did_open(self):
        params = make_did_open("/tmp/test.cpp", "int main() {}", "cpp")
        td = params["textDocument"]
        assert td["languageId"] == "cpp"
        assert td["text"] == "int main() {}"
        assert td["version"] == 1

    def test_parse_diagnostic(self):
        raw = {
            "range": {
                "start": {"line": 5, "character": 10},
                "end": {"line": 5, "character": 15},
            },
            "severity": 1,
            "message": "use of undeclared identifier",
            "source": "clang",
        }
        diag = parse_diagnostic(raw, "/tmp/test.cpp")
        assert diag.line == 5
        assert diag.column == 10
        assert diag.severity == "error"
        assert "undeclared" in diag.message

    def test_parse_hover_dict(self):
        raw = {"contents": {"language": "cpp", "value": "int x"}}
        hover = parse_hover(raw)
        assert hover is not None
        assert hover.contents == "int x"
        assert hover.language == "cpp"

    def test_parse_hover_string(self):
        hover = parse_hover({"contents": "simple text"})
        assert hover is not None
        assert hover.contents == "simple text"

    def test_parse_hover_none(self):
        assert parse_hover(None) is None

    def test_parse_location(self):
        raw = {
            "uri": "file:///tmp/test.cpp",
            "range": {"start": {"line": 10, "character": 0}},
        }
        loc = parse_location(raw)
        assert loc.file == "/tmp/test.cpp"
        assert loc.line == 10

    def test_parse_document_symbol(self):
        raw = {
            "name": "main",
            "kind": 12,  # Function
            "range": {
                "start": {"line": 5, "character": 0},
                "end": {"line": 10, "character": 1},
            },
            "children": [],
        }
        sym = parse_document_symbol(raw)
        assert sym.name == "main"
        assert sym.kind == 12
        d = sym.to_dict()
        assert d["kind"] == "Function"


@skip_no_clangd
class TestClangdClient:
    """Integration tests requiring clangd."""

    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        client = ClangdClient()
        result = await client.start(FIXTURES_DIR)
        assert client.is_running
        assert "capabilities" in result
        await client.stop()
        assert not client.is_running

    @pytest.mark.asyncio
    async def test_diagnostics(self):
        client = ClangdClient()
        await client.start(FIXTURES_DIR)
        try:
            # Open sample.cpp
            sample_path = os.path.join(FIXTURES_DIR, "sample.cpp")
            content = open(sample_path).read()
            await client.send_notification(
                "textDocument/didOpen",
                make_did_open(sample_path, content),
            )

            # Wait for diagnostics
            notif = await client.wait_for_notification(
                "textDocument/publishDiagnostics", timeout=10.0
            )
            # sample.cpp should compile clean (possibly with minor warnings)
            assert notif is not None
        finally:
            await client.stop()

    @pytest.mark.asyncio
    async def test_hover(self):
        client = ClangdClient()
        await client.start(FIXTURES_DIR)
        try:
            sample_path = os.path.join(FIXTURES_DIR, "sample.cpp")
            content = open(sample_path).read()
            await client.send_notification(
                "textDocument/didOpen",
                make_did_open(sample_path, content),
            )

            # Hover over "add" function (line 4, col 4 — the function name)
            result = await client.send_request(
                "textDocument/hover",
                make_text_document_position(sample_path, 4, 4),
                timeout=10.0,
            )
            assert result is not None
        finally:
            await client.stop()
