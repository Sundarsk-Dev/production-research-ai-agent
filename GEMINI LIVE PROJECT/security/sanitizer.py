import re
import json
from storage import db

# ── Injection pattern list ────────────────────────────────────
# These patterns in tool output could trick the LLM into treating
# data as instructions. Detected = flagged + stripped.

_INJECTION_PATTERNS = [
    r"ignore (all |previous |above )?instructions",
    r"you are now",
    r"new persona",
    r"system prompt",
    r"disregard (your |all )?",
    r"forget (everything|your instructions)",
    r"act as (a |an )?",
    r"jailbreak",
    r"<\|.*?\|>",          # token boundary attacks
    r"\[INST\]",           # llama instruction tags
    r"###\s*(instruction|system|human|assistant)",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]

# Max characters returned from any single tool result
# Prevents context flooding
_MAX_OUTPUT_LENGTH = 8000


def sanitize_tool_output(raw: any, session_id: str) -> any:
    """
    Sanitizes tool output before it enters LLM context.
    Works on strings, lists, and dicts recursively.
    Logs any injection attempt to audit log.
    """
    if isinstance(raw, str):
        return _sanitize_string(raw, session_id)

    if isinstance(raw, list):
        return [sanitize_tool_output(item, session_id) for item in raw]

    if isinstance(raw, dict):
        return {k: sanitize_tool_output(v, session_id) for k, v in raw.items()}

    return raw  # int, float, bool — pass through


def _sanitize_string(text: str, session_id: str) -> str:
    # ── Truncate ──────────────────────────────────────────────
    if len(text) > _MAX_OUTPUT_LENGTH:
        text = text[:_MAX_OUTPUT_LENGTH] + "\n[TRUNCATED]"

    # ── Injection detection ───────────────────────────────────
    for pattern in _COMPILED:
        if pattern.search(text):
            db.insert_audit(session_id, "INJECTION", {
                "pattern": pattern.pattern,
                "preview": text[:200]
            })
            # Strip the matched segment rather than reject entirely
            text = pattern.sub("[REDACTED]", text)

    return text.strip()