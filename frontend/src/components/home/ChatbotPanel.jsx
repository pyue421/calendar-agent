import React, { useEffect, useRef, useState } from "react"
import "./chatbot.css"

const INITIAL_MESSAGES = [
  {
    id: "m1",
    role: "user",
    content: "Schedule a new meeting for me for a performance review with Sheila Jackson.",
  },
  {
    id: "m2",
    role: "assistant",
    text: "I'd be happy to create a new meeting for you! \nLet me generate the meeting details for you to review or update.",
    card: {
      title: "New meeting details",
      fields: [
        { id: "f1", label: "Title of the meeting", value: "Performance review" },
        { id: "f2", label: "Date", value: "March 27, 2026" },
        { id: "f3", label: "Time", value: "12:00 - 12:45PM" },
        { id: "f4", label: "Attendees (if any)", value: "Sheila Jackson" },
        { id: "f5", label: "Location (if any)", value: "Zoom Meeting" },
      ],
    },
  },
]

export default function ChatbotPanel() {
  const [messages, setMessages] = useState(INITIAL_MESSAGES)
  const [input, setInput] = useState("")
  const [mode, setMode] = useState("agent")
  const scrollRef = useRef(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  function sendMessage() {
    const text = input.trim()
    if (!text) return
    setMessages((msgs) => [...msgs, { id: `m${Date.now()}`, role: "user", content: text }])
    setInput("")
    setTimeout(() => {
      setMessages((msgs) => [
        ...msgs,
        { id: `m${Date.now() + 1}`, role: "assistant", text: "Got it! Let me help you with that." },
      ])
    }, 800)
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
          <span className="chatbot-header-title">Calendar Agent</span>
        </div>
        <div className="chatbot-mode-group">
          <button
            type="button"
            className={`chatbot-mode-btn${mode === "agent" ? " active" : ""}`}
            onClick={() => setMode("agent")}
            aria-label="Agent mode"
          >
            <svg viewBox="0 0 16 16" fill="none" aria-hidden>
              <rect x="2" y="5" width="12" height="9" rx="2" stroke="currentColor" strokeWidth="1.4" />
              <path d="M5 5V3.5a3 3 0 016 0V5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
              <circle cx="5.5" cy="9.5" r="1" fill="currentColor" />
              <circle cx="10.5" cy="9.5" r="1" fill="currentColor" />
              <path d="M6 12h4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
            </svg>
          </button>
          <button
            type="button"
            className={`chatbot-mode-btn${mode === "email" ? " active" : ""}`}
            onClick={() => setMode("email")}
            aria-label="Email mode"
          >
            <svg viewBox="0 0 16 16" fill="none" aria-hidden>
              <rect x="1.5" y="3.5" width="13" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.4" />
              <path d="M1.5 4l6.5 5 6.5-5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
            </svg>
          </button>
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
              {msg.text && <p className="chatbot-assistant-text">{msg.text}</p>}
              {msg.card && <MeetingCard card={msg.card} />}
            </div>
          )
        )}
      </div>

      <div className="chatbot-input-wrap">
        <div className="chatbot-input-box">
          <textarea
            className="chatbot-textarea"
            placeholder="Ask anything"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
          />
          <div className="chatbot-input-footer">
            <div />
            <button type="button" className="chatbot-send-btn" onClick={sendMessage} aria-label="Send">
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
