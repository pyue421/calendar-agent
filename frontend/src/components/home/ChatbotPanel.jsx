import React, {useEffect, useMemo, useRef, useState} from "react"
import {createPortal} from "react-dom"
import {useSession} from "../../services/SessionContext"
import {actionCandidate, canReschedule, candidateEvent, editedSchedule, requestedFields, scheduleConflicts, weekDates} from "./scenario-card-model"
import "./chatbot.css"

export default function ChatbotPanel() {
  const session = useSession()
  const {sessionId, current_round, total_rounds, round_status, loading, awaiting_rationale, startRound, sendChat} = session
  const [messages, setMessages] = useState([{id: "welcome", role: "assistant", text: "Welcome. Your value profile will begin to appear after your first scheduling decision and reflection. Start Round 1 when you are ready."}])
  const [input, setInput] = useState("")
  const [sending, setSending] = useState(false)
  const scrollRef = useRef(null)
  useEffect(() => { if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight }, [messages])

  async function handleStartRound() {
    setSending(true)
    try {
      const data = await startRound()
      if (data.status === "session_complete") { setMessages(items => [...items, {id: "complete", role: "assistant", text: "All 15 rounds are complete. Thank you for reflecting on these scheduling decisions."}]); return }
      setMessages(items => [...items, {id: `round-${data.round}`, role: "assistant", meta: `Round ${data.round} of ${data.total_rounds}`, text: data.event.description, card: {...data.event, round: data.round}}])
    } catch (error) { setMessages(items => [...items, {id: `err-${Date.now()}`, role: "assistant", text: error.message}]) }
    finally { setSending(false) }
  }

  async function handleDecision(messageId, action, schedule) {
    setSending(true)
    try {
      const data = await session.commitDecision(action, schedule)
      setMessages(items => [...items.map(item => item.id === messageId ? {...item, card: {...item.card, committedAction: action}} : item), {id: `why-${data.decision_id}`, role: "assistant", text: "What mattered most to you in making that decision?", meta: "Reflection"}])
    } catch (error) { setMessages(items => [...items, {id: `err-${Date.now()}`, role: "assistant", text: error.message}]) }
    finally { setSending(false) }
  }

  async function sendMessage() {
    const text = input.trim(); if (!text || sending) return
    setInput(""); setMessages(items => [...items, {id: `user-${Date.now()}`, role: "user", content: text}]); setSending(true)
    try { const data = await sendChat(text); setMessages(items => [...items, {id: `assistant-${Date.now()}`, role: "assistant", text: data.text}]) }
    catch (error) {
      if (awaiting_rationale) setInput(text)
      setMessages(items => [...items, {id: `err-${Date.now()}`, role: "assistant", text: error.message}])
    }
    finally { setSending(false) }
  }

  const canStart = ["ready", "complete"].includes(round_status) && current_round < total_rounds
  return <section className="chatbot-panel"><header className="chatbot-header"><div className="chatbot-header-left"><span className="chatbot-header-title">DISCOVER Agent<span className="chatbot-round-label">{`Round ${current_round} of ${total_rounds} · ${round_status}`}</span></span></div></header>
    <div className="chatbot-messages" ref={scrollRef}>{messages.map(message => message.role === "user" ? <div key={message.id} className="chatbot-msg chatbot-msg-user"><div className="chatbot-user-bubble">{message.content}</div></div> : <div key={message.id} className="chatbot-msg chatbot-msg-assistant">{message.meta && <div className="chatbot-message-meta">{message.meta}</div>}<p className="chatbot-assistant-text">{message.text}</p>{message.card && <ScenarioCard card={message.card} disabled={Boolean(message.card.committedAction)} onDecision={(action, schedule) => handleDecision(message.id, action, schedule)}/>}</div>)}{sending && <div className="chatbot-msg chatbot-msg-assistant"><p className="chatbot-assistant-text chatbot-thinking">Thinking…</p></div>}</div>
    <div className="chatbot-input-wrap">{canStart && <div className="round-controls"><button className="preview-button" onClick={handleStartRound} disabled={sending}>{current_round === 0 ? "Start Round 1" : `Start Round ${current_round + 1}`}</button></div>}<div className="chatbot-input-box"><textarea className="chatbot-textarea" placeholder={awaiting_rationale ? "Explain what mattered in your decision" : "Ask about the scheduling options"} value={input} onChange={event => setInput(event.target.value)} onKeyDown={event => {if (event.key === "Enter" && !event.shiftKey) {event.preventDefault(); sendMessage()}}} rows={1} disabled={!sessionId || loading || sending}/><div className="chatbot-input-footer"><div/><button type="button" className="chatbot-send-btn" onClick={sendMessage} aria-label="Send" disabled={sending || !input.trim()}><svg viewBox="0 0 14 14" fill="none"><path d="M7 11V3M3 7l4-4 4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg></button></div></div></div>
  </section>
}

function ScenarioCard({card, onDecision, disabled}) {
  const session = useSession()
  const requested = useMemo(() => requestedFields(card), [card])
  const [date, setDate] = useState(requested.date)
  const [startTime, setStartTime] = useState(requested.startTime)
  const [endTime, setEndTime] = useState(requested.endTime)
  const [conflictPopover, setConflictPopover] = useState(null)
  const [activePreviewAction, setActivePreviewAction] = useState(null)
  const closeTimer = useRef(null)
  const edited = editedSchedule(date, startTime, endTime)
  const candidateConflicts = edited.valid ? scheduleConflicts(session.calendarEvents, edited.schedule) : []
  const rescheduleEnabled = !disabled && canReschedule(requested.schedule, edited) && candidateConflicts.length === 0
  const acceptConflicts = session.active_request_conflicts || []
  const acceptEnabled = !disabled && session.accept_available !== false

  useEffect(() => { const event = disabled ? null : candidateEvent(card, requested.schedule, edited); session.setCandidateEvent(event ? {...event, invalid: candidateConflicts.length > 0} : null) }, [card, date, disabled, endTime, startTime, candidateConflicts.length]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => { clearTimeout(closeTimer.current); session.setCandidateEvent(null); session.clearPreview() }, []) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const key = event => {
      if (event.key !== "Escape") return
      clearTimeout(closeTimer.current); setConflictPopover(null); setActivePreviewAction(null); session.clearPreview()
    }
    window.addEventListener("keydown", key)
    return () => window.removeEventListener("keydown", key)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (activePreviewAction !== "reschedule" || !rescheduleEnabled) return
    const timer = setTimeout(() => session.loadPreview("reschedule", edited.schedule, "hover").catch(() => {}), 350)
    return () => clearTimeout(timer)
  }, [date, endTime, startTime, activePreviewAction, rescheduleEnabled]) // eslint-disable-line react-hooks/exhaustive-deps

  function cancelClose() { clearTimeout(closeTimer.current) }
  function closePreview() { cancelClose(); setConflictPopover(null); setActivePreviewAction(null); session.clearPreview() }
  function scheduleClose() { cancelClose(); closeTimer.current = setTimeout(closePreview, 140) }
  function show(action, target) {
    cancelClose()
    if (disabled) return
    const conflicts = action === "accept" ? acceptConflicts : action === "reschedule" ? candidateConflicts : []
    if (conflicts.length) { setConflictPopover({anchor: target.getBoundingClientRect(), conflicts}); setActivePreviewAction(null); session.clearPreview(); return }
    const candidate = actionCandidate(action, requested.schedule, edited)
    if (action === "reschedule" && !candidate) return
    setConflictPopover(null); setActivePreviewAction(action)
    session.loadPreview(action, candidate, "hover").catch(() => {})
  }
  function actionProps(action) { return {onMouseEnter: event => show(action, event.currentTarget), onMouseLeave: scheduleClose, onFocus: event => show(action, event.currentTarget), onBlur: scheduleClose} }
  function decide(action) { closePreview(); session.setCandidateEvent(null); onDecision(action, actionCandidate(action, requested.schedule, edited)) }

  return <div className="meeting-card scenario-decision-card"><div className="meeting-card-header"><span className="meeting-card-title">Scenario {card.round || session.current_round}</span></div><div className="meeting-card-body">
    <label className="meeting-field"><span className="meeting-field-label">Meeting title</span><input className="meeting-field-input" value={card.title} disabled/></label>
    <div className="meeting-field-row"><label className="meeting-field meeting-field-date"><span className="meeting-field-label">Date</span><select className="meeting-field-input meeting-field-select" value={date} disabled={disabled} onChange={event => setDate(event.target.value)}>{weekDates(session.week_start, requested.date).map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label><div className="meeting-field"><span className="meeting-field-label">Time</span><div className="meeting-time-range"><input aria-label="Start time" className="meeting-field-input" type="time" value={startTime} disabled={disabled} onChange={event => setStartTime(event.target.value)}/><span className="meeting-time-sep">–</span><input aria-label="End time" className="meeting-field-input" type="time" value={endTime} disabled={disabled} onChange={event => setEndTime(event.target.value)}/></div></div></div>
    {!edited.valid && <p className="meeting-schedule-error" role="alert">{edited.error}</p>}
    {candidateConflicts.length > 0 && <p className="meeting-schedule-error" role="alert">This time overlaps with {candidateConflicts.map(item => item.title).join(", ")}.</p>}
    <div className="meeting-decision-row"><span className="meeting-action-target" {...actionProps("decline")}><button className="meeting-reject-btn" disabled={disabled} onClick={() => decide("decline")}>Decline</button></span><span className="meeting-action-target" {...actionProps("reschedule")}><button className="meeting-reschedule-btn" disabled={!rescheduleEnabled} onClick={() => decide("reschedule")}>Reschedule</button></span><span className="meeting-action-target" {...actionProps("accept")}><button className="meeting-accept-btn" disabled={!acceptEnabled} onClick={() => decide("accept")}>Accept</button></span></div>
    {card.committedAction && <p className="decision-recorded">Decision recorded: {card.committedAction}</p>}
  </div>{conflictPopover && createPortal(<ConflictPopover conflicts={conflictPopover.conflicts} anchor={conflictPopover.anchor} onMouseEnter={cancelClose} onMouseLeave={scheduleClose}/>, document.body)}</div>
}

function ConflictPopover({conflicts, anchor, onMouseEnter, onMouseLeave}) {
  const left = Math.max(8, Math.min(window.innerWidth - 330, anchor.right + 12))
  return <aside className="availability-popover" style={{left, top: Math.max(8, anchor.top)}} onMouseEnter={onMouseEnter} onMouseLeave={onMouseLeave}><strong>Time unavailable</strong><p>This time overlaps with {conflicts.map(item => `${item.title} (${new Date(item.start).toLocaleTimeString([], {hour: "numeric", minute: "2-digit"})}–${new Date(item.end).toLocaleTimeString([], {hour: "numeric", minute: "2-digit"})})`).join(", ")}.</p><small>Move or remove the conflicting event, reschedule this request, or decline it.</small></aside>
}
