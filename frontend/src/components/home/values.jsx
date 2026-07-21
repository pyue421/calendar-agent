import React, { useState } from "react"
import { createPortal } from "react-dom"
import { useSession } from "../../services/SessionContext"
import { valueIndexForEvent } from "../../services/valueMapping"
import "./values.css"

const WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri"]

function calendarItemsForValue(calendarEvents, valueIndex, valueCount) {
  return (calendarEvents || [])
    .filter((ev) => valueIndexForEvent(ev, valueCount) === valueIndex)
    .map((ev) => ({
      id: ev.id,
      text: ev.title,
      meta: `${WEEKDAY_NAMES[ev.day_index ?? 0] || ""} ${ev.start}–${ev.end}`,
    }))
}

export default function ValuesPanel({ valueWeights, previewWeights, previewConfirmed }) {
  const [activeModal, setActiveModal] = useState(null)
  const { calendarEvents, setFocusedValueIndex } = useSession()
  // Dim the bubbles only while the decision is still an unconfirmed preview;
  // once confirmed they render in full color with the previewed weights.
  const isPreviewing = !!previewWeights && !previewConfirmed
  const newValues = previewWeights || valueWeights

  function openModal(section, index, rect) {
    setActiveModal((cur) => {
      const next =
        cur && cur.section === section && cur.index === index ? null : { section, index, rect }
      // While a New Values popup is open, highlight that value's calendar
      // items on the calendar (everything else dims).
      setFocusedValueIndex(next && next.section === "new" ? next.index : null)
      return next
    })
  }

  function closeModal() {
    setActiveModal(null)
    setFocusedValueIndex(null)
  }

  return (
    <section className="home-values-card">
      <div className="values-section">
        <header className="section-header values-header">
          <h2>Original Values</h2>
        </header>
        <div className="value-bubble-wrap">
          {valueWeights.map((value, idx) => (
            <ValueBubble
              key={value.label}
              value={value}
              grayed
              onEvidenceClick={(rect) => openModal("original", idx, rect)}
            />
          ))}
        </div>
      </div>

      <div className="values-section">
        <header className="section-header values-header">
          <h2>New Values</h2>
          {isPreviewing && <span className="values-preview-badge">Previewing decision…</span>}
        </header>
        <div className="value-bubble-wrap">
          {newValues.map((value, idx) => (
            <ValueBubble
              key={value.label}
              value={value}
              previewing={isPreviewing}
              onEvidenceClick={(rect) => openModal("new", idx, rect)}
            />
          ))}
        </div>
      </div>

      {activeModal &&
        createPortal(
          <ValueEvidenceModal
            value={(activeModal.section === "new" ? newValues : valueWeights)[activeModal.index]}
            mode={activeModal.section}
            items={
              activeModal.section === "new"
                ? calendarItemsForValue(calendarEvents, activeModal.index, newValues.length)
                : undefined
            }
            anchorRect={activeModal.rect}
            onClose={closeModal}
          />,
          document.body
        )}
    </section>
  )
}

function ValueBubble({ value, previewing, grayed, onEvidenceClick }) {
  const size = 62 + value.weight * 1.9

  return (
    <div className="value-bubble-slot">
      <button
        type="button"
        className={`value-bubble value-bubble-${value.tone}${previewing ? " value-bubble-previewing" : ""}${grayed ? " value-bubble-grayed" : ""}`}
        style={{ width: `${size}px`, height: `${size}px` }}
        onClick={(e) => onEvidenceClick(e.currentTarget.getBoundingClientRect())}
      >
        <span className="value-bubble-text">{value.label}</span>
        <strong className="value-bubble-text">{`${value.weight}%`}</strong>
      </button>
    </div>
  )
}

function ValueEvidenceModal({ value, mode, items: itemsProp, anchorRect, onClose }) {
  const items =
    itemsProp !== undefined
      ? itemsProp.slice(0, 6)
      : ((mode === "original" ? value.evidence : value.calendarEvents) || []).slice(0, 4)
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
          {mode === "original" ? "Extracted from your conversation" : "Calendar items matched to this value"}
        </p>
        <div className="value-evidence-modal-list">
          {items.length === 0 && (
            <p className="value-evidence-modal-empty">
              {mode === "original"
                ? "No evidence recorded yet."
                : "No calendar items matched to this value yet."}
            </p>
          )}
          {items.map((item, i) => (
            <div key={item.id || i} className="value-evidence-modal-item">
              <p className="value-evidence-modal-quote">
                {mode === "original" ? `"${item.text}"` : item.text}
              </p>
              <p className="value-evidence-modal-meta">
                {item.meta !== undefined ? item.meta : `Round ${item.round}`}
              </p>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}
