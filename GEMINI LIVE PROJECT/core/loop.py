import os
import json
import re
from dotenv import load_dotenv
load_dotenv()

import google.generativeai as genai
from models.schemas import AgentDecision, Phase, PlanPhase, TerminationState, ToolResult
from core.context_builder import build_prompt
from tools.dispatcher import dispatch
from security.middleware import check_action, verify_plan_integrity
from memory.short_term import ShortTermMemory
from memory.long_term import compress_and_store
from memory.retriever import search_memory
from storage import db

genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
_model = genai.GenerativeModel("gemini-2.5-flash-lite")


class PhaseLoop:
    def __init__(self, session_id: str, topic: str, phase_config: PlanPhase,
                 short_term: ShortTermMemory, admin_webhook: str | None):
        self.session_id = session_id
        self.topic = topic
        self.phase = phase_config.phase
        self.goal = phase_config.goal
        self.max_iter = phase_config.max_iterations
        self.short_term = short_term
        self.admin_webhook = admin_webhook
        self.last_result: dict | None = None
        self.iteration = 0
        self._recent_actions: list[tuple] = []

    def run(self) -> TerminationState:
        if not verify_plan_integrity(self.session_id):
            db.insert_audit(self.session_id, "DEVIATION", {
                "reason": "plan hash mismatch", "phase": self.phase
            })
            return TerminationState.HALTED

        while self.iteration < self.max_iter:
            self.iteration += 1
            print(f"\n[ITER {self.iteration}/{self.max_iter}] phase={self.phase}")

            memory = search_memory(self.topic, self.session_id)

            system, user = build_prompt(
                phase=self.phase, goal=self.goal, topic=self.topic,
                window=self.short_term.get_window(),
                memory=memory, last_result=self.last_result
            )

            full_prompt = f"{system}\n\n{user}"

            try:
                response = _model.generate_content(full_prompt)
                raw = response.text.strip()
                print(f"[RAW] {raw[:300]}")
            except Exception as e:
                print(f"[LLM ERROR] {e}")
                db.insert_event(self.session_id, self.phase,
                                "LLM_ERROR", {"error": str(e)})
                continue

            decision = self._parse_decision(raw)
            print(f"[DECISION] {decision}")

            if not decision:
                db.insert_event(self.session_id, self.phase,
                                "PARSE_ERROR", {"raw": raw[:300]})
                continue

            self.short_term.add("assistant", decision.thought, self.phase)

            if self.short_term.needs_compression():
                exchanges, start, end = self.short_term.flush_for_compression()
                compress_and_store(exchanges, self.session_id, start, end)

            approved = check_action(
                decision, self.phase, self.session_id, self.admin_webhook
            )
            if not approved:
                print(f"[HALTED] action not approved: {decision.action}")
                return TerminationState.HALTED

            result: ToolResult = dispatch(decision, self.phase, self.session_id)
            print(f"[RESULT] success={result.success} error={result.error}")

            self.last_result = result.model_dump()
            self.short_term.add("tool", str(result.data)[:300], self.phase)

            action_key = (decision.action, json.dumps(decision.arguments, sort_keys=True))
            self._recent_actions.append(action_key)
            if len(self._recent_actions) > 3:
                self._recent_actions.pop(0)

            if self._is_looping():
                print(f"[LOOP DETECTED] same action 3x: {decision.action}")
                db.insert_event(self.session_id, self.phase,
                                "LOOP_DETECTED", {"action": decision.action})
                break

            if decision.action == "report_write" and self.phase == Phase.SYNTHESIS:
                print("[DONE] report_write in synthesis")
                return TerminationState.SUCCESS

            if result.success and decision.confidence == "high":
                if self._phase_goal_met():
                    print(f"[PHASE COMPLETE] goal met at iter {self.iteration}")
                    return TerminationState.SUCCESS

        print(f"[INCONCLUSIVE] max iterations reached: {self.max_iter}")
        return TerminationState.INCONCLUSIVE

    def _parse_decision(self, raw: str) -> AgentDecision | None:
        """
        Robust JSON extraction. Handles:
        - Clean JSON
        - JSON wrapped in ```json ... ```
        - JSON preceded or followed by extra prose text
        """
        try:
            # Strategy 1 — find first { and last } and extract
            first = raw.find("{")
            last = raw.rfind("}")
            if first != -1 and last != -1 and last > first:
                candidate = raw[first:last + 1]
                return AgentDecision(**json.loads(candidate))
        except Exception:
            pass

        try:
            # Strategy 2 — extract from code fence
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
            if match:
                return AgentDecision(**json.loads(match.group(1)))
        except Exception:
            pass

        print(f"[PARSE FAIL] could not extract JSON | raw: {raw[:200]}")
        return None

    def _is_looping(self) -> bool:
        if len(self._recent_actions) < 3:
            return False
        return (self._recent_actions[0] ==
                self._recent_actions[1] ==
                self._recent_actions[2])

    def _phase_goal_met(self) -> bool:
        events = db.get_events(self.session_id, phase=self.phase)
        successes = [e for e in events if e["event_type"] == "TOOL_SUCCESS"]
        thresholds = {
            Phase.DISCOVERY:      5,
            Phase.INVESTIGATION:  8,
            Phase.CONTRADICTION:  3,
            Phase.SYNTHESIS:      1,
        }
        required = thresholds.get(self.phase, 3)
        print(f"[GOAL CHECK] successes={len(successes)} required={required}")
        return len(successes) >= required