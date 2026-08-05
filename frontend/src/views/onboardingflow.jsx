import React, { useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import "./onboarding-shared.css"
import "./onboarding-mandatory.css"

const STORAGE_KEY = "vitl_onboarding_v1"
const DOB_FORMAT = /^\d{4}\/\d{2}\/\d{2}$/
const LOCATION_SUGGESTIONS = [
  "Waterloo, ON",
  "University of Waterloo",
  "Wilfrid Laurier University",
  "Conestoga College - Waterloo Campus",
  "Kitchener GO Station",
  "Waterloo Park",
  "Pearson International Airport",
  "Region of Waterloo International Airport",
  "Toronto, ON",
  "Mississauga, ON",
]

const defaultState = {
  step: 0,
  homeAddress: "",
  destinationAddress: "",
  dob: "",
  aviationTerm: "",
  aviationLicense: "",
  canGiveRides: null, // true | false | null
}

export default function OnboardingFlow() {
  const navigate = useNavigate()
  const [state, setState] = useState(defaultState)
  const [touched, setTouched] = useState({})

  // Restore saved progress
  useEffect(() => {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return
    try {
      const saved = JSON.parse(raw)
      const nextStep = Number.isFinite(saved?.step) ? Math.max(0, Math.min(2, saved.step)) : 0
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setState((s) => ({ ...s, ...saved, step: nextStep }))
    } catch {
      // ignore
    }
  }, [])

  const steps = useMemo(
    () => [
      { key: "journey", title: "Journey Setup", subtitle: "Tell us about your route" },
      { key: "about", title: "About You", subtitle: "Basic Personal Information" },
      {
        key: "car",
        title: "Do you have access to a car that you could use to\ngive rides occasionally?",
        subtitle: "This helps us plan your role in carpooling – Driving or Riding.",
      },
    ],
    []
  )

  const stepCount = steps.length
  const progressPct = Math.round((state.step / (stepCount - 1)) * 100)

  function saveProgress(nextPartial = {}) {
    const next = { ...state, ...nextPartial }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  }

  function setField(name, value) {
    setState((s) => ({ ...s, [name]: value }))
  }

  function markTouched(name) {
    setTouched((t) => ({ ...t, [name]: true }))
  }

  function isValidForStep(step) {
    if (step === 0) {
      return state.homeAddress.trim().length > 3 && state.destinationAddress.trim().length > 3
    }
    if (step === 1) {
      return DOB_FORMAT.test(state.dob.trim()) && state.aviationTerm.trim().length > 1 && state.aviationLicense.trim().length > 1
    }
    if (step === 2) {
      return state.canGiveRides === true || state.canGiveRides === false
    }
    return true
  }

  function next() {
    const ok = isValidForStep(state.step)
    if (!ok) {
      // mark relevant fields as touched so errors show
      if (state.step === 0) {
        markTouched("homeAddress"); markTouched("destinationAddress")
      } else if (state.step === 1) {
        markTouched("dob"); markTouched("aviationTerm"); markTouched("aviationLicense")
      } else if (state.step === 2) {
        markTouched("canGiveRides")
      }
      return
    }

    const nextStep = Math.min(stepCount - 1, state.step + 1)
    const nextState = { ...state, step: nextStep }
    setState(nextState)
    saveProgress({ step: nextStep })

    if (state.step === stepCount - 1) {
      // mandatory info complete -> go to preference cards (part 2)
      navigate("/onboarding/preferences")
    }
  }

  function back() {
    if (state.step === 0) {
      navigate("/onboarding/auth")
      return
    }
    const prev = Math.max(0, state.step - 1)
    setState((s) => ({ ...s, step: prev }))
    saveProgress({ step: prev })
  }

  const current = steps[state.step]

  return (
    <div className="onb-page">
      <div className="onb-card">
        <div className="onb-progress">
          <motion.div
            className="onb-progress-bar"
            initial={false}
            animate={{ width: `${progressPct}%` }}
            transition={{ duration: 0.2, ease: "easeInOut" }}
          />
        </div>

        {/* Header */}
        <div className="onb-header">
          <div className="onb-title">{current.title}</div>
          <div className="onb-subtitle">{current.subtitle}</div>
        </div>

        {/* Body */}
        <div className="onb-body">
          {state.step === 0 && (
            <JourneySetupScreen
              state={state}
              setField={setField}
              touched={touched}
              markTouched={markTouched}
            />
          )}

          {state.step === 1 && (
            <AboutYouScreen
              state={state}
              setField={setField}
              touched={touched}
              markTouched={markTouched}
            />
          )}

          {state.step === 2 && (
            <CarAccessScreen
              state={state}
              setField={setField}
              touched={touched}
              markTouched={markTouched}
            />
          )}
        </div>

        {/* Footer buttons */}
        <div className="onb-footer">
          <button className="btn btn-ghost" onClick={back}>
            Back
          </button>

          <div className="onb-footer-right">
            <button className="btn btn-primary" onClick={next}>
              {state.step === stepCount - 1 ? "Next section" : "Next"}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

/* -------------------- Step Screens -------------------- */

function Field({ icon, label, value, onChange, onBlur, placeholder, error, listId }) {
  return (
    <div className="field">
      <div className="field-label">
        <span className="field-icon" aria-hidden>{icon}</span>
        <span>{label}</span>
      </div>
      <input
        className={"input" + (error ? " input-error" : "")}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onBlur}
        placeholder={placeholder}
        list={listId}
      />
      {error ? <div className="field-error">{error}</div> : null}
    </div>
  )
}

function JourneySetupScreen({ state, setField, touched, markTouched }) {
  const homeErr =
    touched.homeAddress && state.homeAddress.trim().length <= 3 ? "Enter a home address." : ""
  const destErr =
    touched.destinationAddress && state.destinationAddress.trim().length <= 3 ? "Enter a destination address." : ""

  return (
    <div className="onb-section">
      <Field
        icon={<MapPinIcon />}
        label="Home Address"
        value={state.homeAddress}
        onChange={(v) => setField("homeAddress", v)}
        onBlur={() => markTouched("homeAddress")}
        placeholder=""
        error={homeErr}
        listId="onb-location-suggestions"
      />
      <Field
        icon={<MapPinIcon />}
        label="Destination Address"
        value={state.destinationAddress}
        onChange={(v) => setField("destinationAddress", v)}
        onBlur={() => markTouched("destinationAddress")}
        placeholder=""
        error={destErr}
        listId="onb-location-suggestions"
      />
      <datalist id="onb-location-suggestions">
        {LOCATION_SUGGESTIONS.map((location) => (
          <option key={location} value={location} />
        ))}
      </datalist>
    </div>
  )
}

function MapPinIcon() {
  return (
    <svg viewBox="0 0 32 32" className="field-icon-svg" aria-hidden>
      <path
        d="M12 14a4 4 0 1 0 8 0a4 4 0 0 0 -8 0"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M23.543 21.543l-5.657 5.657a2.667 2.667 0 0 1 -3.771 0l-5.658 -5.657a10.667 10.667 0 1 1 15.086 0z"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function CalendarIcon() {
  return (
    <svg viewBox="0 0 24 24" className="field-icon-svg" aria-hidden>
      <path d="M4 7a2 2 0 0 1 2 -2h12a2 2 0 0 1 2 2v11a2 2 0 0 1 -2 2h-12a2 2 0 0 1 -2 -2z" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M16 3v4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <path d="M8 3v4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <path d="M4 11h16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}

function PlaneDepartureIcon() {
  return (
    <svg viewBox="0 0 24 24" className="field-icon-svg" aria-hidden>
      <path d="M2.5 19h19" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <path d="M3 14l7.5 2l2 5l2.5 -3l3.5 1.2a1.2 1.2 0 0 0 1.4 -1.7l-1.5 -3.2l3.1 -2.5a1.2 1.2 0 0 0 -1 -2.1l-3.7 .5l-3.2 -4.1a1.2 1.2 0 0 0 -2.1 .9l.1 4.1l-6.4 2.7a1.2 1.2 0 0 0 .3 2.2z" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function SchoolIcon() {
  return (
    <svg viewBox="0 0 24 24" className="field-icon-svg" aria-hidden>
      <path d="M3 10l9 -4l9 4l-9 4z" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M7 12v4a5 3 0 0 0 10 0v-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M21 10v4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}

function AboutYouScreen({ state, setField, touched, markTouched }) {
  const dobErr = touched.dob && !DOB_FORMAT.test(state.dob.trim()) ? "Use format YYYY/MM/DD." : ""
  const termErr =
    touched.aviationTerm && state.aviationTerm.trim().length <= 1 ? "Enter your current aviation term." : ""
  const licErr =
    touched.aviationLicense && state.aviationLicense.trim().length <= 1 ? "Enter your aviation licence." : ""

  return (
    <div className="onb-section">
      <div className="field">
        <div className="field-label">
          <span className="field-icon" aria-hidden><CalendarIcon /></span>
          <span>Date of Birth</span>
        </div>
        <input
          className={"input" + (dobErr ? " input-error" : "")}
          type="text"
          value={formatDobInput(state.dob)}
          onChange={(e) => setField("dob", formatDobInput(e.target.value))}
          onBlur={() => markTouched("dob")}
          placeholder="____/__/__"
          inputMode="numeric"
          maxLength={10}
        />
        {dobErr ? <div className="field-error">{dobErr}</div> : null}
      </div>

      <div className="field">
        <div className="field-label">
          <span className="field-icon" aria-hidden><PlaneDepartureIcon /></span>
          <span>Current Aviation Term</span>
        </div>
        <select
          className={"input input-select" + (termErr ? " input-error" : "")}
          value={state.aviationTerm}
          onChange={(e) => setField("aviationTerm", e.target.value)}
          onBlur={() => markTouched("aviationTerm")}
        >
          <option value="">Select term</option>
          <option value="2A">2A</option>
          <option value="2B">2B</option>
          <option value="3A">3A</option>
          <option value="3B">3B</option>
        </select>
        {termErr ? <div className="field-error">{termErr}</div> : null}
      </div>

      <div className="field">
        <div className="field-label">
          <span className="field-icon" aria-hidden><SchoolIcon /></span>
          <span>Aviation License</span>
        </div>
        <select
          className={"input input-select" + (licErr ? " input-error" : "")}
          value={state.aviationLicense}
          onChange={(e) => setField("aviationLicense", e.target.value)}
          onBlur={() => markTouched("aviationLicense")}
        >
          <option value="">Select license</option>
          <option value="None">None</option>
          <option value="Student Pilot Permit">Student Pilot Permit</option>
          <option value="PPL">PPL</option>
          <option value="CPL">CPL</option>
          <option value="ATPL">ATPL</option>
        </select>
        {licErr ? <div className="field-error">{licErr}</div> : null}
      </div>
    </div>
  )
}

function formatDobInput(value) {
  const digits = String(value || "").replace(/\D/g, "").slice(0, 8)
  const y = digits.slice(0, 4)
  const m = digits.slice(4, 6)
  const d = digits.slice(6, 8)
  if (digits.length <= 4) return y
  if (digits.length <= 6) return `${y}/${m}`
  return `${y}/${m}/${d}`
}

function CarAccessScreen({ state, setField, touched, markTouched }) {
  const showErr = touched.canGiveRides && state.canGiveRides == null
  return (
    <div className="onb-section">
      <div className="choice-grid">
        <ChoiceCard
          selected={state.canGiveRides === true}
          icon="🚗"
          title="Yes, I can give rides"
          onClick={() => { setField("canGiveRides", true); markTouched("canGiveRides") }}
        />
        <ChoiceCard
          selected={state.canGiveRides === false}
          icon="👥"
          title="No, I’ll need a ride"
          onClick={() => { setField("canGiveRides", false); markTouched("canGiveRides") }}
        />
      </div>
      {showErr ? <div className="field-error" style={{ marginTop: 10 }}>Please choose one option.</div> : null}
    </div>
  )
}

function ChoiceCard({ selected, icon, title, onClick }) {
  return (
    <button
      type="button"
      className={"choice-card" + (selected ? " choice-selected" : "")}
      onClick={onClick}
    >
      <div className="choice-icon">{icon}</div>
      <div className="choice-title">{title}</div>
    </button>
  )
}
