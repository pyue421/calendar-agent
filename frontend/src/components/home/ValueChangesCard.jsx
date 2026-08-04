import React, {useState} from "react"
import "./chatbot.css"

const TITLES = {preview: "Hypothetical changes", action_commit: "Changes after your decision",
  rationale: "Changes after your reflection", round_complete: "Changes this round"}

export default function ValueChangesCard({transition, title}) {
  const [expandedId, setExpandedId] = useState(null)
  if (!transition?.display_allowed || transition.changes?.length !== 5) return null
  return <div className="meeting-card value-changes-card">
    <div className="meeting-card-header"><span className="meeting-card-title">{title || TITLES[transition.stage] || "Change in estimated scheduling priority"}</span>{transition.hypothetical && <span className="value-change-preview-label">Preview — not committed</span>}</div>
    <div className="meeting-card-body value-changes-body">{transition.changes.map(change => {
      const expanded = expandedId === change.value_id
      const symbol = change.direction === "increase" ? "▲" : change.direction === "decrease" ? "▼" : "•"
      const accessible = change.direction === "increase" ? "Estimated increase" : change.direction === "decrease" ? "Estimated decrease" : "No meaningful estimated change"
      const amount = change.direction === "negligible" ? "No meaningful change" : `${change.delta_percentage_points > 0 ? "+" : "−"}${Math.abs(change.delta_percentage_points).toFixed(1)} points`
      return <div className="value-change-item" key={change.value_id}><button type="button" className="value-change-line value-change-toggle" onClick={() => setExpandedId(expanded ? null : change.value_id)} aria-expanded={expanded}>
        <span className={`value-change-arrow ${change.direction}`} aria-label={accessible}>{symbol}</span><span>{change.display_label}: {amount}</span><span className={`value-change-chevron${expanded ? " open" : ""}`}>▸</span>
      </button>{expanded && <div className="value-change-detail"><p>{change.full_label}</p><p>Estimated relative scheduling priority: {(change.before * 100).toFixed(1)} → {(change.after * 100).toFixed(1)}</p><p>{transition.hypothetical ? "Hypothetical preview" : "Committed model update"}</p></div>}</div>
    })}</div>
  </div>
}
