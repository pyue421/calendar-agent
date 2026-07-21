/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useCallback, useContext, useEffect, useState } from "react"

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000"
const SessionContext = createContext(null)
export function useSession() { return useContext(SessionContext) }

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {...options, headers: {"Content-Type": "application/json", ...(options.headers || {})}})
  const data = await response.json()
  if (!response.ok) throw new Error(data.detail || "Request failed")
  return data
}

function displayValues(profile = []) {
  const tones = ["green", "rose", "amber", "cyan", "violet"]
  return profile.map((value, index) => ({...value, weight: value.relative_weight, tone: tones[index],
    evidence: value.conversation_evidence || [], calendarEvents: value.calendar_action_evidence || []}))
}

export default function SessionProvider({children}) {
  const [sessionId, setSessionId] = useState(null)
  const [state, setState] = useState({current_round: 0, total_rounds: 15, profile_status: "uninitialized", round_status: "loading"})
  const [event, setEvent] = useState(null)
  const [currentProfile, setCurrentProfile] = useState([])
  const [preview, setPreview] = useState(null)
  const [candidateEvent, setCandidateEvent] = useState(null)
  const [calendarEvents, setCalendarEvents] = useState([])
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
    const data = await request(`/api/sessions/${sessionId}/events/next`, {method: "POST"}); applyState(data)
    if (data.event) setEvent(data.event); return data
  }
  async function loadPreview(action, candidateSchedule, displayState = "hover") {
    const data = await request(`/api/sessions/${sessionId}/previews`, {method: "POST", body: JSON.stringify({event_id: event.scenario_id, action, candidate_schedule: candidateSchedule, display_state: displayState})})
    setPreview(data); return data
  }
  async function commitDecision(action, candidateSchedule) {
    const data = await request(`/api/sessions/${sessionId}/decisions`, {method: "POST", body: JSON.stringify({event_id: event.scenario_id, action, candidate_schedule: candidateSchedule})})
    applyState(data); setPreview(null); setCandidateEvent(null); return data
  }
  async function sendChat(message) {
    const data = await request(`/api/sessions/${sessionId}/chat`, {method: "POST", body: JSON.stringify({message})})
    applyState(data); if (data.rationale_recorded) setEvent(null); return data
  }
  return <SessionContext.Provider value={{sessionId, ...state, event, currentProfile, valueWeights: displayValues(currentProfile),
    preview, candidateEvent, setCandidateEvent, calendarEvents, loading, startRound, loadPreview, commitDecision, sendChat,
    clearPreview: () => setPreview(null), sendCalendarAction: async () => ({calendar_events: calendarEvents})}}>{children}</SessionContext.Provider>
}
