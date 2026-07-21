/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useCallback, useContext, useEffect, useState } from "react"

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000"
const SessionContext = createContext(null)

export function useSession() { return useContext(SessionContext) }

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  })
  if (!response.ok) throw new Error((await response.json()).detail || "Request failed")
  return response.json()
}

function toLegacyValues(profile = []) {
  const tones = ["green", "rose", "amber", "cyan", "violet"]
  return [...profile].sort((a, b) => b.weight - a.weight).slice(0, 5).map((value, index) => ({
    ...value, weight: Math.round(value.weight), tone: tones[index],
    evidence: [{ id: `${value.id}-r`, text: "Posterior estimate from committed evidence", round: 0 }],
    calendarEvents: [{ id: `${value.id}-c`, text: `Uncertainty ±${value.uncertainty}%`, round: 0 }],
  }))
}

export default function SessionProvider({ children }) {
  const [sessionId, setSessionId] = useState(null)
  const [event, setEvent] = useState(null)
  const [currentProfile, setCurrentProfile] = useState([])
  const [preview, setPreview] = useState(null)
  const [candidateEvent, setCandidateEvent] = useState(null)
  const [pendingDecision, setPendingDecision] = useState(null)
  const [calendarEvents, setCalendarEvents] = useState([])
  const [loading, setLoading] = useState(true)

  const initialize = useCallback(async () => {
    setLoading(true)
    try {
      const session = await request("/api/sessions", { method: "POST", body: JSON.stringify({ participant_id: `participant_${Date.now()}` }) })
      setSessionId(session.session_id); setCurrentProfile(session.current_profile); setCalendarEvents(session.calendar)
      const next = await request(`/api/sessions/${session.session_id}/events/next`, { method: "POST" })
      setEvent(next.event)
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { initialize().catch(console.error) }, [initialize])

  async function loadPreview(action, candidateSchedule, displayState = "pinned") {
    const result = await request(`/api/sessions/${sessionId}/previews`, {
      method: "POST", body: JSON.stringify({ event_id: event.id, action, candidate_schedule: candidateSchedule, display_state: displayState }),
    })
    setPreview(result)
    return result
  }

  async function commitDecision(action, candidateSchedule) {
    const result = await request(`/api/sessions/${sessionId}/decisions`, {
      method: "POST", body: JSON.stringify({ event_id: event.id, action, candidate_schedule: candidateSchedule }),
    })
    setCurrentProfile(result.current_profile); setCalendarEvents(result.calendar); setPendingDecision(result); setPreview(null); setCandidateEvent(null)
    return result
  }

  async function submitRationale(rationale) {
    const result = await request(`/api/sessions/${sessionId}/rationales`, {
      method: "POST", body: JSON.stringify({ decision_id: pendingDecision.decision_id, rationale }),
    })
    setCurrentProfile(result.current_profile); setPendingDecision(null)
    return result
  }

  return <SessionContext.Provider value={{
    sessionId, event, currentProfile, valueWeights: toLegacyValues(currentProfile), preview,
    candidateEvent, setCandidateEvent, pendingDecision, calendarEvents, loading,
    loadPreview, commitDecision, submitRationale, clearPreview: () => setPreview(null),
    sendCalendarAction: async () => ({ calendar_events: calendarEvents }),
  }}>{children}</SessionContext.Provider>
}
