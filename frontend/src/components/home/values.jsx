import React, {useState} from "react"
import {createPortal} from "react-dom"
import "./values.css"

const innerSlotPositions = [
  [{top: "50%", left: "50%"}],
  [{top: "30%", left: "32%"}, {top: "66%", left: "60%"}],
  [{top: "24%", left: "30%"}, {top: "30%", left: "66%"}, {top: "68%", left: "40%"}],
  [{top: "22%", left: "30%"}, {top: "26%", left: "68%"}, {top: "62%", left: "26%"}, {top: "66%", left: "64%"}],
]

function shortLabel(text, maxWords = 3) {
  const words = text.trim().split(/\s+/)
  return words.length <= maxWords ? text : `${words.slice(0, maxWords).join(" ")}…`
}

export default function ValuesPanel({valueWeights}) {
  const [activeModal, setActiveModal] = useState(null)
  const [showInfo, setShowInfo] = useState(false)

  function openModal(index, rect) {
    setActiveModal(current => current?.index === index ? null : {index, rect})
  }

  return <section className="home-values-card">
    <header className="section-header values-header"><div><h2>Current Values</h2><button type="button" className="values-info-button" onClick={() => setShowInfo(value => !value)}>How are these bubbles calculated?</button></div></header>
    <div className="value-bubble-wrap">
      {valueWeights.length === 0 && <p className="values-empty">Your value profile will begin to appear after your first scheduling decision and reflection.</p>}
      {valueWeights.map((value, index) => <ValueBubble key={value.id} value={value} onEvidenceClick={rect => openModal(index, rect)}/>)}
    </div>
    {showInfo && <div className="values-method-note"><p>The system begins from a hidden symmetric mathematical prior; that prior is not shown as your values. Your first committed profile appears after your first action and explanation.</p><p>Decisions and explanations update a Bayesian choice model. Bubble size is the posterior expected relative scheduling priority under this model—not confidence, personality, or objective importance. Uncertainty and exact evidence are shown separately.</p></div>}
    {activeModal && createPortal(<ValueEvidenceModal value={valueWeights[activeModal.index]} anchorRect={activeModal.rect} onClose={() => setActiveModal(null)}/>, document.body)}
  </section>
}

function ValueBubble({value, onEvidenceClick}) {
  const size = 80 + value.weight * 2.1
  const shown = (value.evidence || []).slice(0, 4)
  const slots = innerSlotPositions[Math.max(shown.length - 1, 0)] || []
  const innerSize = Math.max(34, Math.round(size * 0.34))
  return <div className="value-bubble-slot">
    <div className={`value-bubble value-bubble-${value.tone}`} style={{width: `${size}px`, height: `${size}px`}}>
      {shown.map((item, index) => <button key={item.evidence_id || index} type="button" className="value-bubble-evidence" style={{...slots[index], width: `${innerSize}px`, height: `${innerSize}px`}} onClick={event => onEvidenceClick(event.currentTarget.getBoundingClientRect())}>{shortLabel(item.exact_text)}</button>)}
    </div>
    <div className="value-bubble-label">
      <span>{value.label}</span>
      <strong>{value.relative_weight.toFixed(1)}%</strong>
    </div>
  </div>
}

function ValueEvidenceModal({value, anchorRect, onClose}) {
  const items = value.evidence || []
  const modalWidth = 330, gap = 14
  const openLeft = window.innerWidth - anchorRect.right < modalWidth + gap + 20
  const left = openLeft ? anchorRect.left - modalWidth - gap : anchorRect.right + gap
  const top = Math.min(Math.max(8, anchorRect.top + anchorRect.height / 2 - 90), window.innerHeight - 220)
  return <>
    <div className="value-evidence-backdrop" onClick={onClose}/>
    <div className="value-evidence-modal" style={{top, left, width: modalWidth}}>
      <div className="value-evidence-modal-header"><p>{value.label}</p><button type="button" aria-label="Close" onClick={onClose}>×</button></div>
      <p className="value-evidence-modal-subhead">{`Estimated relative scheduling priority: ${value.relative_weight.toFixed(1)}% · 90% interval ${(value.credible_interval_90.lower * 100).toFixed(1)}–${(value.credible_interval_90.upper * 100).toFixed(1)}%`}</p>
      <div className="value-evidence-modal-list">
        {items.length === 0 && <p className="value-evidence-modal-empty">No direct evidence has been linked to this value yet.</p>}
        {items.map((item, index) => <div key={item.evidence_id || index} className="value-evidence-modal-item">
          <span className={`value-evidence-source value-evidence-source-${item.source_type}`}>{item.source_type === "conversation" ? "Conversation" : "Calendar action"}</span>
          <p className="value-evidence-modal-quote">{item.source_type === "conversation" ? `“${item.exact_text}”` : item.exact_text}</p>
          <p className="value-evidence-modal-meta">{`Round ${item.round} · ${item.event_title} · ${item.scenario_id} · ${item.source_phase}`}</p>
          <p className="value-evidence-modal-meta">{`${(item.posterior_before * 100).toFixed(1)}% → ${(item.posterior_after * 100).toFixed(1)}% (${item.posterior_delta >= 0 ? "+" : ""}${(item.posterior_delta * 100).toFixed(2)} points, ${item.direction}${item.directness ? `, ${item.directness}` : ""})`}</p>
        </div>)}
      </div>
    </div>
  </>
}
