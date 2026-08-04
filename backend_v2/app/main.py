from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .models import CalendarActionRequest, ChatRequest, DecisionRequest, InitialProfileViewedRequest, OnboardingMessageRequest, OnboardingSkipRequest, PreviewRequest, ProfileInteractionRequest, RationaleRequest, SessionCreate
from .llm.rationale_parser import RationaleParserConfigurationError, RationaleParserError, RationaleParserUnavailableError
from .config import LLM_CONFIG, RESEARCH_CONFIGURATION_VALID, STUDY_MODE
from .services.session_service import sessions
from .services.calendar_conflict_service import CalendarConflictError

app = FastAPI(title="Calendar Reflection API", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])


def call(fn, *args):
    try:
        return fn(*args)
    except KeyError:
        raise HTTPException(404, "Session not found")
    except CalendarConflictError as exc:
        raise HTTPException(409, exc.detail())
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except RationaleParserConfigurationError as exc:
        raise HTTPException(503, str(exc))
    except RationaleParserUnavailableError as exc:
        raise HTTPException(503, {"code": "llm_temporarily_unavailable", "message": str(exc), "retryable": True})
    except RationaleParserError as exc:
        raise HTTPException(502, str(exc))


@app.get("/health")
def health():
    return {
        "ok": True,
        "study_mode": STUDY_MODE,
        "research_configuration_valid": RESEARCH_CONFIGURATION_VALID,
        "rationale_parser": LLM_CONFIG.parser,
        "rationale_model": LLM_CONFIG.model if LLM_CONFIG.parser == "gemini" else None,
        "llm_configured": bool(LLM_CONFIG.api_key) if LLM_CONFIG.parser == "gemini" else True,
        "onboarding_roles": {"interviewer": LLM_CONFIG.onboarding_interviewer,
                             "extractor": LLM_CONFIG.onboarding_extractor,
                             "reviewer": LLM_CONFIG.onboarding_reviewer},
    }


@app.post("/api/sessions", status_code=201)
def create(body: SessionCreate): return sessions.create(body.participant_id)


@app.get("/api/sessions/{sid}/state")
def state(sid: str): return call(sessions.state, sid)


@app.post("/api/sessions/{sid}/onboarding/start")
def onboarding_start(sid: str): return call(sessions.start_onboarding, sid)


@app.post("/api/sessions/{sid}/onboarding/messages")
def onboarding_message(sid: str, body: OnboardingMessageRequest): return call(sessions.onboarding_message, sid, body.message)


@app.post("/api/sessions/{sid}/onboarding/skip-question")
def onboarding_skip(sid: str, body: OnboardingSkipRequest): return call(sessions.skip_onboarding_question, sid, body.question_id)


@app.post("/api/sessions/{sid}/onboarding/complete")
def onboarding_complete(sid: str): return call(sessions.complete_onboarding, sid)


@app.post("/api/sessions/{sid}/onboarding/use-neutral-prior")
def onboarding_neutral(sid: str): return call(sessions.use_neutral_prior, sid)


@app.post("/api/sessions/{sid}/onboarding/initial-profile-viewed")
def onboarding_profile_viewed(sid: str, body: InitialProfileViewedRequest):
    return call(sessions.initial_profile_viewed, sid, body.profile_version, body.displayed_at, body.source)


@app.post("/api/sessions/{sid}/profile-interactions")
def profile_interaction(sid: str, body: ProfileInteractionRequest):
    return call(sessions.profile_interaction, sid, body.event_type, body.value_id, body.profile_version,
                body.profile_stage, body.round, body.timestamp, body.source_phase)


@app.post("/api/sessions/{sid}/events/next")
def next_event(sid: str): return call(sessions.next_event, sid)


@app.post("/api/sessions/{sid}/previews")
def preview(sid: str, body: PreviewRequest):
    return call(sessions.preview, sid, body.event_id, body.action, body.candidate_schedule.model_dump() if body.candidate_schedule else None, body.display_state)


@app.post("/api/sessions/{sid}/decisions")
def decision(sid: str, body: DecisionRequest):
    return call(sessions.decide, sid, body.event_id, body.action, body.candidate_schedule.model_dump() if body.candidate_schedule else None)


@app.post("/api/sessions/{sid}/calendar-actions")
def calendar_action(sid: str, body: CalendarActionRequest):
    return call(sessions.calendar_action, sid, body.action_type, body.event_id,
                body.new_schedule.model_dump() if body.new_schedule else None, body.changes, body.source)


@app.post("/api/sessions/{sid}/rationales")
def rationale(sid: str, body: RationaleRequest): return call(sessions.rationale, sid, body.decision_id, body.rationale)


@app.post("/api/sessions/{sid}/chat")
def chat(sid: str, body: ChatRequest): return call(sessions.chat, sid, body.message)


@app.get("/api/sessions/{sid}/export")
def export(sid: str): return call(sessions.export, sid)
