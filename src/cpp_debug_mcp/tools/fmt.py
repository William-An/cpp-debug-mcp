"""Human-readable output formatting for MCP tool results."""

from typing import Any


def section(title: str, content: str) -> str:
    """Format a titled section."""
    return f"── {title} ──\n{content}"


def kv(key: str, value: Any, indent: int = 0) -> str:
    """Format a key-value pair."""
    prefix = "  " * indent
    return f"{prefix}{key}: {value}"


def fmt_session_start(kind: str, session_id: str, details: str = "") -> str:
    lines = [
        section(f"{kind} Session Started", kv("Session ID", session_id)),
    ]
    if details:
        lines.append(details)
    return "\n".join(lines)


def fmt_session_end(kind: str, session_id: str) -> str:
    return f"── {kind} Session Ended ──\n{kv('Session ID', session_id)}"


def fmt_breakpoint(bp: dict) -> str:
    loc = f"{bp.get('file', '?')}:{bp.get('line', '?')}"
    func = bp.get("function") or bp.get("func", "")
    cond = bp.get("condition") or bp.get("cond", "")
    lines = [
        kv("Breakpoint", f"#{bp.get('breakpoint_id', bp.get('id', '?'))}"),
        kv("Location", loc, indent=1),
    ]
    if func:
        lines.append(kv("Function", func, indent=1))
    if cond:
        lines.append(kv("Condition", cond, indent=1))
    return "\n".join(lines)


def fmt_breakpoint_list(breakpoints: list[dict]) -> str:
    if not breakpoints:
        return "No breakpoints set."
    lines = [f"── Breakpoints ({len(breakpoints)}) ──"]
    for bp in breakpoints:
        enabled = bp.get("enabled", "y")
        status = "ON" if enabled == "y" else "OFF"
        loc = bp.get("location", f"{bp.get('file', '?')}:{bp.get('line', '?')}")
        func = bp.get("function", "")
        hits = bp.get("hit_count", "0")
        entry = f"  #{bp.get('id', '?')} [{status}]  {loc}"
        if func:
            entry += f"  ({func})"
        entry += f"  hits={hits}"
        cond = bp.get("condition", "")
        if cond:
            entry += f"  if {cond}"
        lines.append(entry)
    return "\n".join(lines)


def fmt_backtrace(frames: list[dict]) -> str:
    if not frames:
        return "No stack frames."
    lines = [f"── Backtrace ({len(frames)} frames) ──"]
    for f in frames:
        level = f.get("level", "?")
        func = f.get("function", "??")
        file_ = f.get("file", "")
        line = f.get("line", "")
        addr = f.get("address", "")
        loc = f"{file_}:{line}" if file_ else addr
        lines.append(f"  #{level}  {func}  at {loc}")
    return "\n".join(lines)


def fmt_variables(variables: list[dict]) -> str:
    if not variables:
        return "No local variables."
    lines = [f"── Local Variables ({len(variables)}) ──"]
    for v in variables:
        name = v.get("name", "?")
        typ = v.get("type", "")
        val = v.get("value", "")
        if typ:
            lines.append(f"  {typ} {name} = {val}")
        else:
            lines.append(f"  {name} = {val}")
    return "\n".join(lines)


def fmt_evaluate(expression: str, value: str) -> str:
    return f"{expression} = {value}"


def fmt_memory(blocks: list[dict]) -> str:
    if not blocks:
        return "No memory data."
    lines = ["── Memory ──"]
    for block in blocks:
        begin = block.get("begin", "?")
        end = block.get("end", "")
        contents = block.get("contents", "")
        lines.append(f"  {begin}:")
        # Format hex contents in groups of 16 bytes (32 hex chars)
        for i in range(0, len(contents), 32):
            chunk = contents[i:i+32]
            # Add spaces every 2 hex chars for readability
            spaced = " ".join(chunk[j:j+2] for j in range(0, len(chunk), 2))
            offset = i // 2
            lines.append(f"    +{offset:04x}  {spaced}")
    return "\n".join(lines)


def fmt_threads(threads: list[dict]) -> str:
    if not threads:
        return "No threads."
    lines = [f"── Threads ({len(threads)}) ──"]
    for t in threads:
        tid = t.get("id", "?")
        name = t.get("name", "")
        state = t.get("state", "")
        func = t.get("function", "")
        file_ = t.get("file", "")
        line = t.get("line", "")
        loc = f"at {file_}:{line}" if file_ else ""
        name_str = f" ({name})" if name else ""
        lines.append(f"  Thread {tid}{name_str}  [{state}]  {func}  {loc}".rstrip())
    return "\n".join(lines)


def fmt_diagnostics(diagnostics: list[dict]) -> str:
    if not diagnostics:
        return "No diagnostics (clean)."
    # Count by severity
    errors = sum(1 for d in diagnostics if d.get("severity") == "error")
    warnings = sum(1 for d in diagnostics if d.get("severity") == "warning")
    others = len(diagnostics) - errors - warnings
    summary = []
    if errors:
        summary.append(f"{errors} error(s)")
    if warnings:
        summary.append(f"{warnings} warning(s)")
    if others:
        summary.append(f"{others} other")
    lines = [f"── Diagnostics ({', '.join(summary)}) ──"]
    for d in diagnostics:
        sev = d.get("severity", "?").upper()
        line = d.get("line", 0) + 1  # Convert 0-indexed to 1-indexed for display
        col = d.get("column", 0) + 1
        msg = d.get("message", "")
        src = d.get("source", "")
        file_ = d.get("file", "")
        loc = f"{file_}:{line}:{col}" if file_ else f":{line}:{col}"
        src_str = f" [{src}]" if src else ""
        lines.append(f"  {sev}{src_str} {loc}")
        lines.append(f"    {msg}")
    return "\n".join(lines)


def fmt_hover(hover: dict) -> str:
    contents = hover.get("contents", "")
    lang = hover.get("language", "")
    if not contents:
        return "No hover information."
    if lang:
        return f"── Type Info ({lang}) ──\n  {contents}"
    return f"── Type Info ──\n  {contents}"


def fmt_locations(locations: list[dict], title: str = "Locations") -> str:
    if not locations:
        return f"No {title.lower()} found."
    lines = [f"── {title} ({len(locations)}) ──"]
    for loc in locations:
        file_ = loc.get("file", "?")
        line = loc.get("line", 0) + 1  # 0-indexed to 1-indexed
        col = loc.get("column", 0) + 1
        lines.append(f"  {file_}:{line}:{col}")
    return "\n".join(lines)


def fmt_symbols(symbols: list[dict], indent: int = 0) -> str:
    if not symbols:
        return "No symbols found."
    lines = []
    if indent == 0:
        lines.append(f"── Symbols ({len(symbols)}) ──")
    for s in symbols:
        prefix = "  " * (indent + 1)
        kind = s.get("kind", "?")
        name = s.get("name", "?")
        line = s.get("line", 0) + 1
        lines.append(f"{prefix}{kind} {name}  (line {line})")
        children = s.get("children", [])
        if children:
            lines.append(fmt_symbols(children, indent + 1))
    return "\n".join(lines)


def fmt_signature_help(data: dict) -> str:
    sigs = data.get("signatures", [])
    if not sigs:
        return "No signature information."
    active_sig = data.get("active_signature", 0)
    active_param = data.get("active_parameter", 0)
    lines = [f"── Signature Help ──"]
    for i, sig in enumerate(sigs):
        marker = "▸" if i == active_sig else " "
        lines.append(f"  {marker} {sig.get('label', '?')}")
        for j, p in enumerate(sig.get("parameters", [])):
            param_marker = "▸" if i == active_sig and j == active_param else " "
            doc = p.get("documentation", "")
            label = p.get("label", "?")
            doc_str = f"  — {doc}" if doc else ""
            lines.append(f"    {param_marker} {label}{doc_str}")
    return "\n".join(lines)


def fmt_crash_report(report: dict) -> str:
    lines = ["══ Crash Diagnosis Report ══"]

    # Thread info
    thread = report.get("current_thread", {})
    if thread:
        lines.append("")
        lines.append(section("Current Thread", "\n".join([
            kv("ID", thread.get("id", "?"), indent=1),
            kv("State", thread.get("state", "?"), indent=1),
        ])))

    # Backtrace
    bt = report.get("backtrace", [])
    if bt:
        lines.append("")
        lines.append(fmt_backtrace(bt))

    # Local variables
    local_vars = report.get("local_variables", [])
    if local_vars:
        lines.append("")
        lines.append(fmt_variables(local_vars))

    # Static diagnostics
    diags = report.get("static_diagnostics", {})
    if diags:
        lines.append("")
        for file_path, file_diags in diags.items():
            lines.append(f"── Diagnostics: {file_path} ──")
            for d in file_diags:
                sev = d.get("severity", "?").upper()
                line = d.get("line", 0) + 1
                msg = d.get("message", "")
                lines.append(f"  {sev} :{line}  {msg}")

    return "\n".join(lines)


def fmt_variable_info(info: dict) -> str:
    lines = [f"── Variable: {info.get('variable', '?')} ──"]
    lines.append(kv("Runtime Value", info.get("runtime_value", "N/A"), indent=1))
    type_info = info.get("type_info", {})
    if type_info:
        lines.append(kv("Type", type_info.get("contents", "?"), indent=1))
    defn = info.get("definition", {})
    if defn:
        lines.append(kv("Defined at", f"{defn.get('file', '?')}:{defn.get('line', 0) + 1}", indent=1))
    return "\n".join(lines)


def fmt_function_analysis(info: dict) -> str:
    lines = [f"── Function: {info.get('function', '?')} ──"]

    bp = info.get("breakpoint", {})
    if bp:
        loc = f"{bp.get('file', '?')}:{bp.get('line', '?')}"
        lines.append(kv("Location", loc, indent=1))
        lines.append(kv("Breakpoint", f"#{bp.get('id', '?')} (temporary)", indent=1))

    sig = info.get("signature", {})
    if sig:
        lines.append(kv("Signature", sig.get("contents", ""), indent=1))

    refs = info.get("references", [])
    if refs:
        lines.append(f"  References ({len(refs)}):")
        for r in refs[:10]:
            lines.append(f"    {r.get('file', '?')}:{r.get('line', 0) + 1}")
        if len(refs) > 10:
            lines.append(f"    ... and {len(refs) - 10} more")

    local_vars = info.get("local_variables", [])
    if local_vars:
        lines.append("")
        lines.append(fmt_variables(local_vars))

    return "\n".join(lines)
