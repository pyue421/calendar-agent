import React, { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { loadOnboardingQuestions, regenerateCurrentOnboardingQuestion } from "../services/onboarding-questions"
import "./onboarding-shared.css"
import "./onboarding-preferences.css"

const SET_SIZE = 10

export default function OnboardingPreferences() {
  const navigate = useNavigate()
  const [questions, setQuestions] = useState([])
  const [index, setIndex] = useState(0)
  const [answers, setAnswers] = useState({})
  const [selected, setSelected] = useState(null) // "A" | "B" | "none" | null
  const [loading, setLoading] = useState(true)
  const [regenerating, setRegenerating] = useState(false)
  const [loadingError, setLoadingError] = useState("")
  const [questionSource, setQuestionSource] = useState("ai")

  const current = questions[index]
  const progressPct = questions.length ? Math.round(((index + 1) / questions.length) * 100) : 0

  useEffect(() => {
    const controller = new AbortController()
    let active = true

    async function getQuestions() {
      setLoading(true)
      setLoadingError("")
      setAnswers({})
      setSelected(null)
      setIndex(0)

      try {
        const result = await loadOnboardingQuestions({
          size: SET_SIZE,
          regenSeed: 0,
          signal: controller.signal,
        })
        if (!active) return
        setQuestions(result.questions)
        setQuestionSource(result.source)
        setLoadingError(result.error || "")
      } catch (error) {
        if (error?.name === "AbortError") return
        if (!active) return
        setQuestions([])
        setQuestionSource("fallback")
        setLoadingError("Unable to load questions.")
      } finally {
        if (active) setLoading(false)
      }
    }

    getQuestions()
    return () => {
      active = false
      controller.abort()
    }
  }, [])

  function choose(option) {
    if (!current) return
    setSelected(option)
    setAnswers((prev) => ({ ...prev, [current.id]: option }))
  }

  function next() {
    if (!selected || !questions.length) return
    if (index >= questions.length - 1) {
      navigate("/home")
      return
    }
    const nextIndex = index + 1
    const nextQ = questions[nextIndex]
    setIndex(nextIndex)
    setSelected(answers[nextQ.id] ?? null)
  }

  function back() {
    if (index === 0) {
      navigate("/onboarding/mandatory")
      return
    }
    const prevIndex = index - 1
    const prevQ = questions[prevIndex]
    setIndex(prevIndex)
    setSelected(answers[prevQ.id] ?? null)
  }

  function regenerate() {
    if (!current) return
    const nextSeed = Date.now()
    setRegenerating(true)

    const excludePrompts = questions
      .filter((_, idx) => idx !== index)
      .map((q) => q.prompt)

    regenerateCurrentOnboardingQuestion({
      excludePrompts,
      regenSeed: nextSeed,
    })
      .then((result) => {
        if (!result.ok || !result.question) {
          setLoadingError(result.error || "Unable to regenerate question.")
          return
        }

        setQuestions((prev) => {
          const next = [...prev]
          next[index] = { ...result.question, id: current.id }
          return next
        })
        setSelected(null)
        setAnswers((prev) => {
          const next = { ...prev }
          delete next[current.id]
          return next
        })
        setQuestionSource(result.source || "ai")
        setLoadingError(result.error || "")
      })
      .catch(() => {
        setLoadingError("Unable to regenerate question.")
      })
      .finally(() => {
        setRegenerating(false)
      })
  }

  return (
    <div className="onb-page">
      <div className="onb-card pref-card-shell">
        <div className="onb-progress pref-progress">
          <motion.div
            className="onb-progress-bar"
            initial={false}
            animate={{ width: `${progressPct}%` }}
            transition={{ duration: 0.28, ease: "easeInOut" }}
          />
        </div>

        <div className={`pref-title${regenerating ? " pref-title-regenerating" : ""}`}>
          {loading
            ? "Generating questions..."
            : regenerating
              ? "Regenerating question..."
              : (current?.prompt || "No questions available.")}
        </div>

        {!loading && current && (
          <>
            <div className="pref-choice-grid">
              <ChoiceCard
                option="A"
                text={current.a}
                selected={selected === "A"}
                onClick={() => choose("A")}
              />
              <ChoiceCard
                option="B"
                text={current.b}
                selected={selected === "B"}
                onClick={() => choose("B")}
              />
            </div>

            <label className="pref-none">
              <input
                type="radio"
                name={`none-${current.id}`}
                checked={selected === "none"}
                onChange={() => choose("none")}
              />
              <span>No preference</span>
            </label>
          </>
        )}

        {!loading && questionSource === "fallback" && loadingError && (
          <div className="pref-note">{loadingError}. Using fallback questions.</div>
        )}

        <div className="pref-footer">
          <button className="btn btn-ghost" onClick={back}>Back</button>
          <div className="pref-footer-right">
            <button className="btn pref-regen-btn" onClick={regenerate} disabled={loading || regenerating}>
              <span className="pref-regen-icon" aria-hidden>
                <svg viewBox="0 0 24 24" className="pref-regen-icon-gemini">
                  <path d="M12 1.8c1.2 4.8 3.2 6.8 8 8.1-4.8 1.3-6.8 3.3-8 8.1-1.2-4.8-3.2-6.8-8-8.1 4.8-1.3 6.8-3.3 8-8.1z" />
                </svg>
              </span>
              Regenerate
            </button>
            <button className="btn btn-primary" onClick={next} disabled={!selected || loading || regenerating || !current}>
              {index >= questions.length - 1 ? "Finish" : "Next"}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function ChoiceCard({ option, text, selected, onClick }) {
  return (
    <button type="button" className={`pref-choice${selected ? " pref-choice-selected" : ""}`} onClick={onClick}>
      <span className="pref-choice-badge">{option}</span>
      <div className="pref-choice-text">{text}</div>
    </button>
  )
}
