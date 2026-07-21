import React, { useEffect, useState } from "react"
import { useSession } from "../../services/SessionContext"
import "./chatbot.css"

function localInputValue(iso) { return iso ? iso.slice(0, 16) : "" }

export default function ChatbotPanel() {
  const { event, loading, loadPreview, commitDecision, pendingDecision, submitRationale, setCandidateEvent, clearPreview } = useSession()
  const [start, setStart] = useState("")
  const [rationale, setRationale] = useState("")
  const [busy, setBusy] = useState(false)
  const [committed, setCommitted] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => { if (event) setStart(localInputValue(event.requested_start)) }, [event])
  useEffect(() => {
    if (!event || !start) return
    const duration = new Date(event.requested_end) - new Date(event.requested_start)
    const end = new Date(new Date(start).getTime() + duration).toISOString().slice(0, 19)
    const schedule = { start: `${start}:00`, end }
    setCandidateEvent({ id: `${event.id}_candidate`, title: `${event.title} (candidate)`, ...schedule, temporary: true })
    const timer = setTimeout(() => loadPreview("reschedule", schedule, "pinned").catch(console.error), 350)
    return () => clearTimeout(timer)
  }, [start, event]) // eslint-disable-line react-hooks/exhaustive-deps

  async function act(action, displayState = "pinned") {
    setBusy(true)
    try { await loadPreview(action, null, displayState) } finally { setBusy(false) }
  }

  async function commit(action) {
    setBusy(true)
    try {
      let schedule = null
      if (action === "reschedule") {
        const duration = new Date(event.requested_end) - new Date(event.requested_start)
        schedule = { start: `${start}:00`, end: new Date(new Date(start).getTime() + duration).toISOString().slice(0, 19) }
      }
      await commitDecision(action, schedule); setCommitted(true)
    } finally { setBusy(false) }
  }

  async function sendRationale(e) {
    e.preventDefault(); if (!rationale.trim()) return
    setBusy(true); setError("")
    try { await submitRationale(rationale.trim()); setRationale("") }
    catch (requestError) { setError(requestError.message || "Could not analyze the rationale.") }
    finally { setBusy(false) }
  }

  return <section className="chatbot-panel reflection-panel">
    <header className="chatbot-header"><span className="chatbot-header-title">Calendar reflection</span></header>
    <div className="reflection-content">
      {loading && <p>Loading your calendar…</p>}
      {event && !committed && <>
        <p className="reflection-eyebrow">Incoming request</p>
        <h3>{event.title}</h3>
        <p>{event.description}</p>
        <p><strong>{new Date(event.requested_start).toLocaleString()}</strong> · {event.requester}</p>
        <div className="decision-grid">
          {["accept", "decline"].map(action => <div className="decision-option" key={action}>
            <button onMouseEnter={() => act(action, "hover")} onFocus={() => act(action, "focus")} onClick={() => commit(action)} disabled={busy} className="meeting-confirm-btn">{action[0].toUpperCase() + action.slice(1)}</button>
            <button onClick={() => act(action)} disabled={busy} className="preview-button">Preview values</button>
          </div>)}
        </div>
        <div className="reschedule-box">
          <label htmlFor="candidate-time">Try another date and time</label>
          <input id="candidate-time" type="datetime-local" value={start} onChange={e => setStart(e.target.value)} />
          <div className="reschedule-actions"><button onClick={() => commit("reschedule")} disabled={busy} className="meeting-confirm-btn">Confirm reschedule</button><button onClick={() => { setStart(localInputValue(event.requested_start)); setCandidateEvent(null); clearPreview() }} className="preview-button">Cancel</button></div>
        </div>
      </>}
      {pendingDecision && <form onSubmit={sendRationale} className="rationale-form">
        <h3>{pendingDecision.prompt}</h3>
        <p>Your explanation is used as separate evidence and does not define your “true” values.</p>
        <textarea value={rationale} onChange={e => setRationale(e.target.value)} rows="5" placeholder="Tell us what mattered in this situation…" />
        {error && <p className="reflection-error" role="alert">{error}</p>}
        <button className="meeting-confirm-btn" disabled={busy || !rationale.trim()}>Update reflection</button>
      </form>}
      {committed && !pendingDecision && <div><h3>Reflection saved</h3><p>Your committed profile now includes both the scheduling action and your explanation.</p></div>}
    </div>
  </section>
}
