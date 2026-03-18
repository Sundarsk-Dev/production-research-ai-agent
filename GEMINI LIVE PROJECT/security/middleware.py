import hashlib
import json
import time
import requests
from models.schemas import AgentDecision, DeviationAlert, Phase
from security.audit import log_deviation, log_authorization
from tools.registry import is_permitted
from storage import db

AUTHORIZATION_TIMEOUT_SECONDS = 600


def verify_plan_integrity(session_id: str) -> bool:
    result = db.get_plan(session_id)
    if not result:
        return False
    plan, stored_hash = result
    computed = hashlib.sha256(json.dumps(plan).encode()).hexdigest()
    return computed == stored_hash


def check_action(decision: AgentDecision, phase: Phase,
                 session_id: str, admin_webhook: str | None) -> bool:
    """
    Checks action against registry permissions for the current phase.
    Uses registry as the single source of truth — not the stored plan.
    This prevents stale plan permissions from blocking valid actions.
    """
    tool = decision.action

    # ── Primary check: registry permission ───────────────────
    if is_permitted(tool, phase):
        return True

    # ── Deviation detected ────────────────────────────────────
    risk = _assess_risk(tool, phase)
    deviation_id = log_deviation(
        session_id, phase,
        planned=f"permitted tools for {phase}",
        attempted=tool,
        reasoning=decision.thought,
        risk=risk
    )

    print(f"[MIDDLEWARE] deviation — tool '{tool}' not permitted in phase '{phase}'")

    if admin_webhook:
        _alert_admin(admin_webhook, DeviationAlert(
            session_id=session_id,
            planned_action=f"permitted tools for {phase}",
            attempted_action=tool,
            agent_reasoning=decision.thought,
            risk_level=risk,
            phase=phase
        ))
        return _wait_for_authorization(deviation_id, session_id)

    return False


def _assess_risk(action: str, phase: Phase) -> str:
    high_risk = {"report_write", "memory_write"}
    return "high" if action in high_risk else "medium"


def _alert_admin(webhook_url: str, alert: DeviationAlert) -> None:
    message = (
        f"*AGENT DEVIATION ALERT*\n"
        f"Session: `{alert.session_id}`\n"
        f"Phase: `{alert.phase}`\n"
        f"Attempted: `{alert.attempted_action}`\n"
        f"Risk: `{alert.risk_level}`\n"
        f"Reasoning: {alert.agent_reasoning[:200]}"
    )
    try:
        requests.post(webhook_url, json={"text": message}, timeout=5)
    except Exception:
        pass


def _wait_for_authorization(deviation_id: str, session_id: str) -> bool:
    deadline = time.time() + AUTHORIZATION_TIMEOUT_SECONDS
    while time.time() < deadline:
        for event in db.get_audit_log(session_id):
            if event["event_type"] == "AUTHORIZATION":
                detail = json.loads(event["detail"])
                if detail.get("deviation_id") == deviation_id:
                    return detail.get("approved", False)
        time.sleep(10)

    log_authorization(session_id, deviation_id,
                      approved=False, reason="timeout", authorizer="system")
    return False