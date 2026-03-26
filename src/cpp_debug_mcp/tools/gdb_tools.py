"""GDB MCP tool definitions."""

import json
from typing import Any

from fastmcp import Context


def _fmt(controller, responses: list[dict[str, Any]]) -> str:
    """Format GDB MI responses into readable text."""
    return controller.format(responses)


def _payload(responses: list[dict[str, Any]]) -> dict | str | None:
    """Extract the result payload from MI responses."""
    for r in responses:
        if r.get("type") == "result":
            return r.get("payload")
    return None


def register_gdb_tools(mcp):
    """Register all GDB tools on the FastMCP server instance."""

    @mcp.tool()
    async def gdb_start_session(
        executable: str,
        args: list[str] = [],
        working_dir: str = ".",
        ctx: Context = None,
    ) -> str:
        """Start a GDB debugging session for a compiled C++ executable.

        Args:
            executable: Path to the compiled executable (must be built with -g for debug symbols).
            args: Command-line arguments to pass to the program.
            working_dir: Working directory for the debug session.
        """
        manager = ctx.request_context.lifespan_context["gdb"]
        session_id, output = await manager.create_session(executable, args, working_dir)
        return json.dumps({
            "session_id": session_id,
            "status": "started",
            "details": output,
        })

    @mcp.tool()
    async def gdb_end_session(session_id: str, ctx: Context = None) -> str:
        """End a GDB debugging session and clean up resources.

        Args:
            session_id: The session identifier returned by gdb_start_session.
        """
        manager = ctx.request_context.lifespan_context["gdb"]
        await manager.destroy_session(session_id)
        return json.dumps({"session_id": session_id, "status": "ended"})

    @mcp.tool()
    async def gdb_run(
        session_id: str,
        stop_at_main: bool = True,
        ctx: Context = None,
    ) -> str:
        """Start program execution in GDB.

        Args:
            session_id: The session identifier.
            stop_at_main: If true, stop at the beginning of main().
        """
        manager = ctx.request_context.lifespan_context["gdb"]
        ctrl = manager.get_session(session_id)

        if stop_at_main:
            responses = await ctrl.send_command("-exec-run --start")
        else:
            responses = await ctrl.send_command("-exec-run")

        return _fmt(ctrl, responses)

    @mcp.tool()
    async def gdb_set_breakpoint(
        session_id: str,
        location: str,
        condition: str = "",
        ctx: Context = None,
    ) -> str:
        """Set a breakpoint at a location.

        Args:
            session_id: The session identifier.
            location: Where to break. Accepts "file:line" (e.g. "main.cpp:42"), function name (e.g. "main"), or address.
            condition: Optional C++ condition expression (e.g. "i > 10").
        """
        manager = ctx.request_context.lifespan_context["gdb"]
        ctrl = manager.get_session(session_id)

        cmd = "-break-insert"
        if condition:
            cmd += f" -c {condition}"
        cmd += f" {location}"

        responses = await ctrl.send_command(cmd)
        payload = _payload(responses)

        if isinstance(payload, dict) and "bkpt" in payload:
            bkpt = payload["bkpt"]
            return json.dumps({
                "breakpoint_id": bkpt.get("number"),
                "file": bkpt.get("file", ""),
                "line": bkpt.get("line", ""),
                "function": bkpt.get("func", ""),
            })
        return _fmt(ctrl, responses)

    @mcp.tool()
    async def gdb_delete_breakpoint(
        session_id: str,
        breakpoint_id: int,
        ctx: Context = None,
    ) -> str:
        """Delete a breakpoint.

        Args:
            session_id: The session identifier.
            breakpoint_id: The breakpoint number to delete.
        """
        manager = ctx.request_context.lifespan_context["gdb"]
        ctrl = manager.get_session(session_id)
        responses = await ctrl.send_command(f"-break-delete {breakpoint_id}")
        return _fmt(ctrl, responses)

    @mcp.tool()
    async def gdb_list_breakpoints(session_id: str, ctx: Context = None) -> str:
        """List all breakpoints in the session.

        Args:
            session_id: The session identifier.
        """
        manager = ctx.request_context.lifespan_context["gdb"]
        ctrl = manager.get_session(session_id)
        responses = await ctrl.send_command("-break-list")
        payload = _payload(responses)

        if isinstance(payload, dict) and "BreakpointTable" in payload:
            table = payload["BreakpointTable"]
            breakpoints = table.get("body", [])
            result = []
            for bp in breakpoints:
                result.append({
                    "id": bp.get("number"),
                    "type": bp.get("type"),
                    "enabled": bp.get("enabled"),
                    "location": f"{bp.get('file', '?')}:{bp.get('line', '?')}",
                    "function": bp.get("func", ""),
                    "condition": bp.get("cond", ""),
                    "hit_count": bp.get("times", "0"),
                })
            return json.dumps(result, indent=2)
        return _fmt(ctrl, responses)

    @mcp.tool()
    async def gdb_continue(session_id: str, ctx: Context = None) -> str:
        """Continue program execution until next breakpoint or exit.

        Args:
            session_id: The session identifier.
        """
        manager = ctx.request_context.lifespan_context["gdb"]
        ctrl = manager.get_session(session_id)
        responses = await ctrl.send_command("-exec-continue")
        return _fmt(ctrl, responses)

    @mcp.tool()
    async def gdb_step(
        session_id: str,
        mode: str = "into",
        ctx: Context = None,
    ) -> str:
        """Step through program execution.

        Args:
            session_id: The session identifier.
            mode: Step mode - "into" (step into functions), "over" (step over functions), "out" (step out of current function).
        """
        manager = ctx.request_context.lifespan_context["gdb"]
        ctrl = manager.get_session(session_id)

        cmd_map = {
            "into": "-exec-step",
            "over": "-exec-next",
            "out": "-exec-finish",
        }
        cmd = cmd_map.get(mode)
        if not cmd:
            return f"Invalid step mode: {mode}. Use 'into', 'over', or 'out'."

        responses = await ctrl.send_command(cmd)
        return _fmt(ctrl, responses)

    @mcp.tool()
    async def gdb_backtrace(
        session_id: str,
        max_frames: int = 20,
        ctx: Context = None,
    ) -> str:
        """Get the current call stack (backtrace).

        Args:
            session_id: The session identifier.
            max_frames: Maximum number of frames to return.
        """
        manager = ctx.request_context.lifespan_context["gdb"]
        ctrl = manager.get_session(session_id)
        responses = await ctrl.send_command(f"-stack-list-frames 0 {max_frames - 1}")
        payload = _payload(responses)

        if isinstance(payload, dict) and "stack" in payload:
            frames = payload["stack"]
            result = []
            for frame_entry in frames:
                frame = frame_entry.get("frame", frame_entry) if isinstance(frame_entry, dict) else frame_entry
                result.append({
                    "level": frame.get("level"),
                    "function": frame.get("func", "??"),
                    "file": frame.get("file", ""),
                    "line": frame.get("line", ""),
                    "address": frame.get("addr", ""),
                })
            return json.dumps(result, indent=2)
        return _fmt(ctrl, responses)

    @mcp.tool()
    async def gdb_list_variables(
        session_id: str,
        frame: int = 0,
        ctx: Context = None,
    ) -> str:
        """List local variables in a stack frame.

        Args:
            session_id: The session identifier.
            frame: Stack frame number (0 = current frame).
        """
        manager = ctx.request_context.lifespan_context["gdb"]
        ctrl = manager.get_session(session_id)

        if frame != 0:
            await ctrl.send_command(f"-stack-select-frame {frame}")

        responses = await ctrl.send_command("-stack-list-variables --simple-values")
        payload = _payload(responses)

        if isinstance(payload, dict) and "variables" in payload:
            variables = payload["variables"]
            result = []
            for var in variables:
                result.append({
                    "name": var.get("name"),
                    "type": var.get("type", ""),
                    "value": var.get("value", ""),
                })
            return json.dumps(result, indent=2)
        return _fmt(ctrl, responses)

    @mcp.tool()
    async def gdb_evaluate(
        session_id: str,
        expression: str,
        ctx: Context = None,
    ) -> str:
        """Evaluate a C++ expression in the current debugging context.

        Args:
            session_id: The session identifier.
            expression: C++ expression to evaluate (e.g. "x + y", "arr[5]", "*ptr").
        """
        manager = ctx.request_context.lifespan_context["gdb"]
        ctrl = manager.get_session(session_id)
        responses = await ctrl.send_command(f'-data-evaluate-expression "{expression}"')
        payload = _payload(responses)

        if isinstance(payload, dict) and "value" in payload:
            return payload["value"]
        return _fmt(ctrl, responses)

    @mcp.tool()
    async def gdb_read_memory(
        session_id: str,
        address: str,
        count: int = 64,
        ctx: Context = None,
    ) -> str:
        """Read raw memory at an address.

        Args:
            session_id: The session identifier.
            address: Memory address (e.g. "0x7fff5fbff8a0" or "&variable").
            count: Number of bytes to read.
        """
        manager = ctx.request_context.lifespan_context["gdb"]
        ctrl = manager.get_session(session_id)
        responses = await ctrl.send_command(f"-data-read-memory-bytes {address} {count}")
        payload = _payload(responses)

        if isinstance(payload, dict) and "memory" in payload:
            memory = payload["memory"]
            result = []
            for block in memory:
                result.append({
                    "begin": block.get("begin"),
                    "end": block.get("end"),
                    "contents": block.get("contents"),
                })
            return json.dumps(result, indent=2)
        return _fmt(ctrl, responses)

    @mcp.tool()
    async def gdb_thread_info(session_id: str, ctx: Context = None) -> str:
        """List all threads and their states.

        Args:
            session_id: The session identifier.
        """
        manager = ctx.request_context.lifespan_context["gdb"]
        ctrl = manager.get_session(session_id)
        responses = await ctrl.send_command("-thread-info")
        payload = _payload(responses)

        if isinstance(payload, dict) and "threads" in payload:
            threads = payload["threads"]
            result = []
            for t in threads:
                frame = t.get("frame", {})
                result.append({
                    "id": t.get("id"),
                    "name": t.get("name", ""),
                    "state": t.get("state", ""),
                    "function": frame.get("func", ""),
                    "file": frame.get("file", ""),
                    "line": frame.get("line", ""),
                })
            return json.dumps(result, indent=2)
        return _fmt(ctrl, responses)

    @mcp.tool()
    async def gdb_raw_command(
        session_id: str,
        command: str,
        ctx: Context = None,
    ) -> str:
        """Execute a raw GDB command (with safety restrictions).

        Blocked commands: shell, python, pipe, source.

        Args:
            session_id: The session identifier.
            command: The GDB command to execute.
        """
        manager = ctx.request_context.lifespan_context["gdb"]
        ctrl = manager.get_session(session_id)
        responses = await ctrl.send_raw_command(command)
        return _fmt(ctrl, responses)
