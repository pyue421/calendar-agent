# Bayesian calendar reflection backend

Copy `.env.example` to `.env`, add a Gemini API key from Google AI Studio, then run with `uvicorn app.main:app --app-dir backend_v2 --reload`.

This prototype models **situated scheduling priorities**, not objectively true values. It uses a fixed 12-value vocabulary and deterministic scenario/action features. The initial research hypotheses live in `app/config.py`: 800 symmetric Dirichlet-like prior particles, softmax beta 5.0, rationale reliability 0.65, and resampling below 45% effective sample size. These are configurable pilot parameters, not validated psychological constants.

Action features are visible in `scenario_service.py`; candidate-time adjustments are in `calendar_feature_service.py`. Reschedule features respond to delay, conflicts, protected blocks, and work-hour boundaries. Only rationale parsing is an LLM boundary. The default Gemini adapter uses structured JSON output and validates it again as `RationaleObservation`; it receives only the participant rationale and factual committed-action context, and never assigns bubble scores. `RATIONALE_PARSER=deterministic` is an explicit offline/test fallback.

## Gemini configuration

```dotenv
GEMINI_API_KEY=your-key-from-google-ai-studio
GEMINI_MODEL=gemini-2.5-flash-lite
GEMINI_TIMEOUT_SECONDS=30
RATIONALE_PARSER=gemini
SCENARIO_GENERATOR=deterministic
```

The API key is backend-only. Never use a `VITE_` prefix or place it in the frontend. Gemini 2.5 Flash-Lite is the default because it supports structured output and is available on Gemini's free tier, subject to Google's current quotas and data-use terms.

Set `SCENARIO_GENERATOR=gemini` to let Gemini personalize requester/title/request wording. The server still fixes scenario identity, module, schedule/conflict structure, feasible actions, and action features. Invalid or unavailable generation falls back to the controlled deterministic wording.

Persistence is intentionally in-memory for this first vertical slice. Export contains previews, decisions, rationales, evidence, posterior summary, and model configuration. Hidden experimental metadata stays server-side.
