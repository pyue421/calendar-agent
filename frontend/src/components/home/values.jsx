import React, { useState } from "react"
import { createPortal } from "react-dom"
import "./values.css"

const innerSlotPositions = [
  [{ top: "50%", left: "50%" }],
  [{ top: "30%", left: "32%" }, { top: "66%", left: "60%" }],
  [{ top: "24%", left: "30%" }, { top: "30%", left: "66%" }, { top: "68%", left: "40%" }],
  [
    { top: "22%", left: "30%" },
    { top: "26%", left: "68%" },
    { top: "62%", left: "26%" },
    { top: "66%", left: "64%" },
  ],
]

function shortLabel(text, maxWords = 3) {
  const words = text.trim().split(/\s+/)
  if (words.length <= maxWords) return text
  return words.slice(0, maxWords).join(" ") + "…"
}

export default function ValuesPanel({ valueWeights }) {
  const [viewMode, setViewMode] = useState("original")
  const [activeModal, setActiveModal] = useState(null)

  function openModal(index, rect) {
    setActiveModal((cur) => (cur && cur.index === index ? null : { index, rect }))
  }

  function switchMode(next) {
    setViewMode(next)
    setActiveModal(null)
  }

  return (
    <section className="home-values-card">
      <header className="section-header values-header">
        <h2>Values in Your Solution</h2>
        <div className="values-view-toggle">
          <button
            type="button"
            className={`values-view-btn${viewMode === "original" ? " active" : ""}`}
            onClick={() => switchMode("original")}
          >
            Original
          </button>
          <button
            type="button"
            className={`values-view-btn${viewMode === "new" ? " active" : ""}`}
            onClick={() => switchMode("new")}
          >
            New
          </button>
        </div>
      </header>

      <div className="value-bubble-wrap">
        {valueWeights.length === 0 && <p className="values-empty">Complete baseline calibration to create your current profile.</p>}
        {valueWeights.map((value, idx) => (
          <ValueBubble
            key={value.label}
            value={value}
            mode={viewMode}
            onEvidenceClick={(rect) => openModal(idx, rect)}
          />
        ))}
      </div>

      {activeModal &&
        createPortal(
          <ValueEvidenceModal
            value={valueWeights[activeModal.index]}
            mode={viewMode}
            anchorRect={activeModal.rect}
            onClose={() => setActiveModal(null)}
          />,
          document.body
        )}
    </section>
  )
}

function ValueBubble({ value, mode, onEvidenceClick }) {
  const size = 80 + value.weight * 2.1
  const items = (mode === "original" ? value.evidence : value.calendarEvents) || []
  const shown = items.slice(0, 4)
  const slots = innerSlotPositions[Math.max(shown.length - 1, 0)] || []
  const innerSize = Math.max(34, Math.round(size * 0.34))

  return (
    <div className="value-bubble-slot">
      <div
        className={`value-bubble value-bubble-${value.tone}`}
        style={{ width: `${size}px`, height: `${size}px` }}
      >
        {shown.map((item, i) => (
          <button
            key={item.id || i}
            type="button"
            className="value-bubble-evidence"
            style={{ ...slots[i], width: `${innerSize}px`, height: `${innerSize}px` }}
            onClick={(e) => onEvidenceClick(e.currentTarget.getBoundingClientRect())}
          >
            {shortLabel(item.text)}
          </button>
        ))}
      </div>
      <div className="value-bubble-label">
        <span>{value.label}</span>
        <strong>{`${value.weight}%`}</strong>
      </div>
    </div>
  )
}

function ValueEvidenceModal({ value, mode, anchorRect, onClose }) {
  const items = ((mode === "original" ? value.evidence : value.calendarEvents) || []).slice(0, 4)
  const modalWidth = 254
  const gap = 14
  const spaceRight = window.innerWidth - anchorRect.right
  const openLeft = spaceRight < modalWidth + gap + 20
  const left = openLeft ? anchorRect.left - modalWidth - gap : anchorRect.right + gap
  const top = Math.min(
    Math.max(8, anchorRect.top + anchorRect.height / 2 - 90),
    window.innerHeight - 220
  )

  return (
    <>
      <div className="value-evidence-backdrop" onClick={onClose} />
      <div className="value-evidence-modal" style={{ top, left, width: modalWidth }}>
        <div className="value-evidence-modal-header">
          <p>{`${value.label}: ${value.weight}%`}</p>
          <button type="button" aria-label="Close" onClick={onClose}>
            ×
          </button>
        </div>
        <p className="value-evidence-modal-subhead">
          {mode === "original" ? "Extracted from your conversation" : "Extracted from your calendar actions"}
        </p>
        <div className="value-evidence-modal-list">
          {items.length === 0 && (
            <p className="value-evidence-modal-empty">No evidence recorded yet.</p>
          )}
          {items.map((item, i) => (
            <div key={item.id || i} className="value-evidence-modal-item">
              <p className="value-evidence-modal-quote">
                {mode === "original" ? `"${item.text}"` : item.text}
              </p>
              <p className="value-evidence-modal-meta">{`Round ${item.round}`}</p>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}
