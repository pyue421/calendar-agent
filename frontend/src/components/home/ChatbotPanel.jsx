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
  const [popover, setPopover] = useState(null)
  const closeTimer = useRef(null)
  const edited = editedSchedule(date, startTime, endTime)
  const candidateConflicts = edited.valid ? scheduleConflicts(session.calendarEvents, edited.schedule) : []
  const rescheduleEnabled = !disabled && canReschedule(requested.schedule, edited) && candidateConflicts.length === 0
  const acceptConflicts = session.active_request_conflicts || []
  const acceptEnabled = !disabled && session.accept_available !== false

  useEffect(() => { const event = disabled ? null : candidateEvent(card, requested.schedule, edited); session.setCandidateEvent(event ? {...event, invalid: candidateConflicts.length > 0} : null) }, [card, date, disabled, endTime, startTime, candidateConflicts.length]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => { clearTimeout(closeTimer.current); session.setCandidateEvent(null); session.clearPreview() }, []) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (popover?.action !== "reschedule" || !rescheduleEnabled) return
    const timer = setTimeout(() => session.loadPreview("reschedule", edited.schedule, "hover").catch(() => {}), 350)
    return () => clearTimeout(timer)
  }, [date, endTime, startTime, popover?.action, rescheduleEnabled]) // eslint-disable-line react-hooks/exhaustive-deps

  function cancelClose() { clearTimeout(closeTimer.current) }
  function closePreview() { cancelClose(); setPopover(null); session.clearPreview() }
  function scheduleClose() { cancelClose(); closeTimer.current = setTimeout(closePreview, 140) }
  function show(action, target) {
    cancelClose()
    const conflicts = action === "accept" ? acceptConflicts : action === "reschedule" ? candidateConflicts : []
    if (conflicts.length) { setPopover({action, anchor: target.getBoundingClientRect(), conflicts}); session.clearPreview(); return }
    const candidate = actionCandidate(action, requested.schedule, edited)
    if (action === "reschedule" && !candidate) return
    setPopover({action, anchor: target.getBoundingClientRect()})
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
  </div>{popover && createPortal(popover.conflicts ? <ConflictPopover conflicts={popover.conflicts} anchor={popover.anchor} onMouseEnter={cancelClose} onMouseLeave={scheduleClose}/> : <ValuePreviewPopover preview={session.preview?.action === popover.action ? session.preview : null} loading={session.previewLoading} anchor={popover.anchor} onClose={closePreview} onMouseEnter={cancelClose} onMouseLeave={scheduleClose}/>, document.body)}</div>
}

function ConflictPopover({conflicts, anchor, onMouseEnter, onMouseLeave}) {
  const left = Math.max(8, Math.min(window.innerWidth - 330, anchor.right + 12))
  return <aside className="availability-popover" style={{left, top: Math.max(8, anchor.top)}} onMouseEnter={onMouseEnter} onMouseLeave={onMouseLeave}><strong>Time unavailable</strong><p>This time overlaps with {conflicts.map(item => `${item.title} (${new Date(item.start).toLocaleTimeString([], {hour: "numeric", minute: "2-digit"})}–${new Date(item.end).toLocaleTimeString([], {hour: "numeric", minute: "2-digit"})})`).join(", ")}.</p><small>Move or remove the conflicting event, reschedule this request, or decline it.</small></aside>
}

function ValuePreviewPopover({preview, loading, anchor, onClose, onMouseEnter, onMouseLeave}) {
  const ref = useRef(null)
  useEffect(() => { const key = event => {if (event.key === "Escape") onClose()}; window.addEventListener("keydown", key); return () => window.removeEventListener("keydown", key) }, [onClose])
  const left = Math.min(window.innerWidth - 650, anchor.right + 12)
  const top = Math.max(8, Math.min(anchor.top, window.innerHeight - 390))
  return <aside ref={ref} className="value-preview-popover" style={{left: Math.max(8, left), top}} role="dialog" aria-label="Hypothetical value profile" onMouseEnter={onMouseEnter} onMouseLeave={onMouseLeave}><header><div><small>Counterfactual only</small><h3>Hypothetical value profile</h3></div><button onClick={onClose} aria-label="Close preview">×</button></header>{loading || !preview ? <p className="preview-loading">Loading preview…</p> : preview.feasible === false ? <p className="meeting-schedule-error">This option is no longer available because the calendar changed.</p> : <div className="popover-bubbles">{preview.preview_profile.map((value, index) => {const size = 80 + value.weight * 2.1; return <div className="popover-bubble-slot" key={value.id}><div className={`value-bubble value-bubble-${["green", "rose", "amber", "cyan", "violet"][index % 5]}`} style={{width: size, height: size}}/><span>{value.label}</span><strong>{Math.round(value.weight)}%</strong><small>±{value.uncertainty}%</small></div>})}</div>}<p>This preview does not change your current value profile.</p></aside>
}
