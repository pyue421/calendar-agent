# Bayesian calendar reflection backend

This system models broad, **situated scheduling-value dimensions**. It does not discover complete, objectively true, or stable personal values. Copy `.env.example` to `.env`, add a Gemini API key, and run:

```powershell
python -m uvicorn app.main:app --app-dir backend_v2 --reload --port 8000
```

## Five-dimensional vocabulary

- `wellbeing` — health, rest, boundaries, and personal sustainability.
- `achievement_growth` — progress, mastery, learning, and professional development.
- `relationships_care` — family, friendship, social support, and community care.
- `autonomy_privacy` — control over time, independence, focus, and privacy.
- `responsibility_fairness` — reliability, cooperation, promises, integrity, and fairness.

Scenario features in `app/data/scenario_bank.json` are manually authored on a common `[-1, 1]` scale. Positive values mean an action protects or expresses a dimension in that scenario; negative values mean it compromises it. Zero means no direct feature claim. These features describe trade-offs and do not rank actions morally.

## Deterministic grid model

`GridBayesianValueModel` enumerates every five-dimensional non-negative profile on a simplex grid. With `GRID_STEP=0.025`, the cached grid contains 135,751 profiles. Every profile sums to one.

The prior is a symmetric Dirichlet density evaluated on the discrete grid:

```text
p(w) proportional to product_k w_k^(alpha - 1)
```

`PRIOR_ALPHA=1` is a uniform reference prior over grid points. It is an initial transparent research hypothesis, not an established scientific truth. For alpha other than one, boundary zeros are evaluated at half a grid cell to avoid zero/infinite numerical densities; exports record this approximation.

For action `a` in scenario `s`, the update uses:

```text
P(a | w, s) = exp(beta * w·phi(s,a)) / sum_a' exp(beta * w·phi(s,a'))
posterior(w) proportional to previous_posterior(w) * P(a | w, s)
```

Rationales are parsed separately into structured references. The LLM never assigns scores. For referenced dimensions, the configurable rationale likelihood is:

```text
L(w) = (1-r) + r * mean(referenced grid dimensions) / 0.2
```

where `r = RATIONALE_RELIABILITY`. The unreferenced `(1-r)` component represents uninformative/noisy explanation evidence.

Summaries return posterior mean, relative weight, standard deviation, and a weighted 90% credible interval. **Relative weight means “posterior expected relative scheduling priority under the current model.”** It is not confidence, percentage of evidence, percentage of personality, or objective value importance.

The internal prior is never presented as the participant’s profile. A session begins with `profile_status="uninitialized"` and an empty current profile. Round 1 previews apply hypothetical actions to a cloned prior. The first committed profile appears only after both the first action and the participant’s rationale have updated the model.

## Calendar and controlled scenarios

`DefaultCalendarProvider` materializes `app/data/default_calendar.json` relative to the session’s Monday `week_start`. It contains meetings, focus, wellbeing, relationships, appointments, development, protected and flexible blocks. The 15 controlled scenarios are also scheduled relative to that week. Automatic conflict creation is only a fallback when the required conflict is absent.

Gemini may personalize requester, title, and request wording when `SCENARIO_GENERATOR=gemini`. Scenario identity, module, time/conflict structure, actions, hidden condition, and numerical features remain server-controlled. Deterministic wording is the default and failure fallback.

## Exact evidence and exports

Committed action evidence records exact action/time, event, affected commitments, direct feature links, and posterior before/after/delta. Conversation evidence stores the exact participant quote and explicit/implicit linkage. Assistant messages and previews never enter `value_evidence`. Exports include model settings, feature mappings, decisions, structured rationales, previews, evidence, calendar, and posterior summary.

## Prior sensitivity

Replay an exported session under alpha 0.5, 1, 2, and 5:

```powershell
python backend_v2/scripts/prior_sensitivity.py path\to\session-export.json
```

The report gives posterior means, maximum absolute difference, and L1 distance relative to alpha 1. Future work may learn a hierarchical logistic-normal prior after sufficient pilot-participant data exist.

## Configuration

See `.env.example`. The research parameters are `GRID_STEP`, `PRIOR_ALPHA`, `BETA`, and `RATIONALE_RELIABILITY`; evidence-link filtering uses `EVIDENCE_DELTA_THRESHOLD`.

## Verification and performance

```powershell
cd backend_v2
python -m pytest -q
cd ..\frontend
npm.cmd run build
npm.cmd run lint
```

On the development machine used for this revision, constructing the cached 0.025 grid took approximately 0.26 seconds; one cloned action preview plus complete five-value posterior summary took approximately 0.11 seconds. These are local reference measurements, not deployment guarantees.

## Changed-file map

- `app/services/bayesian_value_model.py` — deterministic simplex grid, prior, likelihood updates, summaries.
- `app/data/scenario_bank.json` and `app/services/calendar_feature_service.py` — manual five-value action features and time-sensitive rescheduling.
- `app/data/default_calendar.json` and `app/services/calendar_service.py` — session-relative default calendar provider.
- `app/services/session_service.py` — uninitialized/initialized visibility, rounds, exact evidence, export.
- `app/llm/rationale_parser.py` and `app/models.py` — five-value structured rationale vocabulary.
- `scripts/prior_sensitivity.py` — offline alpha replay analysis.
- `frontend/src/services/SessionContext.jsx`, `components/home/ChatbotPanel.jsx`, and `components/home/values.jsx` — immediate Round 1, hidden initial profile, anchored previews, and exact evidence UI.
- `tests/test_complete_flow.py` — grid, first-use, preview, calendar, evidence, 15-round, and performance regression coverage.
