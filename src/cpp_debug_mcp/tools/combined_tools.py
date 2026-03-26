"""Combined GDB + LSP MCP tool definitions."""

import json

from fastmcp import Context

from ..analysis.correlator import (
    get_crash_report,
    get_variable_info,
    analyze_function_info,
)


def register_combined_tools(mcp):
    """Register combined analysis tools on the FastMCP server instance."""

    @mcp.tool()
    async def inspect_variable_with_type(
        gdb_session_id: str,
        lsp_session_id: str,
        variable_name: str,
        file_path: str,
        line: int,
        ctx: Context = None,
    ) -> str:
        """Inspect a variable combining GDB runtime value with LSP type information.

        Gets the variable's current value from GDB and its type/documentation
        from clangd for a complete picture.

        Args:
            gdb_session_id: Active GDB session (program must be stopped).
            lsp_session_id: Active LSP session for the project.
            variable_name: Name of the variable to inspect.
            file_path: Absolute path to the source file containing the variable.
            line: 1-indexed line number where the variable appears.
        """
        gdb_mgr = ctx.request_context.lifespan_context["gdb"]
        lsp_mgr = ctx.request_context.lifespan_context["lsp"]

        gdb_ctrl = gdb_mgr.get_session(gdb_session_id)
        lsp_client = lsp_mgr.get_session(lsp_session_id)
        opened_files = lsp_mgr.get_opened_files(lsp_session_id)

        result = await get_variable_info(
            gdb_ctrl, lsp_client, opened_files,
            variable_name, file_path, line,
        )
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def diagnose_crash_site(
        gdb_session_id: str,
        lsp_session_id: str,
        max_frames: int = 5,
        ctx: Context = None,
    ) -> str:
        """Diagnose a crash by combining GDB backtrace with LSP static analysis.

        When the program has stopped (e.g., SIGSEGV), this tool gathers:
        - Full backtrace from GDB
        - Local variables at the crash frame
        - Type information at each frame from clangd
        - Static diagnostics (warnings/errors) for relevant source files

        Args:
            gdb_session_id: Active GDB session (program must be stopped at crash).
            lsp_session_id: Active LSP session for the project.
            max_frames: Maximum backtrace frames to analyze.
        """
        gdb_mgr = ctx.request_context.lifespan_context["gdb"]
        lsp_mgr = ctx.request_context.lifespan_context["lsp"]

        gdb_ctrl = gdb_mgr.get_session(gdb_session_id)
        lsp_client = lsp_mgr.get_session(lsp_session_id)
        opened_files = lsp_mgr.get_opened_files(lsp_session_id)

        report = await get_crash_report(
            gdb_ctrl, lsp_client, opened_files, max_frames,
        )
        return json.dumps(report, indent=2)

    @mcp.tool()
    async def analyze_function(
        gdb_session_id: str,
        lsp_session_id: str,
        function_name: str,
        ctx: Context = None,
    ) -> str:
        """Analyze a function using both GDB and LSP.

        Sets a temporary breakpoint at the function, gets its signature and
        references from clangd, and retrieves local variables if the program
        is stopped there.

        Args:
            gdb_session_id: Active GDB session.
            lsp_session_id: Active LSP session for the project.
            function_name: Name of the function to analyze.
        """
        gdb_mgr = ctx.request_context.lifespan_context["gdb"]
        lsp_mgr = ctx.request_context.lifespan_context["lsp"]

        gdb_ctrl = gdb_mgr.get_session(gdb_session_id)
        lsp_client = lsp_mgr.get_session(lsp_session_id)
        opened_files = lsp_mgr.get_opened_files(lsp_session_id)

        result = await analyze_function_info(
            gdb_ctrl, lsp_client, opened_files, function_name,
        )
        return json.dumps(result, indent=2)
