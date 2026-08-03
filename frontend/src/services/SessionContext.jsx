/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react"

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

function displayValues(profile = []) {
  const fallbackTones = {wellbeing: "green", achievement_growth: "rose", relationships_care: "amber",
    autonomy_privacy: "cyan", responsibility_fairness: "violet"}
  return profile.map(value => ({...value, weight: value.relative_weight,
    tone: value.tone || fallbackTones[value.id] || "neutral",
    evidence: value.evidence || [...(value.conversation_evidence || []), ...(value.calendar_action_evidence || [])]}))
}

export default function SessionProvider({children}) {
  const [sessionId, setSessionId] = useState(null)
  const [state, setState] = useState({current_round: 0, total_rounds: 15, profile_status: "uninitialized", round_status: "loading"})
  const [event, setEvent] = useState(null)
  const [currentProfile, setCurrentProfile] = useState([])
  const [preview, setPreview] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const previewRequest = useRef(0)
  const [candidateEvent, setCandidateEvent] = useState(null)
  const [calendarEvents, setCalendarEvents] = useState([])
  const [calendarActionLoading, setCalendarActionLoading] = useState(false)
  const [calendarActionError, setCalendarActionError] = useState(null)
  const [loading, setLoading] = useState(true)
  const applyState = useCallback(data => {
    setState(previous => ({...previous, ...data}))
    if (data.current_profile) setCurrentProfile(data.current_profile)
    if (data.calendar) setCalendarEvents(data.calendar)
  }, [])
  const initialize = useCallback(async () => {
    setLoading(true)
    try {
      const session = await request("/api/sessions", {method: "POST", body: JSON.stringify({participant_id: `participant_${Date.now()}`})})
      setSessionId(session.session_id); applyState(session)
    } finally { setLoading(false) }
  }, [applyState])
  useEffect(() => { initialize().catch(console.error) }, [initialize])

  async function startRound() {
    previewRequest.current += 1; setPreview(null); setPreviewLoading(false); setCandidateEvent(null)
    const data = await request(`/api/sessions/${sessionId}/events/next`, {method: "POST"}); applyState(data)
    if (data.event) setEvent(data.event); return data
  }
  async function loadPreview(action, candidateSchedule, displayState = "hover") {
    const requestNumber = ++previewRequest.current; setPreview(null); setPreviewLoading(true)
    try {
      const data = await request(`/api/sessions/${sessionId}/previews`, {method: "POST", body: JSON.stringify({event_id: event.scenario_id, action, candidate_schedule: candidateSchedule, display_state: displayState})})
      if (requestNumber === previewRequest.current) setPreview(data)
      return data
    } finally {
      if (requestNumber === previewRequest.current) setPreviewLoading(false)
    }
  }
  async function commitDecision(action, candidateSchedule) {
    const data = await request(`/api/sessions/${sessionId}/decisions`, {method: "POST", body: JSON.stringify({event_id: event.scenario_id, action, candidate_schedule: candidateSchedule})})
    previewRequest.current += 1; applyState(data); setPreview(null); setPreviewLoading(false); setCandidateEvent(null); return data
  }
  async function sendChat(message) {
    const data = await request(`/api/sessions/${sessionId}/chat`, {method: "POST", body: JSON.stringify({message})})
    applyState(data); if (data.rationale_recorded) setEvent(null); return data
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
  const previewValueWeights = preview?.feasible !== false && preview?.preview_profile ? displayValues(preview.preview_profile) : null
  return <SessionContext.Provider value={{sessionId, ...state, event, currentProfile, valueWeights: displayValues(currentProfile),
    preview, previewValueWeights, previewLoading, candidateEvent, setCandidateEvent, calendarEvents, loading, startRound, loadPreview, commitDecision, sendChat,
    calendarActionLoading, calendarActionError, sendCalendarAction,
    clearPreview: () => {previewRequest.current += 1; setPreview(null); setPreviewLoading(false)}}}>{children}</SessionContext.Provider>
}
