import uuid
from models.schemas import Plan, Phase, SessionInput, TerminationState
from core.planner import generate_plan, get_phase_config, next_phase
from core.loop import PhaseLoop
from memory.short_term import ShortTermMemory
from storage import db


class Orchestrator:
    """
    Manages the full session lifecycle.
    Owns phase transitions, short-term memory, and termination.
    """

    def __init__(self, session_input: SessionInput):
        self.input = session_input
        self.session_id = session_input.session_id or str(uuid.uuid4())
        self.short_term = ShortTermMemory()
        self.plan: Plan | None = None
        self.current_phase = Phase.DISCOVERY
        self.termination: TerminationState | None = None

    def run(self) -> dict:
        """
        Entry point. Runs all phases in order.
        Returns session summary dict.
        """
        db.init_db()

        db.insert_event(self.session_id, "init", "SESSION_START", {
            "topic": self.input.topic,
            "depth": self.input.depth.value
        })

        # Generate and store plan
        self.plan = generate_plan(
            session_id=self.session_id,
            topic=self.input.topic,
            depth=self.input.depth
        )

        # Run phases in sequence
        phase = Phase.DISCOVERY
        while phase is not None:
            print(f"\n── Phase: {phase.value.upper()} ──")

            phase_config = get_phase_config(self.plan, phase)
            if not phase_config:
                break

            loop = PhaseLoop(
                session_id=self.session_id,
                topic=self.input.topic,
                phase_config=phase_config,
                short_term=self.short_term,
                admin_webhook=self.input.admin_webhook
            )

            state = loop.run()
            print(f"Phase result: {state.value}")

            db.insert_event(self.session_id, phase.value, "PHASE_COMPLETE", {
                "state": state.value,
                "iterations": loop.iteration
            })

            # Hard stop on HALTED — preserve state for resumption
            if state == TerminationState.HALTED:
                self.termination = TerminationState.HALTED
                break

            phase = next_phase(phase)
            if phase is None:
                self.termination = TerminationState.SUCCESS

        # Default to INCONCLUSIVE if we exit without explicit SUCCESS
        if self.termination is None:
            self.termination = TerminationState.INCONCLUSIVE

        db.insert_event(self.session_id, "final", "SESSION_END", {
            "termination": self.termination.value
        })

        return self._session_summary()

    def _session_summary(self) -> dict:
        events = db.get_events(self.session_id)
        audit = db.get_audit_log(self.session_id)
        chain_ok = db.verify_event_chain(self.session_id)

        return {
            "session_id": self.session_id,
            "topic": self.input.topic,
            "termination": self.termination.value,
            "total_events": len(events),
            "audit_events": len(audit),
            "chain_integrity": chain_ok,
            "phases_run": list({e["phase"] for e in events})
        }