/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react"
import {normalizeValueProfile} from "./valueProfile"

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000"
const SessionContext = createContext(null)
export function useSession() { return useContext(SessionContext) }

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {...options, headers: {"Content-Type": "application/json", ...(options.headers || {})}})
  const data = await response.json()
  if (!response.ok) {
    const detail = data.detail || {message: "Request failed"}
    const error = new Error(typeof detail === "string" ? detail : detail.message)
    error.status = response.status; error.detail = detail
    throw error
  }
  return data
}

export default function SessionProvider({children}) {
  const [sessionId, setSessionId] = useState(null)
  const [state, setState] = useState({current_round: 0, total_rounds: 15, profile_status: "uninitialized", round_status: "loading"})
  const [event, setEvent] = useState(null)
  const [currentProfile, setCurrentProfile] = useState([])
  const [preview, setPreview] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [activePreviewTarget, setActivePreviewTarget] = useState(null)
  const [latestActionTransition, setLatestActionTransition] = useState(null)
  const [latestRationaleTransition, setLatestRationaleTransition] = useState(null)
  const [latestRoundTransition, setLatestRoundTransition] = useState(null)
  const previewRequest = useRef(0)
  const [candidateEvent, setCandidateEvent] = useState(null)
  const [calendarEvents, setCalendarEvents] = useState([])
  const [calendarActionLoading, setCalendarActionLoading] = useState(false)
  const [calendarActionError, setCalendarActionError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [onboardingLoading, setOnboardingLoading] = useState(false)
  const [onboardingError, setOnboardingError] = useState(null)
  const [onboardingAssistantMessage, setOnboardingAssistantMessage] = useState(null)
  const completionInFlight = useRef(null)
  const roundStartInFlight = useRef(null)
  const applyState = useCallback(data => {
    setState(previous => ({...previous, ...data,
      ...(data.progress ? {onboarding_progress: data.progress} : {}),
      ...(Object.hasOwn(data, "question_id") ? {onboarding_question_id: data.question_id} : {})}))
    if (data.current_profile) setCurrentProfile(data.current_profile)
    if (data.calendar) setCalendarEvents(data.calendar)
    if (data.active_event) setEvent(data.active_event)
    else if (Object.hasOwn(data, "active_event") || ["complete", "session_complete"].includes(data.round_status)) setEvent(null)
  }, [])
  const initialize = useCallback(async () => {
    setLoading(true)
    try {
      let session
      const storedId = localStorage.getItem("calendar_session_id")
      if (storedId) {
        try { session = await request(`/api/sessions/${storedId}/state`) } catch { localStorage.removeItem("calendar_session_id") }
      }
      if (!session) session = await request("/api/sessions", {method: "POST", body: JSON.stringify({participant_id: `participant_${Date.now()}`})})
      setSessionId(session.session_id); localStorage.setItem("calendar_session_id", session.session_id); applyState(session)
      if (session.onboarding_status === "not_started") {
        const started = await request(`/api/sessions/${session.session_id}/onboarding/start`, {method: "POST"})
        applyState(started); setOnboardingAssistantMessage(started.assistant_message)
      } else if (session.onboarding_status === "active") setOnboardingAssistantMessage(session.onboarding_assistant_message)
    } finally { setLoading(false) }
  }, [applyState])
  useEffect(() => { initialize().catch(console.error) }, [initialize])

  async function startRound() {
    if (!state.can_start_round && !state.canStartRound) throw new Error("Complete onboarding before starting Round 1.")
    previewRequest.current += 1; setPreview(null); setPreviewLoading(false); setActivePreviewTarget(null); setCandidateEvent(null)
    const data = await request(`/api/sessions/${sessionId}/events/next`, {method: "POST"}); applyState(data)
    if (data.event) setEvent(data.event); return data
  }
  async function loadPreview(action, candidateSchedule, displayState = "hover") {
    const requestNumber = ++previewRequest.current; setPreviewLoading(true)
    try {
      const data = await request(`/api/sessions/${sessionId}/previews`, {method: "POST", body: JSON.stringify({event_id: event.scenario_id, action, candidate_schedule: candidateSchedule, display_state: displayState})})
      if (requestNumber !== previewRequest.current) return data
      const committed = normalizeValueProfile(currentProfile)
      const normalized = normalizeValueProfile(data.preview_profile, committed?.scale || null)
      if (data.feasible === false) { setPreview(data); return data }
      if (!normalized) {
        console.warn("Ignoring malformed counterfactual value profile", {action, candidateSchedule})
        return data
      }
      setPreview({...data, preview_profile: normalized.profile, request_id: requestNumber, candidate_schedule: candidateSchedule})
      return data
    } finally {
      if (requestNumber === previewRequest.current) setPreviewLoading(false)
    }
  }
  async function commitDecision(action, candidateSchedule) {
    const data = await request(`/api/sessions/${sessionId}/decisions`, {method: "POST", body: JSON.stringify({event_id: event.scenario_id, action, candidate_schedule: candidateSchedule})})
    previewRequest.current += 1; applyState(data); setPreview(null); setPreviewLoading(false); setActivePreviewTarget(null)
    setLatestActionTransition(data.action_transition || null); setLatestRationaleTransition(null); setLatestRoundTransition(null)
    setCandidateEvent(null); return data
  }
  async function sendChat(message) {
    const data = await request(`/api/sessions/${sessionId}/chat`, {method: "POST", body: JSON.stringify({message})})
    applyState(data)
    if (data.rationale_recorded) {
      setEvent(null); setLatestRationaleTransition(data.rationale_transition || null)
      setLatestRoundTransition(data.round_transition || null); setLatestActionTransition(null)
    }
    return data
  }
  async function sendCalendarAction(action) {
    setCalendarActionLoading(true); setCalendarActionError(null)
    try {
      const data = await request(`/api/sessions/${sessionId}/calendar-actions`, {method: "POST", body: JSON.stringify(action)})
      previewRequest.current += 1; setPreview(null); setPreviewLoading(false); applyState(data)
      return data
    } catch (error) { setCalendarActionError(error.detail || error.message); throw error }
    finally { setCalendarActionLoading(false) }
  }
  async function onboardingCall(path, body) {
    setOnboardingLoading(true); setOnboardingError(null)
    try {
      const data = await request(`/api/sessions/${sessionId}/onboarding/${path}`, {method: "POST", ...(body ? {body: JSON.stringify(body)} : {})})
      applyState(data)
      setOnboardingAssistantMessage(data.can_complete && !data.question_id ? null : data.assistant_message || null)
      return data
    } catch (error) { setOnboardingError(error.detail || {message: error.message, retryable: true}); throw error }
    finally { setOnboardingLoading(false) }
  }
  async function startFirstRound(completed) {
    if (roundStartInFlight.current) return roundStartInFlight.current
    roundStartInFlight.current = (async () => {
      await new Promise(resolve => (window.requestAnimationFrame || window.setTimeout)(resolve))
      const round = await request(`/api/sessions/${sessionId}/events/next`, {method: "POST"})
      applyState(round); if (round.event) setEvent(round.event)
      return {...completed, started_round: round}
    })()
    try { return await roundStartInFlight.current } finally { roundStartInFlight.current = null }
  }
  async function maybeCompleteOnboarding(response) {
    if (response?.question_id !== null || !response?.can_complete || response?.onboarding_status !== "active") return response
    if (completionInFlight.current) return completionInFlight.current
    completionInFlight.current = (async () => {
      const completed = await request(`/api/sessions/${sessionId}/onboarding/complete`, {method: "POST"})
      applyState(completed); setOnboardingAssistantMessage(null)
      return startFirstRound(completed)
    })()
    try { return await completionInFlight.current }
    catch (error) { setOnboardingError(error.detail || {message: error.message, retryable: true}); throw error }
    finally { completionInFlight.current = null }
  }
  async function useNeutralAndStartRound() {
    if (completionInFlight.current) return completionInFlight.current
    setOnboardingLoading(true); setOnboardingError(null)
    completionInFlight.current = (async () => {
      const completed = await request(`/api/sessions/${sessionId}/onboarding/use-neutral-prior`, {method: "POST"})
      applyState(completed); setOnboardingAssistantMessage(null)
      return startFirstRound(completed)
    })()
    try { return await completionInFlight.current }
    catch (error) { setOnboardingError(error.detail || {message: error.message, retryable: true}); throw error }
    finally { completionInFlight.current = null; setOnboardingLoading(false) }
  }
  const startOnboarding = () => onboardingCall("start")
  const sendOnboardingMessage = async message => {
    const data = await onboardingCall("messages", {message})
    return maybeCompleteOnboarding(data)
  }
  const skipOnboardingQuestion = async questionId => maybeCompleteOnboarding(
    await onboardingCall("skip-question", {question_id: questionId}))
  const useNeutralPrior = () => useNeutralAndStartRound()
  const logInitialProfileViewed = profileVersion => request(`/api/sessions/${sessionId}/onboarding/initial-profile-viewed`,
    {method: "POST", body: JSON.stringify({profile_version: profileVersion, displayed_at: new Date().toISOString(), source: "values_panel"})})
  const logProfileInteraction = interaction => request(`/api/sessions/${sessionId}/profile-interactions`,
    {method: "POST", body: JSON.stringify({...interaction, timestamp: new Date().toISOString()})})
  const committedValues = normalizeValueProfile(currentProfile)?.profile || []
  const previewValueWeights = preview?.feasible !== false ? preview?.preview_profile || null : null
  const activePreviewTransition = preview?.action === activePreviewTarget ? preview.preview_transition || null : null
  function invalidatePreviewRequests() { previewRequest.current += 1; setPreviewLoading(false) }
  function beginPreviewTarget(action) { setActivePreviewTarget(action) }
  return <SessionContext.Provider value={{sessionId, ...state, event, currentProfile, valueWeights: committedValues,
    preview, previewValueWeights, previewLoading, activePreviewTransition, latestActionTransition, latestRationaleTransition,
    latestRoundTransition, candidateEvent, setCandidateEvent, calendarEvents, loading, startRound, loadPreview, commitDecision, sendChat,
    calendarActionLoading, calendarActionError, sendCalendarAction,
    onboardingLoading, onboardingError, onboardingAssistantMessage, startOnboarding, sendOnboardingMessage,
    skipOnboardingQuestion, useNeutralPrior, logInitialProfileViewed, logProfileInteraction,
    invalidatePreviewRequests, beginPreviewTarget,
    clearPreview: () => {previewRequest.current += 1; setPreview(null); setPreviewLoading(false); setActivePreviewTarget(null)}}}>{children}</SessionContext.Provider>
}
