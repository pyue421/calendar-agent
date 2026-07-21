import React, { useEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"
import { useSession } from "../../services/SessionContext"
import "./chatbot.css"

export default function ChatbotPanel() {
  const session = useSession()
  const {sessionId, current_round, total_rounds, round_status, calibration_complete, calibration,
    loading, awaiting_rationale, submitCalibration, startRound, sendChat} = session
  const [messages, setMessages] = useState([{id: "welcome", role: "assistant", text: "Welcome. First, complete a brief baseline calibration. These questions initialize a situated scheduling profile—not your objectively true values."}])
  const [input, setInput] = useState("")
  const [sending, setSending] = useState(false)
  const scrollRef = useRef(null)

  useEffect(() => { if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight }, [messages, calibration?.responses])

  async function answerCalibration(question, choice, rationale) {
    setSending(true)
    try {
      const data = await submitCalibration(question.question_id, choice, rationale)
      setMessages(msgs => [...msgs,
        {id: `cal-user-${question.question_id}`, role: "user", content: `${question.options.find(o => o.id === choice).label}. ${rationale}`},
        {id: `cal-assistant-${question.question_id}`, role: "assistant", text: data.calibration_complete ? "Baseline calibration is complete. Your current profile is now based on your six choices and explanations. You can start Round 1." : "Thanks. Here is the next calibration trade-off."}
      ])
    } catch (error) { setMessages(msgs => [...msgs, {id: `err-${Date.now()}`, role: "assistant", text: error.message}]) }
    finally { setSending(false) }
  }

  async function handleStartRound() {
    setSending(true)
    try {
      const data = await startRound()
      if (data.status === "session_complete") {
        setMessages(msgs => [...msgs, {id: "complete", role: "assistant", text: "All 15 rounds are complete. Thank you for reflecting on these scheduling decisions."}]); return
      }
      setMessages(msgs => [...msgs, {id: `round-${data.round}`, role: "assistant",
        meta: `Round ${data.round} of ${data.total_rounds}`, text: data.event.description, card: data.event}])
    } catch (error) { setMessages(msgs => [...msgs, {id: `err-${Date.now()}`, role: "assistant", text: error.message}]) }
    finally { setSending(false) }
  }

  async function handleDecision(messageId, action, schedule) {
    setSending(true)
    try {
      const data = await session.commitDecision(action, schedule)
      setMessages(msgs => [...msgs.map(m => m.id === messageId ? {...m, card: {...m.card, committedAction: action}} : m),
        {id: `why-${data.decision_id}`, role: "assistant", text: "What mattered most to you in making that decision?", meta: "Reflection"}])
    } catch (error) { setMessages(msgs => [...msgs, {id: `err-${Date.now()}`, role: "assistant", text: error.message}]) }
    finally { setSending(false) }
  }

  async function sendMessage() {
    const text = input.trim(); if (!text || sending) return
    setInput(""); setMessages(msgs => [...msgs, {id: `user-${Date.now()}`, role: "user", content: text}]); setSending(true)
    try {
      const data = await sendChat(text)
      setMessages(msgs => [...msgs, {id: `assistant-${Date.now()}`, role: "assistant", text: data.text}])
    } catch (error) { setMessages(msgs => [...msgs, {id: `err-${Date.now()}`, role: "assistant", text: error.message}]) }
    finally { setSending(false) }
  }

  const currentCalibration = !calibration_complete && calibration?.questions?.[calibration.responses || 0]
  const canStart = calibration_complete && ["ready", "complete"].includes(round_status) && current_round < total_rounds

  return <section className="chatbot-panel">
    <header className="chatbot-header"><div className="chatbot-header-left"><span className="chatbot-header-title">DISCOVER Agent
      <span className="chatbot-round-label">{calibration_complete ? `Round ${current_round} of ${total_rounds} · ${round_status}` : `Calibration ${calibration?.responses || 0} of ${calibration?.questions?.length || 6}`}</span>
    </span></div></header>
    <div className="chatbot-messages" ref={scrollRef}>
      {messages.map(msg => msg.role === "user" ? <div key={msg.id} className="chatbot-msg chatbot-msg-user"><div className="chatbot-user-bubble">{msg.content}</div></div> :
        <div key={msg.id} className="chatbot-msg chatbot-msg-assistant">{msg.meta && <div className="chatbot-message-meta">{msg.meta}</div>}<p className="chatbot-assistant-text">{msg.text}</p>
          {msg.card && <ScenarioCard card={msg.card} disabled={Boolean(msg.card.committedAction)} onDecision={(action, schedule) => handleDecision(msg.id, action, schedule)} />}</div>)}
      {currentCalibration && <div className="chatbot-msg chatbot-msg-assistant"><CalibrationCard question={currentCalibration} disabled={sending} onSubmit={answerCalibration} /></div>}
      {sending && <div className="chatbot-msg chatbot-msg-assistant"><p className="chatbot-assistant-text chatbot-thinking">Thinking…</p></div>}
    </div>
    <div className="chatbot-input-wrap">
      {canStart && <div className="round-controls"><button className="preview-button" onClick={handleStartRound} disabled={sending}>{current_round === 0 ? "Start Round 1" : `Start Round ${current_round + 1}`}</button></div>}
      <div className="chatbot-input-box"><textarea className="chatbot-textarea" placeholder={awaiting_rationale ? "Explain what mattered in your decision" : "Ask about the scheduling options"} value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => {if (e.key === "Enter" && !e.shiftKey) {e.preventDefault(); sendMessage()}}} rows={1} disabled={!sessionId || loading || sending || !calibration_complete}/>
        <div className="chatbot-input-footer"><div/><button type="button" className="chatbot-send-btn" onClick={sendMessage} aria-label="Send" disabled={sending || !input.trim()}><svg viewBox="0 0 14 14" fill="none"><path d="M7 11V3M3 7l4-4 4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg></button></div>
      </div>
    </div>
  </section>
}

function CalibrationCard({question, onSubmit, disabled}) {
  const [choice, setChoice] = useState(""); const [reason, setReason] = useState("")
  return <div className="meeting-card calibration-card"><div className="meeting-card-header"><span className="meeting-card-title">Baseline calibration</span></div><div className="meeting-card-body"><p>{question.prompt}</p>
    <div className="calibration-options">{question.options.map(option => <button type="button" key={option.id} className={`calibration-option${choice === option.id ? " selected" : ""}`} onClick={() => setChoice(option.id)}>{option.label}</button>)}</div>
    <label className="meeting-field-label" htmlFor={`reason-${question.question_id}`}>Why does that option fit better?</label><textarea id={`reason-${question.question_id}`} className="meeting-field-input" rows="3" value={reason} onChange={e => setReason(e.target.value)} />
    <button className="meeting-confirm-btn" disabled={disabled || !choice || !reason.trim()} onClick={() => onSubmit(question, choice, reason.trim())}>Continue →</button></div></div>
}

function ScenarioCard({card, onDecision, disabled}) {
  const session = useSession(); const [candidateStart, setCandidateStart] = useState(card.requested_start.slice(0, 16)); const [popover, setPopover] = useState(null)
  const duration = new Date(card.requested_end) - new Date(card.requested_start)
  const schedule = {start: `${candidateStart}:00`, end: new Date(new Date(candidateStart).getTime() + duration).toISOString().slice(0, 19)}
  useEffect(() => {
    if (!candidateStart || disabled) return
    session.setCandidateEvent({id: `${card.scenario_id}-candidate`, title: `${card.title} (candidate)`, ...schedule, temporary: true})
    const timer = setTimeout(() => { if (popover?.action === "reschedule") session.loadPreview("reschedule", schedule, popover.pinned ? "pinned" : "hover").catch(() => {}) }, 350)
    return () => clearTimeout(timer)
  }, [candidateStart, popover?.action]) // eslint-disable-line react-hooks/exhaustive-deps

  function show(action, target, pinned = false) {
    const candidate = action === "reschedule" ? schedule : null
    setPopover({action, anchor: target.getBoundingClientRect(), pinned}); session.loadPreview(action, candidate, pinned ? "pinned" : "hover").catch(() => {})
  }
  function regionProps(action) { return {onMouseEnter: e => show(action, e.currentTarget), onMouseLeave: () => setPopover(cur => cur?.pinned ? cur : null), onFocus: e => show(action, e.currentTarget), onBlur: () => setPopover(cur => cur?.pinned ? cur : null)} }
  return <div className="meeting-card scenario-decision-card"><div className="meeting-card-header"><span className="meeting-card-title">{card.title}</span></div><div className="meeting-card-body"><p className="requester-line">From {card.requester}</p><p>{new Date(card.requested_start).toLocaleString()}</p>
    <div className="decision-region" {...regionProps("decline")}><strong>Decline</strong><span>Keep the conflicting commitment.</span><div><button className="meeting-reject-btn" disabled={disabled} onClick={() => onDecision("decline", null)}>Decline</button><button className="preview-button" onClick={e => show("decline", e.currentTarget, true)}>Preview values</button></div></div>
    <div className="decision-region" {...regionProps("accept")}><strong>Accept requested time</strong><span>Add the request at its proposed time.</span><div><button className="meeting-accept-btn" disabled={disabled} onClick={() => onDecision("accept", null)}>Accept →</button><button className="preview-button" onClick={e => show("accept", e.currentTarget, true)}>Preview values</button></div></div>
    <div className="decision-region" {...regionProps("reschedule")}><strong>Reschedule</strong><label className="meeting-field-label">Choose date and start time</label><input className="meeting-field-input" type="datetime-local" value={candidateStart} onChange={e => setCandidateStart(e.target.value)} min="2026-07-21T00:00"/><div><button className="meeting-confirm-btn" disabled={disabled} onClick={() => onDecision("reschedule", schedule)}>Confirm reschedule</button><button className="preview-button" onClick={e => show("reschedule", e.currentTarget, true)}>Preview values</button></div></div>
    {card.committedAction && <p className="decision-recorded">Decision recorded: {card.committedAction}</p>}
  </div>{popover && session.preview?.action === popover.action && createPortal(<ValuePreviewPopover preview={session.preview} anchor={popover.anchor} onClose={() => {setPopover(null); session.clearPreview()}} />, document.body)}</div>
}

function ValuePreviewPopover({preview, anchor, onClose}) {
  const ref = useRef(null)
  useEffect(() => {
    const key = e => {if (e.key === "Escape") onClose()}; const click = e => {if (ref.current && !ref.current.contains(e.target)) onClose()}
    window.addEventListener("keydown", key); window.addEventListener("mousedown", click); return () => {window.removeEventListener("keydown", key); window.removeEventListener("mousedown", click)}
  }, [onClose])
  const left = Math.min(window.innerWidth - 650, anchor.right + 12); const top = Math.max(8, Math.min(anchor.top, window.innerHeight - 390))
  return <aside ref={ref} className="value-preview-popover" style={{left: Math.max(8, left), top}} role="dialog" aria-label="Hypothetical value profile"><header><div><small>Counterfactual only</small><h3>Hypothetical value profile</h3></div><button onClick={onClose} aria-label="Close preview">×</button></header>
    <div className="popover-bubbles">{preview.preview_profile.map((value, index) => {const size = 80 + value.weight * 2.1; return <div className="popover-bubble-slot" key={value.id}><div className={`value-bubble value-bubble-${["green","rose","amber","cyan","violet"][index%5]}`} style={{width: size, height: size}}/><span>{value.label}</span><strong>{Math.round(value.weight)}%</strong><small>±{value.uncertainty}%</small></div>})}</div><p>This preview does not change your current value profile.</p></aside>
}
