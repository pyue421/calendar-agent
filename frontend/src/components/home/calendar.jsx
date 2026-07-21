import React, { useEffect, useMemo, useRef, useState } from "react"
import { createPortal } from "react-dom"
import { useSession } from "../../services/SessionContext"
import "./calendar.css"
import "./chatbot.css" // shared meeting-field/button styles for the event detail modal

const ROW_HEIGHT = 64
const HOURS = Array.from({ length: 24 }, (_, idx) => idx)
const WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri"]

// Map backend snake_case event to frontend camelCase
function mapEvent(ev) {
  const isoStart = ev.start?.includes("T") ? new Date(ev.start) : null
  const isoEnd = ev.end?.includes("T") ? new Date(ev.end) : null
  return {
    id: ev.id,
    title: ev.title,
    dayIndex: ev.day_index ?? ev.dayIndex ?? (isoStart ? Math.max(0, Math.min(4, (isoStart.getDay() + 6) % 7)) : 0),
    start: isoStart ? isoStart.toTimeString().slice(0, 5) : ev.start,
    end: isoEnd ? isoEnd.toTimeString().slice(0, 5) : ev.end,
    tone: ev.temporary ? "amber" : (ev.tone || "blue"),
    category: ev.category || "work",
    isNew: ev.is_new ?? ev.isNew ?? false,
    metadata: ev.metadata || {},
  }
}

export default function CalendarPanel() {
  const { calendarEvents, candidateEvent, sendCalendarAction } = useSession()

  const [weekOffset, setWeekOffset] = useState(0)
  const [events, setEvents] = useState([])
  const [dragging, setDragging] = useState(null)
  const [dragPreview, setDragPreview] = useState(null)
  const [selectedEvent, setSelectedEvent] = useState(null)
  const scrollerRef = useRef(null)
  const daysColumnsRef = useRef(null)
  const dragPreviewRef = useRef(null)
  const movedRef = useRef(false)
  const downPosRef = useRef({ x: 0, y: 0 })

  // Sync events from session context
  useEffect(() => {
    // Calendar interactions keep a local working copy; context changes are its external reset signal.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setEvents([...(calendarEvents || []), ...(candidateEvent ? [candidateEvent] : [])].map(mapEvent))
  }, [calendarEvents, candidateEvent])

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

    const duration = toMinutes(dragging.event.end) - toMinutes(dragging.event.start)

    function computeSnappedSlot(e) {
      if (!daysColumnsRef.current) return null
      const colsRect = daysColumnsRef.current.getBoundingClientRect()
      // colsRect.top is live viewport-relative and already reflects the
      // current scroll position of .calendar-scroll, so no extra scrollTop
      // adjustment is needed here.
      const relX = e.clientX - colsRect.left
      const relY = e.clientY - colsRect.top - dragging.offsetY
      const colWidth = colsRect.width / 5
      const dayIndex = Math.max(0, Math.min(4, Math.floor(relX / colWidth)))
      const rawStartMinute = Math.round((relY / ROW_HEIGHT) * 60)
      // Snap to the nearest 15-minute mark, like Google Calendar
      let startMinute = Math.round(rawStartMinute / 15) * 15
      startMinute = Math.max(0, Math.min(startMinute, 24 * 60 - duration))
      const endMinute = startMinute + duration
      return { dayIndex, startMinute, endMinute }
    }

    const CLICK_MOVE_THRESHOLD = 4 // px — below this, treat mouseup as a click, not a drag

    function onMouseMove(e) {
      if (
        !movedRef.current &&
        (Math.abs(e.clientX - downPosRef.current.x) > CLICK_MOVE_THRESHOLD ||
          Math.abs(e.clientY - downPosRef.current.y) > CLICK_MOVE_THRESHOLD)
      ) {
        movedRef.current = true
      }
      const slot = computeSnappedSlot(e)
      if (slot) {
        dragPreviewRef.current = slot
        setDragPreview(slot)
      }
    }

    function onMouseUp(e) {
      if (!movedRef.current) {
        // Treated as a click, not a drag — toggle the event detail modal
        const clicked = dragging.event
        setSelectedEvent((cur) =>
          cur && cur.event.id === clicked.id ? null : { event: clicked, rect: dragging.rect }
        )
        dragPreviewRef.current = null
        setDragPreview(null)
        setDragging(null)
        return
      }

      const slot = computeSnappedSlot(e) || dragPreviewRef.current
      if (slot) {
        const newStart = minutesToTime(slot.startMinute)
        const newEnd = minutesToTime(slot.endMinute)
        const oldEvent = dragging.event

        // Update local state immediately
        setEvents((evs) =>
          evs.map((ev) =>
            ev.id === oldEvent.id
              ? { ...ev, dayIndex: slot.dayIndex, start: newStart, end: newEnd }
              : ev
          )
        )

        // Log behavioral signal to backend
        if (sendCalendarAction) {
          sendCalendarAction("reschedule", oldEvent.id, {
            original_day: oldEvent.dayIndex,
            original_start: oldEvent.start,
            original_end: oldEvent.end,
            new_day_index: slot.dayIndex,
            new_start: newStart,
            new_end: newEnd,
          }).catch((err) => console.error("Failed to log calendar action:", err))
        }
      }
      dragPreviewRef.current = null
      setDragPreview(null)
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
  }, [dragging, sendCalendarAction])

  function onEventMouseDown(e, calEvent) {
    e.stopPropagation()
    e.preventDefault()
    const rect = e.currentTarget.getBoundingClientRect()
    const offsetY = e.clientY - rect.top
    movedRef.current = false
    downPosRef.current = { x: e.clientX, y: e.clientY }
    setDragging({ event: calEvent, offsetY, rect })
  }

  function handleRemoveEvent(event) {
    setEvents((evs) => evs.filter((ev) => ev.id !== event.id))
    if (sendCalendarAction) {
      sendCalendarAction("decline", event.id).catch((err) =>
        console.error("Failed to remove event:", err)
      )
    }
    setSelectedEvent(null)
  }

  function handleRescheduleEvent(event, { dayIndex, start, end }) {
    setEvents((evs) =>
      evs.map((ev) => (ev.id === event.id ? { ...ev, dayIndex, start, end } : ev))
    )
    if (sendCalendarAction) {
      sendCalendarAction("reschedule", event.id, {
        original_day: event.dayIndex,
        original_start: event.start,
        original_end: event.end,
        new_day_index: dayIndex,
        new_start: start,
        new_end: end,
      }).catch((err) => console.error("Failed to reschedule event:", err))
    }
  }

  function handleUseSuggestedTime(event) {
    const meta = event.metadata || {}
    if (meta.suggested_start === undefined) return
    handleRescheduleEvent(event, {
      dayIndex: meta.suggested_day_index,
      start: meta.suggested_start,
      end: meta.suggested_end,
    })
    setSelectedEvent(null)
  }

  function handleRetitleEvent(event, title) {
    setEvents((evs) => evs.map((ev) => (ev.id === event.id ? { ...ev, title } : ev)))
    if (sendCalendarAction) {
      sendCalendarAction("modify", event.id, { title }).catch((err) =>
        console.error("Failed to update event title:", err)
      )
    }
  }

  function goToday() {
    setWeekOffset(0)
    if (scrollerRef.current) {
      scrollerRef.current.scrollTop = 8 * ROW_HEIGHT
    }
  }

  return (
    <>
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
                    .filter((event) => event.dayIndex === dayIndex)
                    .map((event) => {
                      const isDragSource = dragging && dragging.event.id === event.id
                      const startMinutes = toMinutes(event.start)
                      const endMinutes = toMinutes(event.end)
                      const duration = endMinutes - startMinutes
                      return (
                        <article
                          key={event.id}
                          className={`calendar-event-card calendar-event-${event.tone}${event.isNew ? " calendar-event-new" : ""}${isDragSource ? " calendar-event-drag-source" : ""}`}
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

                  {dragging && dragPreview && dragPreview.dayIndex === dayIndex && (
                    <div
                      className={`calendar-event-card calendar-event-${dragging.event.tone} calendar-drag-preview`}
                      style={{
                        top: `${(dragPreview.startMinute / 60) * ROW_HEIGHT}px`,
                        height: `${((dragPreview.endMinute - dragPreview.startMinute) / 60) * ROW_HEIGHT}px`,
                      }}
                    >
                      <strong>{dragging.event.title}</strong>
                      <span>
                        {formatEventTime(
                          minutesToTime(dragPreview.startMinute),
                          minutesToTime(dragPreview.endMinute)
                        )}
                      </span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {selectedEvent &&
        createPortal(
          <EventDetailModal
            event={selectedEvent.event}
            anchorRect={selectedEvent.rect}
            onClose={() => setSelectedEvent(null)}
            onUseSuggestedTime={() => handleUseSuggestedTime(selectedEvent.event)}
            onRemove={() => handleRemoveEvent(selectedEvent.event)}
            onRetitle={(title) => handleRetitleEvent(selectedEvent.event, title)}
            onReschedule={(fields) => handleRescheduleEvent(selectedEvent.event, fields)}
          />,
          document.body
        )}
    </>
  )
}

function EventDetailModal({ event, anchorRect, onClose, onUseSuggestedTime, onRemove, onRetitle, onReschedule }) {
  const meta = event.metadata || {}
  const hasSuggestion = meta.suggested_start !== undefined

  const [title, setTitle] = useState(event.title)
  const [dayIndex, setDayIndex] = useState(event.dayIndex)
  const [start, setStart] = useState(event.start)
  const [end, setEnd] = useState(event.end)

  function commitTitle() {
    if (title.trim() && title !== event.title) onRetitle(title.trim())
  }

  function updateDayIndex(next) {
    setDayIndex(next)
    onReschedule({ dayIndex: next, start, end })
  }

  function updateStart(next) {
    setStart(next)
    onReschedule({ dayIndex, start: next, end })
  }

  function updateEnd(next) {
    setEnd(next)
    onReschedule({ dayIndex, start, end: next })
  }

  const modalWidth = 300
  const gap = 14
  const spaceRight = window.innerWidth - anchorRect.right
  const openLeft = spaceRight < modalWidth + gap + 20
  const left = openLeft ? anchorRect.left - modalWidth - gap : anchorRect.right + gap
  const top = Math.min(
    Math.max(8, anchorRect.top + anchorRect.height / 2 - 90),
    window.innerHeight - 260
  )

  return (
    <>
      <div className="event-modal-backdrop" onClick={onClose} />
      <div className="event-modal" style={{ top, left, width: modalWidth }}>
        <div className="meeting-field">
          <label className="meeting-field-label">Title of the meeting</label>
          <input
            className="meeting-field-input"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onBlur={commitTitle}
          />
        </div>
        <div className="meeting-field-row">
          <div className="meeting-field meeting-field-date">
            <label className="meeting-field-label">Date</label>
            <select
              className="meeting-field-input meeting-field-select"
              value={dayIndex}
              onChange={(e) => updateDayIndex(Number(e.target.value))}
            >
              {WEEKDAY_NAMES.map((name, idx) => (
                <option key={name} value={idx}>{name}</option>
              ))}
            </select>
          </div>
          <div className="meeting-field">
            <label className="meeting-field-label">Time</label>
            <div className="meeting-time-range">
              <input
                className="meeting-field-input"
                type="time"
                value={start}
                onChange={(e) => updateStart(e.target.value)}
              />
              <span className="meeting-time-sep">–</span>
              <input
                className="meeting-field-input"
                type="time"
                value={end}
                onChange={(e) => updateEnd(e.target.value)}
              />
            </div>
          </div>
        </div>
        {hasSuggestion && (
          <div className="meeting-field">
            <label className="meeting-field-label">Suggested time</label>
            <div className="meeting-suggested-row">
              <input
                className="meeting-field-input"
                type="text"
                value={WEEKDAY_NAMES[meta.suggested_day_index]}
                disabled
              />
              <div className="meeting-time-range">
                <input className="meeting-field-input" type="text" value={toDisplayTime(meta.suggested_start)} disabled />
                <span className="meeting-time-sep">–</span>
                <input className="meeting-field-input" type="text" value={toDisplayTime(meta.suggested_end)} disabled />
              </div>
            </div>
          </div>
        )}
        <div className="meeting-decision-row">
          <button type="button" className="meeting-reject-btn" onClick={onRemove}>
            Remove
          </button>
          {hasSuggestion && (
            <button type="button" className="meeting-accept-btn" onClick={onUseSuggestedTime}>
              Update to suggested time →
            </button>
          )}
        </div>
      </div>
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
  return `${hour12}:${String(mm).padStart(2, "0")}${suffix}`
}

function isSameDate(a, b) {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  )
}
