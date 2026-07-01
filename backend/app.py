"""DISCOVER Framework — FastAPI Backend.

API endpoints for the DISCOVER value elicitation study.
Connects the React frontend to the multi-agent pipeline:
  Conflict Architect → Scheduling Assistant → [user interaction]
  → Advocate → Challenger → Synthesizer → Value Evidence Ledger

Endpoints:
  POST /api/session/create         — Start a new study session
  POST /api/session/{id}/start-round — Begin the next round
  POST /api/session/{id}/chat      — Send chat message to Scheduling Assistant
  POST /api/session/{id}/calendar-action — Record a calendar action
  POST /api/session/{id}/complete-round  — Finish round, run debate pipeline
  POST /api/session/{id}/reflect   — Submit reflection response
  GET  /api/session/{id}/state     — Get full session state
  GET  /api/session/{id}/export    — Export session data for analysis
  GET  /health                     — Health check
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import config
from session_manager import SessionManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Lifespan ─────────────────────────────────────────────────────────

manager = SessionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.load_env()
    if not config.ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not set — LLM calls will fail")
    logger.info("DISCOVER backend starting")
    yield
    logger.info("DISCOVER backend shutting down")


# ── App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="DISCOVER Framework",
    description="Value elicitation through scheduling task behavior",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response Models ────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    participant_id: str = ""


class ChatRequest(BaseModel):
    message: str


class CalendarActionRequest(BaseModel):
    action: str          # accept | decline | reschedule | modify | prioritize
    event_id: str
    details: dict | None = None


class ReflectionRequest(BaseModel):
    response: str


# ── Endpoints ────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"ok": True, "service": "discover"}


@app.post("/api/session/create")
async def create_session(req: CreateSessionRequest):
    """Create a new experimental session."""
    try:
        session = await manager.create_session(req.participant_id)
        return {
            "session_id": session.id,
            "participant_id": session.participant_id,
            "calendar_events": [e.model_dump() for e in session.calendar_events],
            "total_rounds": config.TOTAL_ROUNDS,
        }
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/session/{session_id}/start-round")
async def start_round(session_id: str):
    """Start the next round — generates scenario via Conflict Architect."""
    try:
        result = await manager.start_round(session_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start round: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/session/{session_id}/chat")
async def chat(session_id: str, req: ChatRequest):
    """Send a message to the Scheduling Assistant."""
    try:
        result = await manager.handle_chat(session_id, req.message)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Chat failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/session/{session_id}/calendar-action")
async def calendar_action(session_id: str, req: CalendarActionRequest):
    """Record a calendar action (accept, decline, reschedule, etc.)."""
    try:
        result = await manager.handle_calendar_action(
            session_id, req.action, req.event_id, req.details,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404 if "not found" in str(e) else 400, detail=str(e))
    except Exception as e:
        logger.error(f"Calendar action failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/session/{session_id}/complete-round")
async def complete_round(session_id: str):
    """Complete the current round — runs the Advocate-Challenger-Synthesizer pipeline."""
    try:
        result = await manager.complete_round(session_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Complete round failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/session/{session_id}/reflect")
async def submit_reflection(session_id: str, req: ReflectionRequest):
    """Submit a participant's reflection response."""
    try:
        result = await manager.submit_reflection(session_id, req.response)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Reflection submission failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/session/{session_id}/state")
async def get_session_state(session_id: str):
    """Get the full current state of a session."""
    state = manager.get_session_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    return state


@app.get("/api/session/{session_id}/export")
async def export_session(session_id: str):
    """Export complete session data for analysis."""
    data = manager.export_session_data(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found")
    return data


# ── Run ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    config.load_env()
    uvicorn.run(
        "app:app",
        host=config.BACKEND_HOST,
        port=config.BACKEND_PORT,
        reload=True,
    )
