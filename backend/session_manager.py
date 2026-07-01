"""Session Manager — orchestrates the DISCOVER experimental session.

Manages the 15-round flow:
  1. Conflict Architect generates scenario → presented via Scheduling Assistant
  2. User interacts (calendar actions + chat) → signals logged
  3. Round completes → Advocate-Challenger-Synthesizer pipeline runs
  4. Value Evidence Ledger updated
  5. At rounds 5, 10, 15: reflection touchpoint triggered

Handles persistence and signal logging for post-hoc decomposition.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import config
from models import (
    BehavioralSignal,
    CalendarEvent,
    ConversationalSignal,
    EventAction,
    Phase,
    Round,
    RoundStatus,
    Session,
)
from agents.conflict_architect import ConflictArchitect
from agents.scheduling_assistant import SchedulingAssistant
from agents.advocate import Advocate
from agents.challenger import Challenger
from agents.synthesizer import Synthesizer

logger = logging.getLogger(__name__)


# ── In-memory session store ──────────────────────────────────────────
_sessions: dict[str, Session] = {}


def get_session(session_id: str) -> Session | None:
    return _sessions.get(session_id)


def get_all_sessions() -> list[Session]:
    return list(_sessions.values())


# ── Default calendar events (simulated existing week) ────────────────

DEFAULT_EVENTS = [
    CalendarEvent(
        id="evt_default_1", title="Team Standup",
        day_index=0, start="09:00", end="09:30",
        tone="purple", category="work",
        description="Daily team sync", source="system", is_movable=False,
    ),
    CalendarEvent(
        id="evt_default_2", title="Deep Work Block",
        day_index=0, start="10:00", end="12:00",
        tone="blue", category="work",
        description="Protected focus time", source="user",
    ),
    CalendarEvent(
        id="evt_default_3", title="Lunch with Sarah",
        day_index=1, start="12:00", end="13:00",
        tone="amber", category="social",
        description="Catch up lunch", source="user",
    ),
    CalendarEvent(
        id="evt_default_4", title="1:1 with Manager",
        day_index=1, start="14:00", end="14:45",
        tone="purple", category="work",
        description="Weekly check-in", source="system", is_movable=False,
    ),
    CalendarEvent(
        id="evt_default_5", title="Gym — Strength Training",
        day_index=2, start="07:00", end="08:00",
        tone="green", category="health",
        description="Morning workout", source="user",
    ),
    CalendarEvent(
        id="evt_default_6", title="Project Review",
        day_index=2, start="14:00", end="15:30",
        tone="purple", category="work",
        description="Q3 project review with stakeholders", source="system",
    ),
    CalendarEvent(
        id="evt_default_7", title="Team Standup",
        day_index=3, start="09:00", end="09:30",
        tone="purple", category="work",
        description="Daily team sync", source="system", is_movable=False,
    ),
    CalendarEvent(
        id="evt_default_8", title="Piano Lesson",
        day_index=3, start="18:00", end="19:00",
        tone="blue", category="personal",
        description="Weekly piano lesson", source="user",
    ),
    CalendarEvent(
        id="evt_default_9", title="Sprint Planning",
        day_index=4, start="10:00", end="11:30",
        tone="purple", category="work",
        description="Bi-weekly sprint planning", source="system",
    ),
    CalendarEvent(
        id="evt_default_10", title="Gym — Cardio",
        day_index=4, start="17:00", end="18:00",
        tone="green", category="health",
        description="Evening run / cycling", source="user",
    ),
]


class SessionManager:
    """Orchestrates a complete DISCOVER experimental session."""

    def __init__(self):
        self.conflict_architect = ConflictArchitect()
        self.scheduling_assistant = SchedulingAssistant()
        self.advocate = Advocate()
        self.challenger = Challenger()
        self.synthesizer = Synthesizer()

    async def create_session(self, participant_id: str = "") -> Session:
        """Create a new experimental session."""
        session = Session(
            participant_id=participant_id,
            calendar_events=list(DEFAULT_EVENTS),  # Copy defaults
        )
        _sessions[session.id] = session
        logger.info(f"Created session {session.id} for participant {participant_id}")
        self._save_session(session)
        return session

    async def start_round(self, session_id: str) -> dict:
        """Start the next round: generate scenario and present it."""
        session = _sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        session.current_round += 1
        round_num = session.current_round

        if round_num > config.TOTAL_ROUNDS:
            return {"status": "session_complete", "round": round_num}

        phase = session.get_phase()
        is_reflection = round_num in config.REFLECTION_ROUNDS

        # Create round object
        round_obj = Round(
            round_num=round_num,
            phase=phase,
            is_reflection_round=is_reflection,
        )
        session.rounds.append(round_obj)

        # Generate scenario via Conflict Architect
        try:
            scenario = await self.conflict_architect.generate_scenario(session, round_num)
            round_obj.scenario = scenario
            round_obj.status = RoundStatus.SCENARIO_PRESENTED

            # Add injected events to calendar (as proposed, not confirmed)
            for event in scenario.injected_events:
                event.is_new = True

            # Present scenario via Scheduling Assistant
            presentation = await self.scheduling_assistant.present_scenario(
                session, scenario.emails, scenario.injected_events,
            )

            # Add assistant message to chat history
            session.chat_history.append({
                "role": "assistant",
                "content": presentation["text"],
            })

            self._save_session(session)

            return {
                "status": "scenario_presented",
                "round": round_num,
                "phase": phase.value,
                "is_reflection_round": is_reflection,
                "message": presentation["text"],
                "emails": presentation.get("emails", []),
                "proposed_events": [e.model_dump() for e in scenario.injected_events],
                "existing_events": [e.model_dump() for e in session.calendar_events],
                "intended_tensions": scenario.intended_tensions,
            }

        except Exception as e:
            logger.error(f"Failed to generate scenario for round {round_num}: {e}")
            round_obj.status = RoundStatus.IN_PROGRESS
            self._save_session(session)
            return {
                "status": "error",
                "round": round_num,
                "error": str(e),
            }

    async def handle_chat(self, session_id: str, user_message: str) -> dict:
        """Handle a chat message from the participant."""
        session = _sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Add user message to chat history
        session.chat_history.append({
            "role": "user",
            "content": user_message,
        })

        # Get response from Scheduling Assistant
        result = await self.scheduling_assistant.respond(user_message, session)

        # Log conversational signals
        round_obj = session.current_round_obj()
        if round_obj:
            round_obj.conversational_signals.extend(result["signals"])

        # Add assistant response to chat history
        session.chat_history.append({
            "role": "assistant",
            "content": result["text"],
        })

        self._save_session(session)

        return {
            "text": result["text"],
            "card": result.get("card"),
            "round": session.current_round,
        }

    async def handle_calendar_action(
        self,
        session_id: str,
        action: str,
        event_id: str,
        details: dict | None = None,
    ) -> dict:
        """Handle a calendar action (accept, decline, reschedule, etc.)."""
        session = _sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        details = details or {}
        event_action = EventAction(action)

        # Find the event
        event = next(
            (e for e in session.calendar_events if e.id == event_id),
            None,
        )
        # Also check proposed events from current scenario
        round_obj = session.current_round_obj()
        proposed_event = None
        if round_obj and round_obj.scenario:
            proposed_event = next(
                (e for e in round_obj.scenario.injected_events if e.id == event_id),
                None,
            )

        target_event = event or proposed_event
        event_title = target_event.title if target_event else event_id

        # Log behavioral signal
        signal = BehavioralSignal(
            round_num=session.current_round,
            action=event_action,
            event_id=event_id,
            event_title=event_title,
            details=details,
        )
        if round_obj:
            round_obj.behavioral_signals.append(signal)
            round_obj.status = RoundStatus.IN_PROGRESS

        # Apply the action
        if event_action == EventAction.ACCEPT and proposed_event:
            # Add proposed event to calendar
            proposed_event.is_new = False
            session.calendar_events.append(proposed_event)

        elif event_action == EventAction.DECLINE and proposed_event:
            # Remove from proposed events (don't add to calendar)
            if round_obj and round_obj.scenario:
                round_obj.scenario.injected_events = [
                    e for e in round_obj.scenario.injected_events
                    if e.id != event_id
                ]

        elif event_action == EventAction.RESCHEDULE and target_event:
            # Update event timing
            if "new_start" in details:
                target_event.start = details["new_start"]
            if "new_end" in details:
                target_event.end = details["new_end"]
            if "new_day_index" in details:
                target_event.day_index = details["new_day_index"]
            # Make sure it's in the calendar
            if proposed_event and proposed_event not in session.calendar_events:
                proposed_event.is_new = False
                session.calendar_events.append(proposed_event)

        elif event_action == EventAction.MODIFY and target_event:
            for key, value in details.items():
                if hasattr(target_event, key):
                    setattr(target_event, key, value)

        self._save_session(session)

        return {
            "status": "action_recorded",
            "action": action,
            "event_id": event_id,
            "event_title": event_title,
            "calendar_events": [e.model_dump() for e in session.calendar_events],
        }

    async def complete_round(self, session_id: str) -> dict:
        """Complete the current round: run debate pipeline, update ledger."""
        session = _sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        round_obj = session.current_round_obj()
        if not round_obj:
            raise ValueError("No active round")

        # Run the Advocate-Challenger-Synthesizer pipeline
        logger.info(f"Running debate pipeline for round {session.current_round}")

        try:
            # 1. Advocate argues FOR
            advocate_output = await self.advocate.argue(session)
            logger.info(f"Advocate completed for round {session.current_round}")

            # 2. Challenger argues AGAINST
            challenger_output = await self.challenger.challenge(session)
            logger.info(f"Challenger completed for round {session.current_round}")

            # 3. Synthesizer resolves the debate
            synthesis = await self.synthesizer.synthesize(
                session, advocate_output, challenger_output,
            )
            logger.info(f"Synthesizer completed for round {session.current_round}")

            # 4. Apply synthesis to the ledger
            debate_record = self.synthesizer.apply_synthesis(
                session, synthesis, advocate_output, challenger_output,
            )
            round_obj.debate_record = debate_record
            session.debate_history.append(debate_record)

        except Exception as e:
            logger.error(f"Debate pipeline failed for round {session.current_round}: {e}")
            # Don't block the session on a debate failure
            synthesis = {"synthesis_narrative": f"Debate pipeline error: {e}"}

        # Handle reflection if this is a reflection round
        reflection = None
        if round_obj.is_reflection_round:
            try:
                reflection = await self.synthesizer.generate_reflection(
                    session, session.current_round,
                )
                round_obj.reflection_prompt = reflection
                round_obj.status = RoundStatus.AWAITING_REFLECTION

                # Add reflection to chat
                session.chat_history.append({
                    "role": "assistant",
                    "content": reflection,
                })
            except Exception as e:
                logger.error(f"Reflection generation failed: {e}")
                round_obj.status = RoundStatus.COMPLETED
        else:
            round_obj.status = RoundStatus.COMPLETED

        self._save_session(session)

        return {
            "status": "round_completed" if not reflection else "reflection_pending",
            "round": session.current_round,
            "synthesis": synthesis.get("synthesis_narrative", ""),
            "value_weights": session.value_ledger.to_weights(),
            "hypotheses": session.value_ledger.to_summary(),
            "reflection": reflection,
        }

    async def submit_reflection(
        self,
        session_id: str,
        reflection_response: str,
    ) -> dict:
        """Submit the participant's response to a reflection prompt."""
        session = _sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        round_obj = session.current_round_obj()
        if not round_obj:
            raise ValueError("No active round")

        round_obj.reflection_response = reflection_response
        round_obj.status = RoundStatus.COMPLETED

        # Log as conversational signal
        round_obj.conversational_signals.append(
            ConversationalSignal(
                round_num=session.current_round,
                role="user",
                content=reflection_response,
                signal_type="reflection",
            )
        )

        # Also add to chat history
        session.chat_history.append({
            "role": "user",
            "content": reflection_response,
        })

        self._save_session(session)

        return {
            "status": "reflection_submitted",
            "round": session.current_round,
        }

    def get_session_state(self, session_id: str) -> dict | None:
        """Get the full current state of a session."""
        session = _sessions.get(session_id)
        if not session:
            return None

        round_obj = session.current_round_obj()

        return {
            "session_id": session.id,
            "participant_id": session.participant_id,
            "current_round": session.current_round,
            "phase": session.get_phase().value if session.current_round > 0 else None,
            "round_status": round_obj.status.value if round_obj else None,
            "is_reflection_round": round_obj.is_reflection_round if round_obj else False,
            "calendar_events": [e.model_dump() for e in session.calendar_events],
            "value_weights": session.value_ledger.to_weights(),
            "hypotheses": session.value_ledger.to_summary(),
            "chat_history": session.chat_history[-20:],
            "total_rounds": config.TOTAL_ROUNDS,
        }

    def export_session_data(self, session_id: str) -> dict | None:
        """Export complete session data for analysis (post-hoc decomposition)."""
        session = _sessions.get(session_id)
        if not session:
            return None

        return {
            "session": session.model_dump(),
            "behavioral_signals": [s.model_dump() for s in session.get_all_behavioral_signals()],
            "conversational_signals": [s.model_dump() for s in session.get_all_conversational_signals()],
            "debate_history": [d.model_dump() for d in session.debate_history],
            "final_ledger": session.value_ledger.model_dump(),
        }

    def _save_session(self, session: Session) -> None:
        """Persist session to disk."""
        path = config.DATA_DIR / f"{session.id}.json"
        try:
            path.write_text(session.model_dump_json(indent=2))
        except Exception as e:
            logger.error(f"Failed to save session {session.id}: {e}")
