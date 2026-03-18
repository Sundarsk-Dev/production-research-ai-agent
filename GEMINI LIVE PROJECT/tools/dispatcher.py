import json
from models.schemas import AgentDecision, ToolResult, Phase
from tools.registry import is_permitted, TOOL_REGISTRY
from security.sanitizer import sanitize_tool_output
from security.audit import log_permission_denied
from storage import db


def dispatch(decision: AgentDecision, phase: Phase, session_id: str) -> ToolResult:
    """
    Central execution gate. Three checks before any tool runs:
      1. Tool exists in registry
      2. Tool is permitted in current phase
      3. Arguments match expected keys

    On any failure — log audit event, return failed ToolResult.
    Never raise exceptions outward — caller always gets a ToolResult.
    """
    tool = decision.action
    args = decision.arguments

    # ── Check 1: tool exists ──────────────────────────────────
    if tool not in TOOL_REGISTRY:
        log_permission_denied(session_id, phase, tool, "tool not in registry")
        return ToolResult(tool=tool, success=False, data={},
                          error=f"Unknown tool: {tool}")

    # ── Check 2: phase permission ─────────────────────────────
    if not is_permitted(tool, phase):
        log_permission_denied(session_id, phase, tool, "not permitted in phase")
        db.insert_audit(session_id, "PERMISSION_DENIED", {
            "tool": tool, "phase": phase, "reason": "phase restriction"
        })
        return ToolResult(tool=tool, success=False, data={},
                          error=f"Tool '{tool}' not permitted in phase '{phase}'")

    # ── Check 3: argument validation ──────────────────────────
    expected = set(TOOL_REGISTRY[tool]["args"])
    provided = set(args.keys())
    missing = expected - provided
    if missing:
        log_permission_denied(session_id, phase, tool, f"missing args: {missing}")
        return ToolResult(tool=tool, success=False, data={},
                          error=f"Missing arguments: {missing}")

    # ── Execute ───────────────────────────────────────────────
    try:
        raw_result = _execute(tool, args)
    except Exception as e:
        db.insert_event(session_id, phase, "TOOL_ERROR", {
            "tool": tool, "args": args, "error": str(e)
        })
        return ToolResult(tool=tool, success=False, data={}, error=str(e))

    # ── Sanitize before returning to LLM context ──────────────
    clean_result = sanitize_tool_output(raw_result, session_id)

    db.insert_event(session_id, phase, "TOOL_SUCCESS", {
        "tool": tool, "args": args
    })

    return ToolResult(tool=tool, success=True, data=clean_result)


def _execute(tool: str, args: dict):
    """Routes to the actual tool implementation."""
    if tool == "web_search":
        from tools.search import web_search
        return web_search(args["query"])

    if tool == "url_fetch":
        from tools.search import url_fetch
        return url_fetch(args["url"])

    if tool == "memory_read":
        from memory.retriever import search_memory
        return search_memory(args["query"], args.get("session_id", ""))

    if tool == "memory_write":
        # memory_write is handled by the loop directly with full context
        # dispatcher signals it is approved, loop handles the write
        return {"status": "approved", "content_type": args["content_type"]}

    if tool == "report_write":
        # Same pattern — loop handles actual write with session context
        return {"status": "approved", "section": args["section"]}

    raise ValueError(f"No implementation for tool: {tool}")