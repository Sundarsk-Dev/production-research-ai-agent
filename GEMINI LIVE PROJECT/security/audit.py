from storage import db
from models.schemas import Phase


def log_permission_denied(session_id: str, phase: Phase, tool: str, reason: str) -> None:
    db.insert_audit(session_id, "PERMISSION_DENIED", {
        "tool": tool,
        "phase": phase,
        "reason": reason
    })


def log_deviation(session_id: str, phase: Phase, planned: str,
                  attempted: str, reasoning: str, risk: str) -> str:
    """Logs a plan deviation. Returns the audit event ID for tracking."""
    return db.insert_audit(session_id, "DEVIATION", {
        "planned_action": planned,
        "attempted_action": attempted,
        "agent_reasoning": reasoning,
        "risk_level": risk,
        "phase": phase
    })


def log_authorization(session_id: str, deviation_id: str,
                      approved: bool, reason: str, authorizer: str) -> None:
    db.insert_audit(session_id, "AUTHORIZATION", {
        "deviation_id": deviation_id,
        "approved": approved,
        "reason": reason,
        "authorizer": authorizer
    })


def get_session_audit(session_id: str) -> list[dict]:
    return db.get_audit_log(session_id)