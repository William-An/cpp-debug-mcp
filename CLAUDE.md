# CLAUDE.md — cpp-debug-mcp

## Project Overview

MCP server plugin for Claude Code that integrates GDB (via GDB/MI) and clangd (via LSP) for C++ debugging. Published on PyPI as `cpp-debug-mcp`.

## Repository Layout

```
src/cpp_debug_mcp/
  server.py          — FastMCP server entry point, lifespan, tool registration
  __main__.py         — python -m entry point
  gdb/
    controller.py     — Async GDB/MI wrapper (pygdbmi + run_in_executor)
    session.py        — Session lifecycle, tmux console management
  lsp/
    client.py         — Async JSON-RPC client for clangd over STDIO
    protocol.py       — LSP message helpers & response parsers
    session.py        — clangd session manager
  analysis/
    correlator.py     — Cross-references GDB runtime + LSP static info
  tools/
    fmt.py            — Human-readable output formatting
    gdb_tools.py      — 16 GDB MCP tools
    lsp_tools.py      — 8 LSP MCP tools
    combined_tools.py — 3 combined GDB+LSP tools
tests/               — pytest tests (fixtures in tests/fixtures/)
```

## Development Setup

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
pytest tests/ -v
```

## Testing

- 27 tests currently pass; 10 are skipped when clangd is not installed
- Tests require `gdb` to be installed (system package)
- Test fixtures: `tests/fixtures/sample.cpp` (valid program), `tests/fixtures/segfault.cpp` (null deref)
- Fixtures are compiled automatically by tests via the Makefile

## Release & Publish Flow

1. Bump version in **both** `pyproject.toml` and `setup.cfg` (they must stay in sync)
2. Commit and push to `master`
3. Create a GitHub release: `gh release create v<VERSION> --title "v<VERSION>" --notes "..."`
4. The `.github/workflows/publish.yml` workflow runs tests on Python 3.10/3.12/3.13, then publishes to PyPI via trusted publisher (OIDC — no API tokens needed)
5. PyPI indexing takes ~30 seconds; verify with `pip index versions cpp-debug-mcp`

## MCP Registration

Global (all projects):
```bash
claude mcp add --scope user cpp-debug -- uvx cpp-debug-mcp
```

`uvx` automatically fetches the latest PyPI version on each invocation — no manual updates needed.

## Key Conventions

- All tools are registered via `register_*_tools(mcp)` functions called from `server.py`
- Tools access session managers via `ctx.request_context.lifespan_context["gdb"]` / `["lsp"]`
- GDB raw commands are sanitized — `shell`, `!`, `python`, `pipe`, `source` are blocked
- Max 4 GDB sessions, 2 LSP sessions, 30-minute inactivity timeout
- Interactive GDB console uses tmux + GDB's `new-ui console <PTY>` command
- All output goes through `tools/fmt.py` for human-readable formatting
- `setup.cfg` exists for backward compatibility with older pip/setuptools

## Dependencies

- `fastmcp>=2.0` — MCP server framework
- `pygdbmi>=0.11` — GDB/MI output parsing
- Dev: `pytest>=7.0`, `pytest-asyncio>=0.21`
