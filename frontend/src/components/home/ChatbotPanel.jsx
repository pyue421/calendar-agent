import React, { useEffect, useRef, useState } from "react"
import { useSession } from "../../services/SessionContext"
import { DEFAULT_VALUE_WEIGHTS } from "../../services/defaultValueWeights"
import { previewWeightsForAction } from "../../services/valuePreview"
import "./chatbot.css"

export default function ChatbotPanel() {
  const {
    currentRound,
    phase,
    loading,
    startRound,
    sendChat,
    sendCalendarAction,
    completeRound,
    submitReflection,
  } = useSession()

  // Session creation/restoration is owned entirely by SessionContext's own
  // mount effect — starting a second one here used to race it (child
  // effects fire before parent effects) and always won, silently abandoning
  // any in-progress session on every reload. See SessionContext.jsx.
  const [messages, setMessages] = useState([
    {
      id: "m_welcome",
      role: "assistant",
      text: "Welcome! I'm your calendar scheduling assistant. I'll help you manage your week. Press **Start Round** when you're ready to begin.",
    },
  ])
  const [input, setInput] = useState("")
  const [sending, setSending] = useState(false)
  const [roundActive, setRoundActive] = useState(false)
  // Whether the current round's scenario card has a confirmed decision yet.
  // Gates the "Complete Round" button — the participant must lock in
  // accept/decline/postpone before they can move on.
  const [roundDecided, setRoundDecided] = useState(false)
  const scrollRef = useRef(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  async function handleStartRound() {
    setSending(true)
    try {
      const data = await startRound()
      if (data.status === "session_complete") {
        setMessages((msgs) => [
          ...msgs,
          { id: `m_${Date.now()}`, role: "assistant", text: "All 15 rounds are complete! Thank you for participating. Your value profile has been generated." },
        ])
        setRoundActive(false)
        return
      }
      setRoundActive(true)
      // Add the scenario message, with a meeting card for the proposed event
      const card = buildScenarioCard(data.emails, data.round)
      // No proposed event this round means nothing to confirm — don't leave
      // "Complete Round" permanently disabled.
      setRoundDecided(!card)
      setMessages((msgs) => [
        ...msgs,
        {
          id: `m_round_${data.round}`,
          role: "assistant",
          text: data.message,
          meta: `Round ${data.round}/15 — ${data.phase}`,
          card,
        },
      ])
    } catch (e) {
      console.error("Failed to start round:", e)
    } finally {
      setSending(false)
    }
  }

  async function handleCompleteRound() {
    setSending(true)
    try {
      const data = await completeRound()
      setRoundActive(false)

      if (data.reflection) {
        // This is a reflection round — show the reflection prompt
        setMessages((msgs) => [
          ...msgs,
          {
            id: `m_reflect_${Date.now()}`,
            role: "assistant",
            text: data.reflection,
            meta: "Reflection",
            isReflection: true,
          },
        ])
      } else {
        setMessages((msgs) => [
          ...msgs,
          {
            id: `m_complete_${Date.now()}`,
            role: "assistant",
            text: `Round ${data.round} complete. ${data.synthesis || ""}\n\nPress **Start Round** to continue.`,
          },
        ])
      }
    } catch (e) {
      console.error("Failed to complete round:", e)
    } finally {
      setSending(false)
    }
  }

  async function sendMessage() {
    const text = input.trim()
    if (!text || sending) return
    setInput("")

    const userMsg = { id: `m_${Date.now()}`, role: "user", content: text }
    setMessages((msgs) => [...msgs, userMsg])

    setSending(true)
    try {
      const data = await sendChat(text)
      setMessages((msgs) => [
        ...msgs,
        {
          id: `m_${Date.now() + 1}`,
          role: "assistant",
          text: data.text,
          card: data.card || null,
        },
      ])
    } catch (e) {
      setMessages((msgs) => [
        ...msgs,
        { id: `m_err_${Date.now()}`, role: "assistant", text: "Sorry, something went wrong. Please try again." },
      ])
    } finally {
      setSending(false)
    }
  }

  async function handleCardDecision(msgId, card, decision, details) {
    if (!card.eventId || card.decision === decision) return
    setMessages((msgs) =>
      msgs.map((m) =>
        m.id === msgId ? { ...m, card: { ...m.card, decision } } : m
      )
    )
    setRoundDecided(true)
    try {
      await sendCalendarAction(decision, card.eventId, details)
    } catch (e) {
      console.error("Failed to record calendar action:", e)
    }
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <section className="chatbot-panel">
      <header className="chatbot-header">
        <div className="chatbot-header-left">
          <svg className="chatbot-sparkle" viewBox="0 0 16 16" fill="none" aria-hidden>
            <path
              d="M8 2v12M2 8h12M4.1 4.1l7.8 7.8M11.9 4.1l-7.8 7.8"
              stroke="#25252a"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
          <span className="chatbot-header-title">
            DISCOVER Agent
            {currentRound > 0 && (
              <span style={{ fontSize: 11, opacity: 0.6, marginLeft: 8 }}>
                Round {currentRound}/15 · {phase}
              </span>
            )}
          </span>
        </div>
      </header>

      <div className="chatbot-messages" ref={scrollRef}>
        {messages.map((msg) =>
          msg.role === "user" ? (
            <div key={msg.id} className="chatbot-msg chatbot-msg-user">
              <div className="chatbot-user-bubble">{msg.content}</div>
            </div>
          ) : (
            <div key={msg.id} className="chatbot-msg chatbot-msg-assistant">
              {msg.meta && (
                <div style={{ fontSize: 11, color: "#7c7c8a", marginBottom: 4 }}>{msg.meta}</div>
              )}
              {msg.text && <p className="chatbot-assistant-text">{msg.text}</p>}
              {msg.valuesCard && <ValueChangesCard breakdown={msg.valuesCard} />}
              {msg.card && (
                <MeetingCard
                  card={msg.card}
                  onAccept={(details) => handleCardDecision(msg.id, msg.card, "accept", details)}
                  onReject={() => handleCardDecision(msg.id, msg.card, "decline")}
                  onPostpone={() => handleCardDecision(msg.id, msg.card, "postpone")}
                  onConfirmBreakdown={(breakdown) =>
                    setMessages((msgs) => [
                      ...msgs,
                      { id: `m_breakdown_${Date.now()}`, role: "assistant", valuesCard: breakdown },
                    ])
                  }
                />
              )}
            </div>
          )
        )}
        {sending && (
          <div className="chatbot-msg chatbot-msg-assistant">
            <p className="chatbot-assistant-text" style={{ opacity: 0.5 }}>Thinking…</p>
          </div>
        )}
      </div>

      <div className="chatbot-input-wrap">
        {/* Round control buttons */}
        <div style={{ display: "flex", gap: 8, padding: "0 12px 6px", justifyContent: "center" }}>
          {!roundActive && (
            <button
              type="button"
              onClick={handleStartRound}
              disabled={sending || loading}
              style={{
                padding: "6px 16px", fontSize: 13, borderRadius: 6,
                border: "1px solid #dee5eb", background: "#f0f4ff",
                cursor: sending ? "not-allowed" : "pointer", fontWeight: 500,
              }}
            >
              {currentRound === 0 ? "Start Round 1" : `Start Round ${currentRound + 1}`}
            </button>
          )}
          {roundActive && (
            <button
              type="button"
              onClick={handleCompleteRound}
              disabled={sending || loading || !roundDecided}
              title={roundDecided ? undefined : "Confirm a decision on this round's scenario first"}
              style={{
                padding: "6px 16px", fontSize: 13, borderRadius: 6,
                border: "1px solid #dee5eb", background: "#fff4e6",
                cursor: sending || !roundDecided ? "not-allowed" : "pointer", fontWeight: 500,
                opacity: roundDecided ? 1 : 0.5,
              }}
            >
              Complete Round
            </button>
          )}
        </div>

        <div className="chatbot-input-box">
          <textarea
            className="chatbot-textarea"
            placeholder="Ask anything"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            disabled={sending}
          />
          <div className="chatbot-input-footer">
            <div />
            <button type="button" className="chatbot-send-btn" onClick={sendMessage} aria-label="Send" disabled={sending}>
              <svg viewBox="0 0 14 14" fill="none" aria-hidden>
                <path
                  d="M7 11V3M3 7l4-4 4 4"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </section>
  )
}

const WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

function buildScenarioCard(emails, roundNum) {
  const email = emails?.[0]
  const event = email?.proposed_event
  if (!email || !event) return null

  return {
    mode: "accept_reject",
    eventId: event.id,
    title: `Scenario ${roundNum}`,
    meetingTitle: event.title,
    dayIndex: event.day_index,
    start: event.start,
    end: event.end,
  }
}

function changeExplanation(action, title, label, delta) {
  const verb = { accept: "Accepting", decline: "Declining", postpone: "Postponing" }[action]
  if (delta > 0) {
    if (action === "accept")
      return `${verb} "${title}" reads as leaning into ${label} — taking this on reinforces the weight it already carries in your profile.`
    if (action === "decline")
      return `${verb} "${title}" suggests you protected ${label} over the request, so its weight rose in the estimate.`
    return `${verb} "${title}" keeps the decision open, and the estimate nudges ${label} up toward a more balanced profile.`
  }
  if (action === "accept")
    return `${verb} "${title}" pulled the estimate toward your stronger values, easing ${label} down slightly.`
  if (action === "decline")
    return `${verb} "${title}" shifted weight away from ${label} toward values that were under-represented.`
  return `${verb} "${title}" nudges ${label} down toward a more balanced profile while the decision stays open.`
}

function ValueChangesCard({ breakdown }) {
  const { action, title, items } = breakdown
  const [expandedLabel, setExpandedLabel] = useState(null)

  return (
    <div className="meeting-card">
      <div className="meeting-card-header">
        <span className="meeting-card-title">Value Changes</span>
      </div>
      <div className="meeting-card-body value-changes-body">
        {items.map((item) => {
          const delta = item.to - item.from
          const changed = delta !== 0
          const arrow = delta > 0 ? "▲" : delta < 0 ? "▼" : "•"
          const sign = delta > 0 ? `+${delta}` : delta < 0 ? `${delta}` : "±0"
          const expanded = expandedLabel === item.label
          const line = (
            <>
              <span
                className={`value-change-arrow${delta > 0 ? " up" : delta < 0 ? " down" : ""}`}
              >
                {arrow}
              </span>
              {` ${item.label}: ${item.from}% → ${item.to}% (${sign})`}
            </>
          )
          if (!changed) {
            return (
              <p key={item.label} className="value-change-line">
                {line}
              </p>
            )
          }
          return (
            <div key={item.label} className="value-change-item">
              <button
                type="button"
                className="value-change-line value-change-toggle"
                onClick={() => setExpandedLabel(expanded ? null : item.label)}
                aria-expanded={expanded}
              >
                {line}
                <span className={`value-change-chevron${expanded ? " open" : ""}`}>▸</span>
              </button>
              {expanded && (
                <p className="value-change-detail">
                  {changeExplanation(action, title, item.label, delta)}
                </p>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function MeetingCard({ card, onAccept, onReject, onPostpone, onConfirmBreakdown }) {
  if (card.mode === "accept_reject") {
    return (
      <ScenarioCard
        card={card}
        onAccept={onAccept}
        onReject={onReject}
        onPostpone={onPostpone}
        onConfirmBreakdown={onConfirmBreakdown}
      />
    )
  }
  return <ConfirmCard card={card} />
}

function ConfirmCard({ card }) {
  const [fields, setFields] = useState(card.fields)
  const [confirmed, setConfirmed] = useState(false)

  function updateField(id, value) {
    setFields((f) => f.map((field) => (field.id === id ? { ...field, value } : field)))
  }

  return (
    <div className="meeting-card">
      <div className="meeting-card-header">
        <div className="meeting-card-logo" aria-hidden>
          <svg viewBox="0 0 12 12" fill="none">
            <circle cx="6" cy="6" r="4.5" stroke="#4285F4" strokeWidth="1.5" />
          </svg>
        </div>
        <span className="meeting-card-title">{card.title}</span>
      </div>
      <div className="meeting-card-body">
        {fields.map((field) => (
          <div key={field.id} className="meeting-field">
            <label className="meeting-field-label">{field.label}</label>
            <input
              className="meeting-field-input"
              type="text"
              value={field.value}
              onChange={(e) => updateField(field.id, e.target.value)}
            />
          </div>
        ))}
        <button
          type="button"
          className={`meeting-confirm-btn${confirmed ? " confirmed" : ""}`}
          onClick={() => setConfirmed(true)}
        >
          {confirmed ? "Confirmed ✓" : "Confirm →"}
        </button>
      </div>
    </div>
  )
}

function ScenarioCard({ card, onAccept, onReject, onPostpone, onConfirmBreakdown }) {
  const [meetingTitle, setMeetingTitle] = useState(card.meetingTitle)
  const [dayIndex, setDayIndex] = useState(card.dayIndex)
  const [start, setStart] = useState(card.start)
  const [end, setEnd] = useState(card.end)
  // Action the participant is previewing but has not confirmed yet.
  const [pending, setPending] = useState(null)
  const { valueWeights, setPreviewValueWeights, setPreviewConfirmed } = useSession()

  const baselineWeights = valueWeights && valueWeights.length > 0 ? valueWeights : DEFAULT_VALUE_WEIGHTS
  const previewFor = (action) => previewWeightsForAction(baselineWeights, card.eventId, action)

  function preview(action) {
    // Only previews: pushes the estimated weights into the New Values
    // bubbles so the participant can see the effect before committing.
    // Nothing is recorded until they press Confirm.
    setPending(action)
    setPreviewValueWeights(previewFor(action))
    setPreviewConfirmed(false)
  }

  function confirmPending() {
    if (!pending) return
    if (pending === "accept") {
      onAccept({
        new_title: meetingTitle.trim() || card.meetingTitle,
        new_day_index: dayIndex,
        new_start: start,
        new_end: end,
      })
    } else if (pending === "decline") {
      onReject()
    } else {
      onPostpone()
    }
    if (onConfirmBreakdown) {
      const next = previewFor(pending)
      onConfirmBreakdown({
        action: pending,
        title: meetingTitle.trim() || card.meetingTitle,
        items: baselineWeights.map((v, i) => ({
          label: v.label,
          from: v.weight,
          to: next[i].weight,
        })),
      })
    }
    setPreviewConfirmed(true)
    setPending(null)
  }

  function actionLabel(action, idle, previewing, confirmed) {
    if (pending === action) return previewing
    if (!pending && card.decision === action) return confirmed
    return idle
  }

  function actionClass(action) {
    if (pending === action) return " previewing"
    if (!pending && card.decision === action) return ` confirmed-${action}`
    return ""
  }

  return (
    <div className="meeting-card">
      <div className="meeting-card-header">
        <span className="meeting-card-title">{card.title}</span>
      </div>
      <div className="meeting-card-body">
        <div className="meeting-field">
          <label className="meeting-field-label">Title of the meeting</label>
          <div className="meeting-input-shell meeting-input-shell-plain">
            <input
              className="meeting-field-input"
              type="text"
              value={meetingTitle}
              onChange={(e) => setMeetingTitle(e.target.value)}
            />
          </div>
        </div>
        <div className="meeting-field-row">
          <div className="meeting-field meeting-field-date">
            <label className="meeting-field-label">Date</label>
            <div className="meeting-input-shell meeting-input-shell-plain meeting-input-shell-select">
              <select
                className="meeting-field-input meeting-field-select"
                value={dayIndex}
                onChange={(e) => setDayIndex(Number(e.target.value))}
              >
                {WEEKDAY_NAMES.map((name, idx) => (
                  <option key={name} value={idx}>{name}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="meeting-field">
            <label className="meeting-field-label">Time</label>
            <div className="meeting-time-range">
              <div className="meeting-input-shell meeting-input-shell-plain meeting-time-shell">
                <input
                  className="meeting-field-input"
                  type="time"
                  value={start}
                  onChange={(e) => setStart(e.target.value)}
                />
              </div>
              <span className="meeting-time-sep">–</span>
              <div className="meeting-input-shell meeting-input-shell-plain meeting-time-shell">
                <input
                  className="meeting-field-input"
                  type="time"
                  value={end}
                  onChange={(e) => setEnd(e.target.value)}
                />
              </div>
            </div>
          </div>
        </div>

        <div className="meeting-decision-row">
          <button
            type="button"
            className={`meeting-action-btn${actionClass("decline")}`}
            onClick={() => preview("decline")}
            disabled={!!card.decision}
          >
            {actionLabel("decline", "Decline", "Declining (preview)", "Declined ✓")}
          </button>
          <button
            type="button"
            className={`meeting-action-btn${actionClass("postpone")}`}
            onClick={() => preview("postpone")}
            disabled={!!card.decision}
          >
            {actionLabel("postpone", "Postpone", "Postponing (preview)", "Postponed ✓")}
          </button>
          <button
            type="button"
            className={`meeting-action-btn${actionClass("accept")}`}
            onClick={() => preview("accept")}
            disabled={!!card.decision}
          >
            {actionLabel("accept", "Accept", "Accepting (preview)", "Accepted ✓")}
          </button>
        </div>
        {pending && (
          <div className="meeting-confirm-row">
            <button type="button" className="meeting-confirm-decision-btn" onClick={confirmPending}>
              Confirm →
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
