import React from "react"
import { useSession } from "../../services/SessionContext"
import "./values.css"

export default function ValuePreviewPanel() {
  const { preview } = useSession()
  if (!preview) return <section className="home-values-card preview-values-card"><header className="section-header"><h2>Hypothetical preview</h2></header><p className="preview-empty">Hover, focus, or select “Preview values” to compare a possible decision.</p></section>
  return <section className="home-values-card preview-values-card" aria-live="polite">
    <header className="section-header"><div><p className="reflection-eyebrow">Hypothetical preview</p><h2>{preview.action[0].toUpperCase() + preview.action.slice(1)}</h2></div></header>
    <div className="preview-bubbles">{[...preview.preview_profile].sort((a,b) => b.weight-a.weight).slice(0,5).map(value => {
      const size = 64 + value.weight * 2.1
      return <div className="preview-bubble-slot" key={value.id}><div className="value-bubble value-bubble-green" style={{width:size,height:size}} /><span>{value.label}</span><strong>{Math.round(value.weight)}%</strong><small>±{value.uncertainty}%</small></div>
    })}</div>
    <p className="preview-disclaimer">A counterfactual reflection, not a claim about your objectively true values. Your current profile remains unchanged until you commit.</p>
  </section>
}

