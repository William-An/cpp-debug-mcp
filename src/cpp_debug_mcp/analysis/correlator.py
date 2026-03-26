"""Cross-reference GDB runtime state with LSP static analysis."""

import json
from typing import Any

from ..gdb.controller import GdbMiController
from ..lsp.client import ClangdClient
from ..lsp.protocol import (
    file_uri,
    make_did_open,
    make_text_document_position,
    make_reference_params,
    parse_diagnostic,
    parse_hover,
    parse_location,
)
from pathlib import Path


async def ensure_file_open(
    client: ClangdClient,
    file_path: str,
    opened_files: set[str],
) -> None:
    """Open a file in clangd if not already opened."""
    uri = file_uri(file_path)
    if uri not in opened_files:
        try:
            content = Path(file_path).resolve().read_text()
        except (FileNotFoundError, OSError):
            return
        lang = "c" if file_path.endswith(".c") else "cpp"
        await client.send_notification(
            "textDocument/didOpen",
            make_did_open(file_path, content, lang),
        )
        opened_files.add(uri)


async def get_crash_report(
    gdb_ctrl: GdbMiController,
    lsp_client: ClangdClient,
    opened_files: set[str],
    max_frames: int = 5,
) -> dict[str, Any]:
    """Build a crash diagnosis report combining GDB backtrace with LSP info.

    Returns a structured report with:
    - stop_reason and signal info
    - backtrace with per-frame type info from LSP
    - local variables at crash site
    - static diagnostics for relevant files
    """
    report: dict[str, Any] = {}

    # Get stop reason from GDB
    stop_responses = await gdb_ctrl.send_command("-thread-info")
    for r in stop_responses:
        if r.get("type") == "result" and isinstance(r.get("payload"), dict):
            threads = r["payload"].get("threads", [])
            if threads:
                current = threads[0]
                report["current_thread"] = {
                    "id": current.get("id"),
                    "state": current.get("state"),
                    "name": current.get("name", ""),
                }

    # Get backtrace
    bt_responses = await gdb_ctrl.send_command(f"-stack-list-frames 0 {max_frames - 1}")
    frames = []
    for r in bt_responses:
        if r.get("type") == "result" and isinstance(r.get("payload"), dict):
            stack = r["payload"].get("stack", [])
            for frame_entry in stack:
                frame = frame_entry.get("frame", frame_entry) if isinstance(frame_entry, dict) else frame_entry
                frames.append({
                    "level": frame.get("level"),
                    "function": frame.get("func", "??"),
                    "file": frame.get("file", ""),
                    "fullname": frame.get("fullname", ""),
                    "line": frame.get("line", ""),
                    "address": frame.get("addr", ""),
                })

    report["backtrace"] = frames

    # Get local variables at crash frame
    try:
        var_responses = await gdb_ctrl.send_command("-stack-list-variables --simple-values")
        for r in var_responses:
            if r.get("type") == "result" and isinstance(r.get("payload"), dict):
                report["local_variables"] = r["payload"].get("variables", [])
    except Exception:
        report["local_variables"] = []

    # Enrich with LSP info for each frame
    diagnostics_by_file: dict[str, list] = {}
    for frame in frames:
        file_path = frame.get("fullname") or frame.get("file", "")
        if not file_path or not Path(file_path).exists():
            continue

        await ensure_file_open(lsp_client, file_path, opened_files)

        # Get hover info at crash line
        line = frame.get("line", "")
        if line:
            try:
                hover_result = await lsp_client.send_request(
                    "textDocument/hover",
                    make_text_document_position(file_path, int(line) - 1, 0),
                    timeout=5.0,
                )
                hover = parse_hover(hover_result)
                if hover:
                    frame["type_info"] = hover.to_dict()
            except Exception:
                pass

        # Collect diagnostics per file (once per file)
        if file_path not in diagnostics_by_file:
            notif = await lsp_client.wait_for_notification(
                "textDocument/publishDiagnostics", timeout=5.0
            )
            if notif and "diagnostics" in notif:
                diagnostics_by_file[file_path] = [
                    parse_diagnostic(d, file_path).to_dict()
                    for d in notif["diagnostics"]
                ]

    report["static_diagnostics"] = diagnostics_by_file
    return report


async def get_variable_info(
    gdb_ctrl: GdbMiController,
    lsp_client: ClangdClient,
    opened_files: set[str],
    variable_name: str,
    file_path: str,
    line: int,
) -> dict[str, Any]:
    """Get combined runtime value (GDB) and type info (LSP) for a variable."""
    result: dict[str, Any] = {"variable": variable_name}

    # GDB: evaluate the variable
    try:
        eval_responses = await gdb_ctrl.send_command(
            f'-data-evaluate-expression "{variable_name}"'
        )
        for r in eval_responses:
            if r.get("type") == "result" and isinstance(r.get("payload"), dict):
                result["runtime_value"] = r["payload"].get("value", "")
    except Exception as e:
        result["runtime_value"] = f"(error: {e})"

    # LSP: hover for type info
    if file_path and Path(file_path).exists():
        await ensure_file_open(lsp_client, file_path, opened_files)
        try:
            hover_result = await lsp_client.send_request(
                "textDocument/hover",
                make_text_document_position(file_path, line - 1, 0),
                timeout=5.0,
            )
            hover = parse_hover(hover_result)
            if hover:
                result["type_info"] = hover.to_dict()
        except Exception:
            pass

        # LSP: go to definition
        try:
            def_result = await lsp_client.send_request(
                "textDocument/definition",
                make_text_document_position(file_path, line - 1, 0),
                timeout=5.0,
            )
            if isinstance(def_result, list) and def_result:
                loc = parse_location(def_result[0])
                result["definition"] = loc.to_dict()
        except Exception:
            pass

    return result


async def analyze_function_info(
    gdb_ctrl: GdbMiController,
    lsp_client: ClangdClient,
    opened_files: set[str],
    function_name: str,
) -> dict[str, Any]:
    """Analyze a function using both GDB and LSP.

    Sets a temporary breakpoint, gets LSP definition/references, and if stopped
    at the function, retrieves local variables.
    """
    result: dict[str, Any] = {"function": function_name}

    # Set a temporary breakpoint at the function
    try:
        bp_responses = await gdb_ctrl.send_command(f"-break-insert -t {function_name}")
        for r in bp_responses:
            if r.get("type") == "result" and isinstance(r.get("payload"), dict):
                bkpt = r["payload"].get("bkpt", {})
                result["breakpoint"] = {
                    "id": bkpt.get("number"),
                    "file": bkpt.get("file", ""),
                    "fullname": bkpt.get("fullname", ""),
                    "line": bkpt.get("line", ""),
                }
                file_path = bkpt.get("fullname", bkpt.get("file", ""))
                line = bkpt.get("line", "")
    except Exception as e:
        result["breakpoint_error"] = str(e)
        file_path = ""
        line = ""

    # LSP: get definition and references
    if file_path and Path(file_path).exists():
        await ensure_file_open(lsp_client, file_path, opened_files)

        if line:
            try:
                hover_result = await lsp_client.send_request(
                    "textDocument/hover",
                    make_text_document_position(file_path, int(line) - 1, 0),
                    timeout=5.0,
                )
                hover = parse_hover(hover_result)
                if hover:
                    result["signature"] = hover.to_dict()
            except Exception:
                pass

            try:
                refs = await lsp_client.send_request(
                    "textDocument/references",
                    make_reference_params(file_path, int(line) - 1, 0),
                    timeout=5.0,
                )
                if isinstance(refs, list):
                    result["references"] = [
                        parse_location(r).to_dict() for r in refs[:20]
                    ]
            except Exception:
                pass

    # Try to get local variables if we're stopped at the function
    try:
        var_responses = await gdb_ctrl.send_command("-stack-list-variables --simple-values")
        for r in var_responses:
            if r.get("type") == "result" and isinstance(r.get("payload"), dict):
                result["local_variables"] = r["payload"].get("variables", [])
    except Exception:
        pass

    return result
