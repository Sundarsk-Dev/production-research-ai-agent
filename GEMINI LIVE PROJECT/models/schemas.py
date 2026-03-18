from pydantic import BaseModel, Field
from typing import Literal
from enum import Enum


# ── Enums ─────────────────────────────────────────────────────

class Phase(str, Enum):
    DISCOVERY   = "discovery"
    INVESTIGATION = "investigation"
    CONTRADICTION = "contradiction"
    SYNTHESIS   = "synthesis"


class Depth(str, Enum):
    SHALLOW  = "shallow"
    STANDARD = "standard"
    DEEP     = "deep"


class AuditEventType(str, Enum):
    DEVIATION         = "DEVIATION"
    INJECTION         = "INJECTION"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    AUTHORIZATION     = "AUTHORIZATION"


class TerminationState(str, Enum):
    SUCCESS      = "SUCCESS"
    INCONCLUSIVE = "INCONCLUSIVE"
    HALTED       = "HALTED"


# ── Session input ─────────────────────────────────────────────

class SessionInput(BaseModel):
    topic:       str   = Field(..., min_length=3)
    depth:       Depth = Depth.STANDARD
    session_id:  str | None = None   # None = new session
    admin_webhook: str | None = None  # Slack webhook URL


# ── LLM structured output ─────────────────────────────────────

class AgentDecision(BaseModel):
    thought:    str
    action:     str
    arguments:  dict = Field(default_factory=dict)
    confidence: Literal["low", "medium", "high"]


class PlanPhase(BaseModel):
    phase:           Phase
    goal:            str
    permitted_tools: list[str]
    max_iterations:  int
    success_criteria: str


class Plan(BaseModel):
    session_id: str
    topic:      str
    phases:     list[PlanPhase]


# ── Memory ────────────────────────────────────────────────────

class MemoryChunkInput(BaseModel):
    main_topics:     list[str]
    key_decisions:   list[str]
    open_questions:  list[str]
    one_line_summary: str


# ── Tool results ──────────────────────────────────────────────

class SearchResult(BaseModel):
    title:   str
    url:     str
    snippet: str
    source:  str


class ToolResult(BaseModel):
    tool:    str
    success: bool
    data:    list[SearchResult] | str | dict
    error:   str | None = None


# ── Security ──────────────────────────────────────────────────

class DeviationAlert(BaseModel):
    session_id:      str
    planned_action:  str
    attempted_action: str
    agent_reasoning: str
    risk_level:      Literal["low", "medium", "high"]
    phase:           Phase


class AuthorizationResponse(BaseModel):
    deviation_id: str
    approved:     bool
    reason:       str
    authorizer:   str


# ── Report output ─────────────────────────────────────────────

class Finding(BaseModel):
    claim:      str
    evidence:   str
    source:     str
    confidence: float = Field(..., ge=0.0, le=1.0)


class Contradiction(BaseModel):
    claim_a:  str
    claim_b:  str
    source_a: str
    source_b: str


class ResearchReport(BaseModel):
    session_id:         str
    topic:              str
    executive_summary:  str
    findings:           list[Finding]
    contradictions:     list[Contradiction]
    knowledge_gaps:     list[str]
    sources:            list[str]
    confidence_overall: float = Field(..., ge=0.0, le=1.0)
    termination_state:  TerminationState