const ISO_MINUTE = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/

export function requestedFields(card) {
  const start = ISO_MINUTE.exec(card.requested_start || "")
  const end = ISO_MINUTE.exec(card.requested_end || "")
  return {
    date: start?.[1] || "",
    startTime: start?.[2] || "",
    endTime: end?.[2] || "",
    schedule: {start: card.requested_start, end: card.requested_end},
  }
}

export function editedSchedule(date, startTime, endTime) {
  if (!date || !startTime || !endTime) return {valid: false, error: "Choose a date, start time, and end time."}
  const start = `${date}T${startTime}:00`
  const end = `${date}T${endTime}:00`
  if (new Date(end).getTime() <= new Date(start).getTime()) return {valid: false, error: "End time must be later than start time."}
  return {valid: true, schedule: {start, end}, error: ""}
}

function minute(value) { return String(value || "").slice(0, 16) }
export function schedulesEqual(left, right) {
  return Boolean(left && right && minute(left.start) === minute(right.start) && minute(left.end) === minute(right.end))
}

export function actionCandidate(action, requested, edited) {
  if (action !== "reschedule") return null
  return edited?.valid && !schedulesEqual(requested, edited.schedule) ? edited.schedule : null
}

export function canReschedule(requested, edited) {
  return Boolean(actionCandidate("reschedule", requested, edited))
}

export function weekDates(weekStart, fallbackDate) {
  const first = new Date(`${weekStart || fallbackDate}T00:00:00`)
  if (Number.isNaN(first.getTime())) return fallbackDate ? [fallbackDate] : []
  return Array.from({length: 7}, (_, offset) => {
    const date = new Date(first); date.setDate(first.getDate() + offset)
    const value = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`
    return {value, label: date.toLocaleDateString(undefined, {weekday: "short", month: "short", day: "numeric"})}
  })
}

export function candidateEvent(card, requested, edited) {
  const schedule = actionCandidate("reschedule", requested, edited)
  if (!schedule) return null
  const event = {id: `${card.scenario_id}-candidate`, title: `${card.title} (candidate)`, ...schedule, temporary: true}
  if (card.value_mapping) {
    Object.assign(event, {value_mapping: card.value_mapping, primary_value_id: card.primary_value_id, value_tone: card.value_tone})
  }
  return event
}

export function scheduleConflicts(calendar, schedule, excludeEventId = null) {
  if (!schedule) return []
  const start = new Date(schedule.start).getTime(), end = new Date(schedule.end).getTime()
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return []
  return (calendar || []).filter(event => event.id !== excludeEventId && !event.temporary && event.blocks_time !== false &&
    start < new Date(event.end).getTime() && end > new Date(event.start).getTime())
}
