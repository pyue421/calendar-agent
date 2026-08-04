# Conversational prior elicitation

## Purpose and claim boundary

This onboarding phase collects domain-specific scheduling evidence to form a weak, conversation-informed starting hypothesis for the calendar model. It is not a validated psychological survey, personality measure, diagnosis, or method for discovering “true values.” Participants are not shown prior probabilities, evidence scores, or inferred value mappings.

The LLM does not directly assign Bayesian probabilities. It may provide a short neutral acknowledgement, extract quote-grounded evidence into the fixed taxonomy, and independently review those mappings. Deterministic, versioned backend code constructs the prior.

## Versioned protocol

Protocol `conversational_prior_v1`, version `1.0.0`, is stored in `backend_v2/app/data/onboarding_protocol.json`. Its six fixed question families are `typical_week`, `competing_commitments`, `protected_commitments`, `unexpected_requests`, `successful_week`, and `rescheduling_concerns`. Questions concern concrete scheduling experiences without naming the five model dimensions. Participants may skip any question or choose a neutral model.

The default protocol permits eight participant turns, no more than two total follow-ups, and no more than one follow-up per core question. Follow-ups are selected only from the versioned approved list. Five answered core questions are required to attempt an informed prior.

## Role separation and evidence

The interviewer cannot see posterior weights and cannot extract evidence. The extractor sees participant turns, question IDs, exact text, and taxonomy definitions; it cannot output probabilities. The reviewer independently accepts, marks ambiguous, or rejects each candidate without posterior access. Every evidence record has a stable turn and question ID, exact quote, one value ID, relation, directness, strength, alternative explanations, review decision, provider/model provenance, and timestamp. Assistant text cannot be evidence. Quotes absent from participant turns are rejected.

Transcripts are sensitive research data. Ordinary completion responses omit transcript, evidence mappings, scores, and distributions. The researcher export retains them with protocol, prompt, provider, model, parameter, and timestamp provenance.

## Deterministic prior algorithm

Version `conversation_prior_builder_v1` starts with zero scores for the five stable IDs. Each reviewed item contributes:

`relation_sign × directness_weight × strength_weight × review_weight`

Supports/challenges map to `+1/−1`; explicit/implicit/ambiguous to `1/0.6/0.25`; weak/moderate/strong to `0.5/1/1.5`; accepted/ambiguous/rejected to `1/0.35/0`. Scores are summed, clipped, and centered. The builder evaluates `evidence_scale × dot(grid_point, centered_scores)`, combines that likelihood with the symmetric base prior, and robustly mixes the evidence posterior with the neutral base distribution.

Provisional pilot defaults are evidence scale `0.75`, mixture weight `0.35`, score clip `3.0`, and minimum accepted evidence `2`. These parameters are not validated and must be calibrated and frozen before the main study. The robust mixture is deliberately weak and remains overridable by calendar decisions and rationales.

## Fallback and visibility

Insufficient grounded evidence, no extracted evidence, participant choice, or disabled personalization retains the neutral symmetric prior and records the fallback reason. Transient LLM failures do not silently trigger fallback: the neutral posterior remains unchanged and the participant may retry or explicitly choose neutral.

After a conversation-informed prior is successfully applied, `profile_status` becomes `initialized` and the five bubbles show that weak starting estimate during Round 1. Reviewed onboarding evidence is attached to the corresponding bubbles. A neutral fallback contains no conversational evidence, so its symmetric mathematical prior remains hidden until the first decision-plus-rationale initialization point. Round 1 previews retain their existing behavior.

## Reproducibility and validity risks

Exports record exact transcripts, structured outputs, review decisions, deterministic contributions, base/evidence/mixed distributions, prompts, models, protocol version, algorithm version, parameters, and whether prior information was shown. Known risks include language-model mapping error, keyword/context sensitivity, limited behavioral generalization from a short interview, differential response detail, and anchoring if visibility protections regress.

## TODO before the main study

- Pilot and calibrate prior strength and evidence thresholds.
- Freeze protocol wording, prompts, provider/model versions, and parameters.
- Complete construct-validation and inter-rater review work.
- Specify privacy, retention, access-control, and deletion procedures.
- Add appropriate citations without inventing references.
- Align exports and analyses with preregistration.
