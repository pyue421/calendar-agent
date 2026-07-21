import React, { createContext, useContext, useState, useCallback, useEffect } from "react"

const API_BASE = "http://127.0.0.1:8000"

const SessionContext = createContext(null)

export function useSession() {
  return useContext(SessionContext)
}

export default function SessionProvider({ children }) {
  const [sessionId, setSessionId] = useState(null)
  const [currentRound, setCurrentRound] = useState(0)
  const [phase, setPhase] = useState(null)
  const [calendarEvents, setCalendarEvents] = useState([])
  const [valueWeights, setValueWeights] = useState([])
  const [roundStatus, setRoundStatus] = useState(null)
  const [loading, setLoading] = useState(false)
  // Optimistic, client-side-only preview of the "New Values" bubbles while a
  // scenario decision (accept/decline/postpone) is being considered or has
  // just been made — see services/valuePreview.js. Null means "show the
  // real value_weights from the backend". previewConfirmed distinguishes an
  // unconfirmed preview (dimmed bubbles) from a confirmed decision (full-color
  // bubbles showing the previewed weights until the round completes).
  const [previewValueWeights, setPreviewValueWeights] = useState(null)
  const [previewConfirmed, setPreviewConfirmed] = useState(false)

  // Create session on mount
  useEffect(() => {
    const stored = localStorage.getItem("discover_session_id")
    if (stored) {
      setSessionId(stored)
      refreshState(stored)
    }
  }, [])

  async function createSession(participantId = "") {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/session/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ participant_id: participantId }),
      })
      const data = await res.json()
      setSessionId(data.session_id)
      setCalendarEvents(data.calendar_events || [])
      localStorage.setItem("discover_session_id", data.session_id)
      return data
    } finally {
      setLoading(false)
    }
  }

  async function refreshState(sid) {
    const id = sid || sessionId
    if (!id) return
    try {
      const res = await fetch(`${API_BASE}/api/session/${id}/state`)
      const data = await res.json()
      setCurrentRound(data.current_round)
      setPhase(data.phase)
      setCalendarEvents(data.calendar_events || [])
      setValueWeights(data.value_weights || [])
      setRoundStatus(data.round_status)
      return data
    } catch (e) {
      console.error("Failed to refresh session state:", e)
    }
  }

  async function startRound() {
    if (!sessionId) return
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/start-round`, {
        method: "POST",
      })
      const data = await res.json()
      setCurrentRound(data.round)
      setPhase(data.phase)
      // Proposed events stay pending (shown only in the chat's meeting card)
      // until the user accepts them via sendCalendarAction — see MeetingCard.
      if (data.existing_events) setCalendarEvents(data.existing_events)
      return data
    } finally {
      setLoading(false)
    }
  }

  async function sendChat(message) {
    if (!sessionId) return
    const res = await fetch(`${API_BASE}/api/session/${sessionId}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    })
    return await res.json()
  }

  async function sendCalendarAction(action, eventId, details = null) {
    if (!sessionId) return
    const res = await fetch(`${API_BASE}/api/session/${sessionId}/calendar-action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, event_id: eventId, details }),
    })
    const data = await res.json()
    if (data.calendar_events) setCalendarEvents(data.calendar_events)
    return data
  }

  async function completeRound() {
    if (!sessionId) return
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/complete-round`, {
        method: "POST",
      })
      const data = await res.json()
      if (data.value_weights) {
        setValueWeights(data.value_weights)
        // Real weights just landed — drop the optimistic preview override.
        setPreviewValueWeights(null)
        setPreviewConfirmed(false)
      }
      return data
    } finally {
      setLoading(false)
    }
  }

  async function submitReflection(response) {
    if (!sessionId) return
    const res = await fetch(`${API_BASE}/api/session/${sessionId}/reflect`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ response }),
    })
    return await res.json()
  }

  return (
    <SessionContext.Provider
      value={{
        sessionId,
        currentRound,
        phase,
        calendarEvents,
        valueWeights,
        previewValueWeights,
        setPreviewValueWeights,
        previewConfirmed,
        setPreviewConfirmed,
        roundStatus,
        loading,
        createSession,
        refreshState,
        startRound,
        sendChat,
        sendCalendarAction,
        completeRound,
        submitReflection,
      }}
    >
      {children}
    </SessionContext.Provider>
  )
}
