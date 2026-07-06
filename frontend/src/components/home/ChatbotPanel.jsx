import React, { useEffect, useRef, useState } from "react"
import { useSession } from "../../services/SessionContext"
import "./chatbot.css"

export default function ChatbotPanel() {
  const {
    sessionId,
    currentRound,
    phase,
    loading,
    createSession,
    startRound,
    sendChat,
    completeRound,
    submitReflection,
  } = useSession()

  const [messages, setMessages] = useState([])
  const [input, setInput] = useState("")
  const [sending, setSending] = useState(false)
  const [roundActive, setRoundActive] = useState(false)
  const scrollRef = useRef(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  // Initialize session on mount
  useEffect(() => {
    if (!sessionId) {
      initSession()
    }
  }, [])

  async function initSession() {
    try {
      await createSession("participant_" + Date.now())
      setMessages([
        {
          id: "m_welcome",
          role: "assistant",
          text: "Welcome! I'm your calendar scheduling assistant. I'll help you manage your week. Press **Start Round** when you're ready to begin.",
        },
      ])
    } catch (e) {
      console.error("Failed to create session:", e)
      setMessages([
        { id: "m_error", role: "assistant", text: "Failed to connect to the server. Make sure the backend is running on port 8000." },
      ])
    }
  }

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
      // Add the scenario message
      setMessages((msgs) => [
        ...msgs,
        {
          id: `m_round_${data.round}`,
          role: "assistant",
          text: data.message,
          meta: `Round ${data.round}/15 — ${data.phase}`,
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
              {msg.card && <MeetingCard card={msg.card} />}
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
              disabled={sending || loading}
              style={{
                padding: "6px 16px", fontSize: 13, borderRadius: 6,
                border: "1px solid #dee5eb", background: "#fff4e6",
                cursor: sending ? "not-allowed" : "pointer", fontWeight: 500,
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

function MeetingCard({ card }) {
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
