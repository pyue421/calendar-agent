import React, {useState} from "react"
import {createPortal} from "react-dom"
import {useSession} from "../../services/SessionContext"
import "./values.css"

export default function ValuesPanel() {
  const {valueWeights = [], previewValueWeights, previewLoading} = useSession()
  const [activeValueId, setActiveValueId] = useState(null)
  const [showInfo, setShowInfo] = useState(false)
  const displayedProfile = previewValueWeights || valueWeights
  const committedValue = valueWeights.find(value => value.id === activeValueId)
  const previewing = previewLoading || Boolean(previewValueWeights)

  return <section className="home-values-card" aria-label="Value Profile">
    <header className="section-header values-header">
      <div><h2>Value Profile</h2><button type="button" className="values-info-button" onClick={() => setShowInfo(value => !value)}>How are these bubbles calculated?</button></div>
      {previewing && <span className="values-preview-state">Previewing…</span>}
    </header>
    <div className="value-bubble-wrap">
      {displayedProfile.length === 0 && <p className="values-empty">Your value profile will begin to appear after your first scheduling decision and reflection.</p>}
      {displayedProfile.map(value => <ValueBubble key={value.id} value={value} onClick={() => setActiveValueId(value.id)}/>)}
    </div>
    {showInfo && <div className="values-method-note"><p>The system begins from a hidden symmetric mathematical prior; that prior is not shown as your values. Your first committed profile appears after your first action and explanation.</p><p>Decisions and explanations update a Bayesian choice model. Relative bubble size represents the model’s current estimate, not confidence, personality, or objective importance.</p></div>}
    {activeValueId && createPortal(<ValueEvidenceModal value={committedValue} onClose={() => setActiveValueId(null)}/>, document.body)}
  </section>
}

function ValueBubble({value, onClick}) {
  const size = 62 + value.weight * 1.9
  return <button type="button" className={`value-bubble value-bubble-${value.tone}`} style={{width: `${size}px`, height: `${size}px`}} onClick={onClick} aria-label={`View evidence for ${value.label}`}>
    <span>{value.label}</span>
  </button>
}

function ValueEvidenceModal({value, onClose}) {
  const items = value?.evidence || []
  return <>
    <div className="value-evidence-backdrop" onClick={onClose}/>
    <div className="value-evidence-modal" role="dialog" aria-modal="true" aria-label={`${value?.label || "Value"} evidence`}>
      <div className="value-evidence-modal-header"><p>{value?.label || "Value evidence"}</p><button type="button" aria-label="Close" onClick={onClose}>×</button></div>
      {value?.description && <p className="value-evidence-modal-definition">{value.description}</p>}
      <div className="value-evidence-modal-list">
        {items.length === 0 && <p className="value-evidence-modal-empty">No direct evidence has been linked to this value yet.</p>}
        {items.map((item, index) => <div key={item.evidence_id || index} className="value-evidence-modal-item">
          <span className={`value-evidence-source value-evidence-source-${item.source_type}`}>{item.source_type === "conversation" ? "Conversation" : "Calendar action"}</span>
          <p className="value-evidence-modal-quote">{item.exact_text}</p>
          <p className="value-evidence-modal-meta">{[`Round ${item.round}`, item.event_title, item.source_phase, item.directness].filter(Boolean).join(" · ")}</p>
        </div>)}
      </div>
    </div>
  </>
}
