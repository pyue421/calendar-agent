import React, { useState } from "react"
import "./goals.css"

const INITIAL_GOALS = [
  { id: "g1", text: "Run 5K twice a week", date: "Mon May 5, 2026", dots: ["#22c55e", "#fbbf24", "#f97316"] },
  { id: "g2", text: "Run 5K twice a week", date: "Mon May 5, 2026", dots: ["#22c55e"] },
  { id: "g3", text: "Run 5K twice a week", date: "Mon May 5, 2026", dots: ["#fbbf24"] },
  { id: "g4", text: "Run 5K twice a week", date: "Mon May 5, 2026", dots: ["#f97316"] },
]

export default function GoalsPanel() {
  const [goals, setGoals] = useState(INITIAL_GOALS)
  const [newGoal, setNewGoal] = useState("")

  function addGoal() {
    const text = newGoal.trim()
    if (!text) return
    const now = new Date()
    const dateStr = now.toLocaleDateString("en-US", {
      weekday: "short",
      month: "short",
      day: "numeric",
      year: "numeric",
    })
    setGoals((g) => [...g, { id: `g${Date.now()}`, text, date: dateStr, dots: [] }])
    setNewGoal("")
  }

  function deleteGoal(id) {
    setGoals((g) => g.filter((goal) => goal.id !== id))
  }

  function toggleFlag(id) {
    setGoals((g) => g.map((goal) => (goal.id === id ? { ...goal, flagged: !goal.flagged } : goal)))
  }

  return (
    <section className="goals-panel">
      <header className="goals-header">
        <h2 className="goals-title">Goals and Objectives</h2>
      </header>

      <div className="goals-add-box">
        <input
          className="goals-input"
          type="text"
          placeholder="Add a goal/objective..."
          value={newGoal}
          onChange={(e) => setNewGoal(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addGoal()}
        />
        <div className="goals-add-actions">
          <button type="button" className="goals-add-btn" onClick={addGoal}>
            Add →
          </button>
          <button type="button" className="goals-attach-btn">
            Attach value(s)
          </button>
        </div>
      </div>

      <ul className="goals-list">
        {goals.map((goal) => (
          <li key={goal.id} className="goal-item">
            <div className="goal-item-info">
              <div className="goal-item-title-row">
                <span className="goal-item-text">{goal.text}</span>
                <div className="goal-item-dots">
                  {goal.dots.map((color, i) => (
                    <span key={i} className="goal-dot" style={{ backgroundColor: color }} />
                  ))}
                </div>
              </div>
              <span className="goal-item-date">{goal.date}</span>
            </div>
            <div className="goal-item-actions">
              <button
                type="button"
                className={`goal-flag-btn${goal.flagged ? " flagged" : ""}`}
                onClick={() => toggleFlag(goal.id)}
                aria-label="Flag goal"
              >
                <svg viewBox="0 0 15 15" fill="none" aria-hidden>
                  <path
                    d="M2.5 1.5v12M2.5 1.5h9l-3 4 3 4.5H2.5"
                    stroke="currentColor"
                    strokeWidth="1.3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
              <button
                type="button"
                className="goal-delete-btn"
                onClick={() => deleteGoal(goal.id)}
                aria-label="Delete goal"
              >
                <svg viewBox="0 0 15 15" fill="none" aria-hidden>
                  <path
                    d="M3 4h9M5 4V3h5v1M5.5 7v4M9.5 7v4M4 4l1 9h5l1-9"
                    stroke="currentColor"
                    strokeWidth="1.3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
