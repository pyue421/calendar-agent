import React, { useEffect, useMemo, useRef, useState } from "react"
import "./calendar.css"

const ROW_HEIGHT = 64
const HOURS = Array.from({ length: 24 }, (_, idx) => idx)
const WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri"]

const INITIAL_EVENTS = [
  { id: "e1", title: "Team Meeting", dayIndex: 0, start: "09:00", end: "10:30", tone: "purple" },
  { id: "e2", title: "Aviation Practice", dayIndex: 1, start: "11:00", end: "12:30", tone: "blue" },
  { id: "e3", title: "Activity", dayIndex: 2, start: "12:00", end: "13:30", tone: "purple" },
  { id: "e4", title: "Aviation Practice", dayIndex: 4, start: "09:00", end: "10:30", tone: "blue" },
]

export default function CalendarPanel() {
  const [weekOffset, setWeekOffset] = useState(0)
  const [events, setEvents] = useState(INITIAL_EVENTS)
  const [dragging, setDragging] = useState(null)
  const scrollerRef = useRef(null)
  const daysColumnsRef = useRef(null)
  const ghostRef = useRef(null)

  const weekStart = useMemo(() => {
    const base = startOfWeekMonday(new Date())
    return addDays(base, weekOffset * 7)
  }, [weekOffset])

  const visibleDays = useMemo(
    () => WEEKDAY_NAMES.map((name, index) => ({ name, date: addDays(weekStart, index) })),
    [weekStart]
  )

  useEffect(() => {
    if (scrollerRef.current) {
      scrollerRef.current.scrollTop = 8 * ROW_HEIGHT
    }
  }, [])

  useEffect(() => {
    if (!dragging) return

    function onMouseMove(e) {
      if (ghostRef.current) {
        ghostRef.current.style.left = `${e.clientX - 60}px`
        ghostRef.current.style.top = `${e.clientY - dragging.offsetY}px`
      }
    }

    function onMouseUp(e) {
      if (daysColumnsRef.current && scrollerRef.current) {
        const colsRect = daysColumnsRef.current.getBoundingClientRect()
        const scrollTop = scrollerRef.current.scrollTop
        const relX = e.clientX - colsRect.left
        const relY = e.clientY - colsRect.top + scrollTop - dragging.offsetY
        const colWidth = colsRect.width / 5
        const dayIndex = Math.max(0, Math.min(4, Math.floor(relX / colWidth)))
        const rawStartMinute = Math.round((relY / ROW_HEIGHT) * 60)
        const startMinute = Math.max(0, Math.round(rawStartMinute / 15) * 15)
        const duration = toMinutes(dragging.event.end) - toMinutes(dragging.event.start)
        const endMinute = Math.min(startMinute + duration, 24 * 60)
        setEvents((evs) =>
          evs.map((ev) =>
            ev.id === dragging.event.id
              ? { ...ev, dayIndex, start: minutesToTime(startMinute), end: minutesToTime(endMinute) }
              : ev
          )
        )
      }
      setDragging(null)
    }

    document.body.style.userSelect = "none"
    document.body.style.cursor = "grabbing"
    window.addEventListener("mousemove", onMouseMove)
    window.addEventListener("mouseup", onMouseUp)
    return () => {
      document.body.style.userSelect = ""
      document.body.style.cursor = ""
      window.removeEventListener("mousemove", onMouseMove)
      window.removeEventListener("mouseup", onMouseUp)
    }
  }, [dragging])

  function onEventMouseDown(e, calEvent) {
    e.stopPropagation()
    e.preventDefault()
    const rect = e.currentTarget.getBoundingClientRect()
    const offsetY = e.clientY - rect.top
    setDragging({ event: calEvent, offsetY })
  }

  function goToday() {
    setWeekOffset(0)
    if (scrollerRef.current) {
      scrollerRef.current.scrollTop = 8 * ROW_HEIGHT
    }
  }

  const draggingDuration = dragging
    ? toMinutes(dragging.event.end) - toMinutes(dragging.event.start)
    : 0

  return (
    <>
      {dragging && (
        <div
          ref={ghostRef}
          className={`calendar-event-card calendar-event-${dragging.event.tone} calendar-drag-ghost`}
          style={{
            position: "fixed",
            left: "-9999px",
            top: "-9999px",
            width: "140px",
            height: `${(draggingDuration / 60) * ROW_HEIGHT}px`,
            zIndex: 9999,
            pointerEvents: "none",
            opacity: 0.85,
          }}
        >
          <strong>{dragging.event.title}</strong>
          <span>{formatEventTime(dragging.event.start, dragging.event.end)}</span>
        </div>
      )}

      <section className="home-calendar-card">
        <header className="calendar-topbar">
          <div className="calendar-top-left">
            <div className="calendar-week-nav">
              <button
                type="button"
                className="calendar-arrow"
                onClick={() => setWeekOffset((w) => w - 1)}
                aria-label="Previous week"
              >
                <svg viewBox="0 0 24 24" className="calendar-chevron-icon" aria-hidden>
                  <path d="M15 5L8 12L15 19" />
                </svg>
              </button>
              <div className="calendar-week-label">{formatWeekRange(weekStart)}</div>
              <button
                type="button"
                className="calendar-arrow"
                onClick={() => setWeekOffset((w) => w + 1)}
                aria-label="Next week"
              >
                <svg viewBox="0 0 24 24" className="calendar-chevron-icon" aria-hidden>
                  <path d="M9 5L16 12L9 19" />
                </svg>
              </button>
            </div>
          </div>

          <h2 className="calendar-title">My Calendar</h2>

          <button type="button" className="today-pill calendar-today" onClick={goToday}>
            Today
          </button>
        </header>

        <div className="calendar-days-header">
          <div className="calendar-time-head" />
          {visibleDays.map((day) => {
            const isToday = isSameDate(day.date, new Date())
            return (
              <div key={day.name} className={`calendar-day-header-cell${isToday ? " is-today" : ""}`}>
                <span>{day.name}</span>
                <strong>{day.date.getDate()}</strong>
              </div>
            )
          })}
        </div>

        <div className="calendar-scroll" ref={scrollerRef}>
          <div className="calendar-scroll-body" style={{ height: `${ROW_HEIGHT * HOURS.length}px` }}>
            <div className="calendar-time-column">
              {HOURS.map((hour) => (
                <div key={hour} className="calendar-time-label" style={{ height: `${ROW_HEIGHT}px` }}>
                  {formatHour(hour)}
                </div>
              ))}
            </div>

            <div className="calendar-days-columns" ref={daysColumnsRef}>
              {visibleDays.map((day, dayIndex) => (
                <div key={`${day.name}-${day.date.toDateString()}`} className="calendar-day-column">
                  {HOURS.map((hour) => (
                    <div key={hour} className="calendar-grid-line" style={{ height: `${ROW_HEIGHT}px` }} />
                  ))}

                  {events
                    .filter(
                      (event) =>
                        event.dayIndex === dayIndex &&
                        !(dragging && dragging.event.id === event.id)
                    )
                    .map((event) => {
                      const startMinutes = toMinutes(event.start)
                      const endMinutes = toMinutes(event.end)
                      const duration = endMinutes - startMinutes
                      return (
                        <article
                          key={event.id}
                          className={`calendar-event-card calendar-event-${event.tone}`}
                          style={{
                            top: `${(startMinutes / 60) * ROW_HEIGHT}px`,
                            height: `${(duration / 60) * ROW_HEIGHT}px`,
                            cursor: "grab",
                          }}
                          onMouseDown={(e) => onEventMouseDown(e, event)}
                        >
                          <strong>{event.title}</strong>
                          <span>{formatEventTime(event.start, event.end)}</span>
                        </article>
                      )
                    })}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>
    </>
  )
}

function minutesToTime(minutes) {
  const hh = Math.floor(minutes / 60)
  const mm = minutes % 60
  return `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`
}

function startOfWeekMonday(date) {
  const base = new Date(date)
  base.setHours(0, 0, 0, 0)
  const day = base.getDay()
  const diff = day === 0 ? -6 : 1 - day
  base.setDate(base.getDate() + diff)
  return base
}

function addDays(date, days) {
  const next = new Date(date)
  next.setDate(next.getDate() + days)
  return next
}

function formatWeekRange(weekStart) {
  const weekEnd = addDays(weekStart, 6)
  const firstMonth = weekStart.toLocaleString("en-US", { month: "short" })
  const secondMonth = weekEnd.toLocaleString("en-US", { month: "short" })
  if (firstMonth === secondMonth) {
    return `${firstMonth} ${weekStart.getDate()}-${weekEnd.getDate()}`
  }
  return `${firstMonth} ${weekStart.getDate()}-${secondMonth} ${weekEnd.getDate()}`
}

function toMinutes(timeString) {
  const [hh, mm] = timeString.split(":").map(Number)
  return hh * 60 + mm
}

function formatHour(hour24) {
  if (hour24 === 0) return "12 AM"
  if (hour24 < 12) return `${hour24} AM`
  if (hour24 === 12) return "12 PM"
  return `${hour24 - 12} PM`
}

function formatEventTime(start, end) {
  return `${toDisplayTime(start)} - ${toDisplayTime(end)}`
}

function toDisplayTime(hhmm) {
  const [hh, mm] = hhmm.split(":").map(Number)
  const suffix = hh >= 12 ? "PM" : "AM"
  const hour12 = hh % 12 === 0 ? 12 : hh % 12
  return `${hour12}:${String(mm).padStart(2, "0")} ${suffix}`
}

function isSameDate(a, b) {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  )
}
