import json
from models.schemas import Phase
from tools.registry import get_permitted_tools

_SYSTEM = """You are an autonomous research agent.

Current phase: {phase}
Phase goal: {goal}

Permitted tools in this phase ONLY:
{tools}

STRICT RULES:
- You MUST only call tools listed above. Calling any other tool halts the session immediately.
- report_write is ONLY permitted in the synthesis phase. Never call it in any other phase.
- web_search and url_fetch are NOT permitted in synthesis phase. Do not call them.
- In synthesis phase: first call memory_read to retrieve your findings, then call report_write to write the report.
- memory_write stores findings with content_type: "finding" or "contradiction".
- report_write requires: section (string) and content (string). Example: section="findings", content="your report text here".
- Do NOT repeat the exact same tool call with identical arguments 3 times in a row.
- If a URL returns 403 or 404, do not retry it. Move on immediately.

Return ONLY a valid JSON object. No prose. No markdown. No extra text.
Schema:
{{
  "thought": "your reasoning",
  "action": "tool_name",
  "arguments": {{"key": "value"}},
  "confidence": "low | medium | high"
}}"""

_USER = """Topic: {topic}

Recent context:
{window}

Relevant memory:
{memory}

Last tool result:
{last_result}

What is your next action? Return JSON only."""


def build_prompt(phase: Phase, goal: str, topic: str,
                 window: list[dict], memory: list[dict],
                 last_result: dict | None) -> tuple[str, str]:
    permitted = get_permitted_tools(phase)
    tool_list = "\n".join(f"  - {t}" for t in permitted)

    system = _SYSTEM.format(
        phase=phase.value,
        goal=goal,
        tools=tool_list
    )

    user = _USER.format(
        topic=topic,
        window=_format_window(window),
        memory=_format_memory(memory),
        last_result=_format_result(last_result)
    )

    return system, user


def _format_window(window: list[dict]) -> str:
    if not window:
        return "None"
    lines = []
    for e in window[-8:]:
        lines.append(f"[{e['role'].upper()}] {e['content'][:250]}")
    return "\n".join(lines)


def _format_memory(memory: list[dict]) -> str:
    if not memory:
        return "No memory found. Use memory_read to retrieve past findings before writing the report."
    lines = []
    for m in memory:
        lines.append(
            f"- [{m['range']}] {m['summary']}"
            f" | topics: {', '.join(m['main_topics'][:3])}"
            f" | decisions: {', '.join(m['key_decisions'][:2])}"
        )
    return "\n".join(lines)


def _format_result(result: dict | None) -> str:
    if not result:
        return "None"
    if not result.get("success"):
        return f"FAILED: {result.get('error', 'unknown')} — do not retry this URL"
    data = result.get("data", "")
    if isinstance(data, list):
        lines = [f"- {r.get('title', '')}: {r.get('snippet', '')[:150]}"
                 for r in data[:3]]
        return "\n".join(lines)
    if isinstance(data, dict):
        return json.dumps(data)[:400]
    return str(data)[:400]