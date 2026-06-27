import React, { useState } from "react"
import "./values.css"

const bubblePositions = [
  { left: "6%", top: "10%" },
  { left: "38%", top: "2%" },
  { left: "68%", top: "5%" },
  { left: "22%", top: "50%" },
  { left: "52%", top: "54%" },
]

export default function ValuesPanel({ valueWeights }) {
  const [viewMode, setViewMode] = useState("bubble")
  const valuesByPriority = [...valueWeights].sort(
    (a, b) => b.weight - a.weight || a.label.localeCompare(b.label)
  )

  return (
    <section className="home-values-card">
      <header className="section-header values-header">
        <h2>Values in Your Solution</h2>
        <div className="values-view-toggle">
          <button
            type="button"
            className={`values-view-btn${viewMode === "bubble" ? " active" : ""}`}
            onClick={() => setViewMode("bubble")}
          >
            Bubble
          </button>
          <button
            type="button"
            className={`values-view-btn${viewMode === "list" ? " active" : ""}`}
            onClick={() => setViewMode("list")}
          >
            List
          </button>
        </div>
      </header>

      {viewMode === "bubble" ? (
        <div className="value-bubble-wrap">
          {valueWeights.map((value, idx) => (
            <ValueBubble key={value.label} value={value} index={idx} />
          ))}
        </div>
      ) : (
        <div className="values-list-wrap">
          {valuesByPriority.map((value, idx) => (
            <article key={value.label} className={`values-list-item values-list-item-${value.tone}`}>
              <span className="values-list-rank">{idx + 1}</span>
              <div className="values-list-main">
                <strong>{value.label}</strong>
                <span>{`${value.weight}%`}</span>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

function ValueBubble({ value, index }) {
  const size = 80 + value.weight * 2.1
  return (
    <div
      className={`value-bubble value-bubble-${value.tone}`}
      style={{
        left: bubblePositions[index].left,
        top: bubblePositions[index].top,
        width: `${size}px`,
        height: `${size}px`,
      }}
    >
      <span>{value.label}</span>
      <strong>{`${value.weight}%`}</strong>
    </div>
  )
}
