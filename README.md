# cpp-debug-mcp

A [Claude Code](https://claude.ai/code) MCP server plugin for C++ debugging. Integrates **GDB** (via GDB/MI) and **clangd** (via LSP) to give Claude Code tools for stepping through code, inspecting variables, reading diagnostics, and correlating runtime state with static analysis — all from the conversation.

## Prerequisites

- Python 3.10+
- [GDB](https://www.gnu.org/software/gdb/) (for debugging tools)
- [clangd](https://clangd.llvm.org/) (for static analysis tools)
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

## Quick Start

Register the MCP server globally (all projects, auto-updates):

```bash
claude mcp add --scope user cpp-debug -- uvx cpp-debug-mcp
```

That's it. Verify with `/mcp` inside Claude Code to confirm the server is connected.

## Installation Options

### Auto-updating via uvx (recommended)

No install step needed — `uvx` fetches the latest version from PyPI on each invocation. Just register with the command above.

### From PyPI

```bash
pip install cpp-debug-mcp
```

### From GitHub

```bash
pip install git+https://github.com/William-An/cpp-debug-mcp.git
```

### From source (for development)

```bash
git clone https://github.com/William-An/cpp-debug-mcp.git
cd cpp-debug-mcp
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Register with Claude Code

### Global (all projects)

```bash
claude mcp add --scope user cpp-debug -- uvx cpp-debug-mcp
```

### Per-project (CLI)

```bash
claude mcp add cpp-debug -- uvx cpp-debug-mcp
```

### Per-project (.mcp.json)

```json
{
  "mcpServers": {
    "cpp-debug": {
      "type": "stdio",
      "command": "uvx",
      "args": ["cpp-debug-mcp"]
    }
  }
}
```

| Scope | Flag | Config file | Availability |
|---|---|---|---|
| **User** | `--scope user` | `~/.claude.json` | All projects, private to you |
| **Project** | `--scope project` | `.mcp.json` | This project, shared via git |
| **Local** | *(default)* | `.mcp.json` | This project, private to you |

## Tools

### GDB Tools (16)

| Tool | Description |
|---|---|
| `gdb_start_session` | Start a GDB session for a compiled executable |
| `gdb_end_session` | End a session and clean up |
| `gdb_run` | Start execution (optionally stop at `main`) |
| `gdb_set_breakpoint` | Set a breakpoint by file:line, function, or address |
| `gdb_delete_breakpoint` | Delete a breakpoint by ID |
| `gdb_list_breakpoints` | List all active breakpoints |
| `gdb_continue` | Continue until next breakpoint or exit |
| `gdb_step` | Step into, over, or out of functions |
| `gdb_backtrace` | Get the call stack |
| `gdb_list_variables` | List local variables in a stack frame |
| `gdb_evaluate` | Evaluate a C++ expression (e.g. `*ptr`, `arr[5]`) |
| `gdb_read_memory` | Read raw memory at an address |
| `gdb_thread_info` | List all threads and their states |
| `gdb_raw_command` | Execute a raw GDB command (with safety restrictions) |
| `gdb_open_console` | Open an interactive GDB console via tmux (requires tmux) |
| `gdb_close_console` | Close the interactive GDB console |

### LSP/clangd Tools (8)

| Tool | Description |
|---|---|
| `lsp_start_session` | Start a clangd session for a project |
| `lsp_end_session` | End a clangd session |
| `lsp_diagnostics` | Get compile errors and warnings for a file |
| `lsp_hover` | Get type/documentation info at a position |
| `lsp_goto_definition` | Find where a symbol is defined |
| `lsp_find_references` | Find all references to a symbol |
| `lsp_document_symbols` | List all symbols in a file |
| `lsp_signature_help` | Get function signature help at a call site |

### Combined Tools (3)

| Tool | Description |
|---|---|
| `inspect_variable_with_type` | GDB runtime value + clangd type info for a variable |
| `diagnose_crash_site` | Backtrace + local variables + LSP diagnostics at crash |
| `analyze_function` | Breakpoint + signature + references + locals for a function |

## Example Usage

Compile your C++ program with debug symbols, then ask Claude Code to debug it:

```
> Compile main.cpp with debug symbols and find why it segfaults

Claude will:
1. Run g++ -g -O0 -o main main.cpp
2. Call gdb_start_session with the executable
3. Call gdb_run to execute until the crash
4. Call diagnose_crash_site to get the full crash report
5. Explain the root cause with backtrace, variable values, and type info
```

## Architecture

```
src/cpp_debug_mcp/
├── server.py              # FastMCP entry point with lifespan management
├── gdb/
│   ├── controller.py      # Async GDB/MI subprocess wrapper (pygdbmi)
│   └── session.py         # Session lifecycle (max 4, 30min timeout)
├── lsp/
│   ├── client.py          # Async JSON-RPC client for clangd over STDIO
│   ├── protocol.py        # LSP message helpers and response parsers
│   └── session.py         # Session lifecycle (max 2, 30min timeout)
├── analysis/
│   └── correlator.py      # Cross-references GDB runtime + LSP static info
└── tools/
    ├── fmt.py             # Human-readable output formatting
    ├── gdb_tools.py       # 16 GDB MCP tools (incl. interactive console)
    ├── lsp_tools.py       # 8 LSP MCP tools
    └── combined_tools.py  # 3 combined analysis tools
```

## Safety

- **Command sanitization**: `gdb_raw_command` blocks `shell`, `!`, `python`, `pipe`, and `source` commands
- **Resource limits**: Max 4 GDB sessions and 2 LSP sessions concurrently
- **Auto-cleanup**: Stale sessions are cleaned up after 30 minutes of inactivity
- **Process lifecycle**: All subprocesses are terminated on server shutdown

## Running Tests

```bash
source .venv/bin/activate
uv pip install -e ".[dev]"
python -m pytest tests/ -v
```

GDB tests require `gdb` to be installed. LSP tests require `clangd`. Tests that need unavailable tools are automatically skipped.

## License

MIT
