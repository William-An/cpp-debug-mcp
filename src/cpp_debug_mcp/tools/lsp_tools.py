"""LSP/clangd MCP tool definitions."""

import json
from pathlib import Path

from fastmcp import Context

from ..lsp.protocol import (
    file_uri,
    make_did_open,
    make_text_document_position,
    make_reference_params,
    parse_diagnostic,
    parse_hover,
    parse_location,
    parse_document_symbol,
)


async def _ensure_file_open(session_id: str, file_path: str, ctx: Context) -> None:
    """Open a file in clangd if not already opened."""
    lsp_mgr = ctx.request_context.lifespan_context["lsp"]
    client = lsp_mgr.get_session(session_id)
    uri = file_uri(file_path)

    if uri not in lsp_mgr.get_opened_files(session_id):
        content = Path(file_path).resolve().read_text()
        lang = "cpp"
        if file_path.endswith(".c"):
            lang = "c"
        elif file_path.endswith(".h"):
            lang = "c"  # could be c or cpp, default c
        await client.send_notification(
            "textDocument/didOpen",
            make_did_open(file_path, content, lang),
        )
        lsp_mgr.mark_file_opened(session_id, uri)


def register_lsp_tools(mcp):
    """Register all LSP tools on the FastMCP server instance."""

    @mcp.tool()
    async def lsp_start_session(
        project_root: str,
        compile_commands_dir: str = "",
        ctx: Context = None,
    ) -> str:
        """Start a clangd LSP session for static analysis of C++ code.

        Args:
            project_root: Root directory of the C++ project.
            compile_commands_dir: Directory containing compile_commands.json (optional, improves accuracy).
        """
        manager = ctx.request_context.lifespan_context["lsp"]
        session_id, capabilities = await manager.create_session(
            project_root, compile_commands_dir
        )
        return json.dumps({
            "session_id": session_id,
            "status": "started",
        })

    @mcp.tool()
    async def lsp_end_session(session_id: str, ctx: Context = None) -> str:
        """End a clangd LSP session.

        Args:
            session_id: The session identifier returned by lsp_start_session.
        """
        manager = ctx.request_context.lifespan_context["lsp"]
        await manager.destroy_session(session_id)
        return json.dumps({"session_id": session_id, "status": "ended"})

    @mcp.tool()
    async def lsp_diagnostics(
        session_id: str,
        file_path: str,
        ctx: Context = None,
    ) -> str:
        """Get compile errors and warnings for a C++ file from clangd.

        Args:
            session_id: The LSP session identifier.
            file_path: Absolute path to the C++ source file.
        """
        manager = ctx.request_context.lifespan_context["lsp"]
        client = manager.get_session(session_id)

        await _ensure_file_open(session_id, file_path, ctx)

        # Wait for diagnostics notification
        notif = await client.wait_for_notification(
            "textDocument/publishDiagnostics", timeout=15.0
        )

        if notif and "diagnostics" in notif:
            diagnostics = [
                parse_diagnostic(d, file_path).to_dict()
                for d in notif["diagnostics"]
            ]
            return json.dumps(diagnostics, indent=2)
        return json.dumps([])

    @mcp.tool()
    async def lsp_hover(
        session_id: str,
        file_path: str,
        line: int,
        column: int,
        ctx: Context = None,
    ) -> str:
        """Get type and documentation info at a specific code position.

        Args:
            session_id: The LSP session identifier.
            file_path: Absolute path to the C++ source file.
            line: 0-indexed line number.
            column: 0-indexed column number.
        """
        manager = ctx.request_context.lifespan_context["lsp"]
        client = manager.get_session(session_id)

        await _ensure_file_open(session_id, file_path, ctx)

        result = await client.send_request(
            "textDocument/hover",
            make_text_document_position(file_path, line, column),
        )

        hover = parse_hover(result)
        if hover:
            return json.dumps(hover.to_dict())
        return json.dumps({"contents": "", "language": ""})

    @mcp.tool()
    async def lsp_goto_definition(
        session_id: str,
        file_path: str,
        line: int,
        column: int,
        ctx: Context = None,
    ) -> str:
        """Find where a symbol is defined.

        Args:
            session_id: The LSP session identifier.
            file_path: Absolute path to the C++ source file.
            line: 0-indexed line number.
            column: 0-indexed column number.
        """
        manager = ctx.request_context.lifespan_context["lsp"]
        client = manager.get_session(session_id)

        await _ensure_file_open(session_id, file_path, ctx)

        result = await client.send_request(
            "textDocument/definition",
            make_text_document_position(file_path, line, column),
        )

        if isinstance(result, list):
            locations = [parse_location(loc).to_dict() for loc in result]
            return json.dumps(locations, indent=2)
        elif isinstance(result, dict) and "uri" in result:
            return json.dumps([parse_location(result).to_dict()], indent=2)
        return json.dumps([])

    @mcp.tool()
    async def lsp_find_references(
        session_id: str,
        file_path: str,
        line: int,
        column: int,
        ctx: Context = None,
    ) -> str:
        """Find all references to a symbol.

        Args:
            session_id: The LSP session identifier.
            file_path: Absolute path to the C++ source file.
            line: 0-indexed line number.
            column: 0-indexed column number.
        """
        manager = ctx.request_context.lifespan_context["lsp"]
        client = manager.get_session(session_id)

        await _ensure_file_open(session_id, file_path, ctx)

        result = await client.send_request(
            "textDocument/references",
            make_reference_params(file_path, line, column),
        )

        if isinstance(result, list):
            locations = [parse_location(loc).to_dict() for loc in result]
            return json.dumps(locations, indent=2)
        return json.dumps([])

    @mcp.tool()
    async def lsp_document_symbols(
        session_id: str,
        file_path: str,
        ctx: Context = None,
    ) -> str:
        """List all symbols (functions, classes, variables) in a file.

        Args:
            session_id: The LSP session identifier.
            file_path: Absolute path to the C++ source file.
        """
        manager = ctx.request_context.lifespan_context["lsp"]
        client = manager.get_session(session_id)

        await _ensure_file_open(session_id, file_path, ctx)

        result = await client.send_request(
            "textDocument/documentSymbol",
            {"textDocument": {"uri": file_uri(file_path)}},
        )

        if isinstance(result, list):
            symbols = [parse_document_symbol(s).to_dict() for s in result]
            return json.dumps(symbols, indent=2)
        return json.dumps([])

    @mcp.tool()
    async def lsp_signature_help(
        session_id: str,
        file_path: str,
        line: int,
        column: int,
        ctx: Context = None,
    ) -> str:
        """Get function signature help at a call site.

        Args:
            session_id: The LSP session identifier.
            file_path: Absolute path to the C++ source file.
            line: 0-indexed line number.
            column: 0-indexed column number (should be inside the parentheses of a function call).
        """
        manager = ctx.request_context.lifespan_context["lsp"]
        client = manager.get_session(session_id)

        await _ensure_file_open(session_id, file_path, ctx)

        result = await client.send_request(
            "textDocument/signatureHelp",
            make_text_document_position(file_path, line, column),
        )

        if result and "signatures" in result:
            signatures = []
            for sig in result["signatures"]:
                signatures.append({
                    "label": sig.get("label", ""),
                    "documentation": sig.get("documentation", ""),
                    "parameters": [
                        {"label": p.get("label", ""), "documentation": p.get("documentation", "")}
                        for p in sig.get("parameters", [])
                    ],
                })
            return json.dumps({
                "signatures": signatures,
                "active_signature": result.get("activeSignature", 0),
                "active_parameter": result.get("activeParameter", 0),
            }, indent=2)
        return json.dumps({"signatures": []})
