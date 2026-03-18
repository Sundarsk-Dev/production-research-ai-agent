import os
import json
from dotenv import load_dotenv
load_dotenv()

import google.generativeai as genai
from models.schemas import Plan, PlanPhase, Phase, Depth
from storage import db

genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
_model = genai.GenerativeModel("gemini-2.5-flash-lite")

_PHASE_LIMITS = {
    Phase.DISCOVERY:      10,
    Phase.INVESTIGATION:  15,
    Phase.CONTRADICTION:  8,
    Phase.SYNTHESIS:      5,
}

_PHASE_GOALS = {
    Phase.DISCOVERY:     "Find at least 5 credible sources on the topic.",
    Phase.INVESTIGATION: "Deepen findings — every key claim needs 2+ sources.",
    Phase.CONTRADICTION: "Find and log all conflicting claims across sources.",
    Phase.SYNTHESIS:     "Assemble verified report with confidence scores.",
}


def generate_plan(session_id: str, topic: str, depth: Depth) -> Plan:
    """Always uses default plan — avoids LLM generating wrong permissions."""
    multiplier = {"shallow": 0.5, "standard": 1.0, "deep": 1.5}[depth.value]
    plan = _default_plan(session_id, topic, multiplier)
    db.insert_plan(session_id, plan.model_dump())
    return plan


def get_phase_config(plan: Plan, phase: Phase) -> PlanPhase | None:
    for p in plan.phases:
        if p.phase == phase:
            return p
    return None


def get_phase_goal(phase: Phase) -> str:
    return _PHASE_GOALS.get(phase, "Complete the current phase.")


def next_phase(current: Phase) -> Phase | None:
    order = [Phase.DISCOVERY, Phase.INVESTIGATION,
             Phase.CONTRADICTION, Phase.SYNTHESIS]
    idx = order.index(current)
    return order[idx + 1] if idx + 1 < len(order) else None


def _default_plan(session_id: str, topic: str, multiplier: float) -> Plan:
    configs = [
        (Phase.DISCOVERY,
         ["web_search", "url_fetch"],
         "5 sources found"),
        (Phase.INVESTIGATION,
         ["web_search", "url_fetch", "memory_read"],
         "all claims have 2+ sources"),
        (Phase.CONTRADICTION,
         ["web_search", "url_fetch", "memory_read", "memory_write"],
         "contradictions logged"),
        (Phase.SYNTHESIS,
         ["memory_read", "report_write"],
         "report complete"),
    ]
    phases = [
        PlanPhase(
            phase=p,
            goal=_PHASE_GOALS[p],
            permitted_tools=t,
            max_iterations=int(_PHASE_LIMITS[p] * multiplier),
            success_criteria=c
        )
        for p, t, c in configs
    ]
    return Plan(session_id=session_id, topic=topic, phases=phases)