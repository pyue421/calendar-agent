import React, {useEffect, useRef, useState} from "react"
import {createPortal} from "react-dom"
import {useSession} from "../../services/SessionContext"
import {bubbleSize} from "../../services/valueProfile"
import ValueChangesCard from "./ValueChangesCard"
import "./values.css"

export default function ValuesPanel() {
  const {valueWeights = [], previewValueWeights, previewLoading, activePreviewTransition,
    latestActionTransition, latestRoundTransition, profile_source, profile_stage, profile_version,
    initial_profile_version, initial_profile_displayed, current_round, logInitialProfileViewed, logProfileInteraction} = useSession()
  const [activeValueId, setActiveValueId] = useState(null)
  const [showInfo, setShowInfo] = useState(false)
  const displayedProfile = previewValueWeights || valueWeights
  const committedValue = valueWeights.find(value => value.id === activeValueId)
  const previewing = previewLoading || Boolean(previewValueWeights)
  const exposureLogged = useRef(false)
  useEffect(() => {
    if (exposureLogged.current || initial_profile_displayed || profile_source !== "onboarding_conversation" ||
        valueWeights.length !== 5 || !initial_profile_version) return
    exposureLogged.current = true
    logInitialProfileViewed(initial_profile_version).catch(() => { exposureLogged.current = false })
  }, [initial_profile_displayed, initial_profile_version, logInitialProfileViewed, profile_source, valueWeights.length])
  function interaction(event_type, value_id) {
    logProfileInteraction({event_type, value_id, profile_version, profile_stage, round: current_round,
      source_phase: profile_stage === "conversation_initial" ? "onboarding" : "calendar"}).catch(() => {})
  }
  function openValue(value) {
    setActiveValueId(value.id); interaction("value_bubble_opened", value.id)
    interaction("value_evidence_opened", value.id)
  }
  function closeValue() {
    if (activeValueId) interaction("value_modal_closed", activeValueId)
    setActiveValueId(null)
  }

  return <section className="home-values-card" aria-label="Value Profile">
    <header className="section-header values-header">
      <div><h2>{profile_stage === "conversation_initial" ? "Initial scheduling priorities" : "Current scheduling priorities"}</h2><button type="button" className="values-info-button" onClick={() => setShowInfo(value => !value)}>How are these bubbles calculated?</button></div>
      {previewing && <span className="values-preview-state">Previewing…</span>}
    </header>
    <div className="value-bubble-wrap">
      {displayedProfile.length === 0 && <p className="values-empty">Your value profile will appear after conversational onboarding or your first scheduling decision and reflection.</p>}
      {profile_stage === "conversation_initial" && <p className="values-initial-explanation">Based on what you shared, this is the model’s preliminary interpretation of the priorities that may influence how you organize your time. It may change as you make scheduling decisions and explain your reasoning.</p>}
      {displayedProfile.map(value => <ValueBubble key={value.id} value={value} onClick={() => openValue(value)}/>)}
    </div>
    <ValueChangesCard transition={activePreviewTransition || latestRoundTransition || latestActionTransition}/>
    {showInfo && <div className="values-method-note"><p>The first profile may be initialized from reviewed conversational scheduling evidence. If conversational personalization is skipped, the symmetric mathematical prior remains hidden until a scheduling decision and reflection.</p><p>Decisions and explanations continue to update the Bayesian choice model. Relative bubble size represents the model’s current estimate, not confidence, personality, or objective importance.</p></div>}
    {activeValueId && createPortal(<ValueEvidenceModal value={committedValue} onClose={closeValue}/>, document.body)}
  </section>
}

function ValueBubble({value, onClick}) {
  const size = bubbleSize(value.weight)
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
