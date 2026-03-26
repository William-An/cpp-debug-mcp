"""FastMCP server entry point with lifespan and tool registration."""

import logging
import sys
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from .gdb.session import GdbSessionManager
from .lsp.session import LspSessionManager
from .tools.gdb_tools import register_gdb_tools
from .tools.lsp_tools import register_lsp_tools
from .tools.combined_tools import register_combined_tools

# Configure logging to stderr (required for STDIO transport)
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(server):
    """Manage GDB and LSP session managers lifecycle."""
    gdb_manager = GdbSessionManager()
    lsp_manager = LspSessionManager()
    logger.info("cpp-debug MCP server starting")
    try:
        yield {"gdb": gdb_manager, "lsp": lsp_manager}
    finally:
        logger.info("cpp-debug MCP server shutting down")
        await gdb_manager.destroy_all()
        await lsp_manager.destroy_all()


mcp = FastMCP(
    name="cpp-debug",
    instructions=(
        "C++ debugging server providing GDB and clangd (LSP) tools. "
        "Use gdb_start_session to begin debugging a compiled executable, "
        "and lsp_start_session for static analysis. "
        "Combined tools like diagnose_crash_site correlate runtime and static info."
    ),
    lifespan=lifespan,
)

# Register all tools
register_gdb_tools(mcp)
register_lsp_tools(mcp)
register_combined_tools(mcp)
