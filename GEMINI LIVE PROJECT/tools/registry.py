from models.schemas import Phase

PHASE_PERMISSIONS: dict[Phase, list[str]] = {
    Phase.DISCOVERY:      ["web_search", "url_fetch"],
    Phase.INVESTIGATION:  ["web_search", "url_fetch", "memory_read"],
    Phase.CONTRADICTION:  ["web_search", "url_fetch", "memory_read", "memory_write"],
    Phase.SYNTHESIS:      ["memory_read", "memory_write", "report_write"],
}

TOOL_REGISTRY: dict[str, dict] = {
    "web_search": {
        "description": "Search the web. Required args: query (string).",
        "args": ["query"],
    },
    "url_fetch": {
        "description": "Fetch text from a URL. Required args: url (string).",
        "args": ["url"],
    },
    "memory_read": {
        "description": "Search memory for past findings. Required args: query (string).",
        "args": ["query"],
    },
    "memory_write": {
        "description": (
            "Store a finding or contradiction. "
            "Required args: content (string), content_type (string — use 'finding' or 'contradiction')."
        ),
        "args": ["content", "content_type"],
    },
    "report_write": {
        "description": (
            "Write a section of the final report. ONLY call this in synthesis phase. "
            "Required args: section (string — e.g. 'summary', 'findings', 'contradictions'), "
            "content (string — the text to write for this section)."
        ),
        "args": ["section", "content"],
    },
}


def is_permitted(tool: str, phase: Phase) -> bool:
    return tool in PHASE_PERMISSIONS.get(phase, [])


def get_tool_descriptions() -> str:
    lines = []
    for name, meta in TOOL_REGISTRY.items():
        lines.append(f"- {name}: {meta['description']}")
    return "\n".join(lines)


def get_permitted_tools(phase: Phase) -> list[str]:
    return PHASE_PERMISSIONS.get(phase, [])