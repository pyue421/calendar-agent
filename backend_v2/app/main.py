from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .models import ChatRequest, DecisionRequest, PreviewRequest, RationaleRequest, SessionCreate
from .llm.rationale_parser import RationaleParserConfigurationError, RationaleParserError
from .config import LLM_CONFIG
from .services.session_service import sessions

app = FastAPI(title="Calendar Reflection API", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])


def call(fn, *args):
    try:
        return fn(*args)
    except KeyError:
        raise HTTPException(404, "Session not found")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except RationaleParserConfigurationError as exc:
        raise HTTPException(503, str(exc))
    except RationaleParserError as exc:
        raise HTTPException(502, str(exc))


@app.get("/health")
def health():
    return {
        "ok": True,
        "rationale_parser": LLM_CONFIG.parser,
        "rationale_model": LLM_CONFIG.model if LLM_CONFIG.parser == "gemini" else None,
        "llm_configured": bool(LLM_CONFIG.api_key) if LLM_CONFIG.parser == "gemini" else True,
    }


@app.post("/api/sessions", status_code=201)
def create(body: SessionCreate): return sessions.create(body.participant_id)


@app.get("/api/sessions/{sid}/state")
def state(sid: str): return call(sessions.state, sid)


@app.post("/api/sessions/{sid}/events/next")
def next_event(sid: str): return call(sessions.next_event, sid)


@app.post("/api/sessions/{sid}/previews")
def preview(sid: str, body: PreviewRequest):
    return call(sessions.preview, sid, body.event_id, body.action, body.candidate_schedule.model_dump() if body.candidate_schedule else None, body.display_state)


@app.post("/api/sessions/{sid}/decisions")
def decision(sid: str, body: DecisionRequest):
    return call(sessions.decide, sid, body.event_id, body.action, body.candidate_schedule.model_dump() if body.candidate_schedule else None)


@app.post("/api/sessions/{sid}/rationales")
def rationale(sid: str, body: RationaleRequest): return call(sessions.rationale, sid, body.decision_id, body.rationale)


@app.post("/api/sessions/{sid}/chat")
def chat(sid: str, body: ChatRequest): return call(sessions.chat, sid, body.message)


@app.get("/api/sessions/{sid}/export")
def export(sid: str): return call(sessions.export, sid)
