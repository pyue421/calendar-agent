import React, { useEffect, useMemo, useRef, useState } from "react"
import { useSession } from "../../services/SessionContext"
import "./calendar.css"

const ROW_HEIGHT = 64
const HOURS = Array.from({ length: 24 }, (_, idx) => idx)
const WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri"]

// Map backend snake_case event to frontend camelCase
function mapEvent(ev) {
  return {
    id: ev.id,
    title: ev.title,
    dayIndex: ev.day_index ?? ev.dayIndex ?? 0,
    start: ev.start,
    end: ev.end,
    tone: ev.tone || "blue",
    category: ev.category || "work",
    isNew: ev.is_new ?? ev.isNew ?? false,
  }
}

export default function CalendarPanel() {
  const { calendarEvents, sendCalendarAction } = useSession()

  const [weekOffset, setWeekOffset] = useState(0)
  const [events, setEvents] = useState([])
  const [dragging, setDragging] = useState(null)
  const [dragPreview, setDragPreview] = useState(null)
  const scrollerRef = useRef(null)
  const daysColumnsRef = useRef(null)
  const dragPreviewRef = useRef(null)

  // Sync events from session context
  useEffect(() => {
    if (calendarEvents && calendarEvents.length > 0) {
      setEvents(calendarEvents.map(mapEvent))
    }
  }, [calendarEvents])

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

    function onMouseMove(e) {
      const slot = computeSnappedSlot(e)
      if (slot) {
        dragPreviewRef.current = slot
        setDragPreview(slot)
      }
    }

    function onMouseUp(e) {
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
