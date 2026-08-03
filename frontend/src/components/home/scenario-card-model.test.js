import test from "node:test"
import assert from "node:assert/strict"
import {readFileSync} from "node:fs"
import {fileURLToPath} from "node:url"
import {actionCandidate, canReschedule, candidateEvent, editedSchedule, requestedFields, scheduleConflicts, schedulesEqual, weekDates} from "./scenario-card-model.js"

const card = {scenario_id: "s1", title: "Planning", requested_start: "2026-07-20T09:00:00", requested_end: "2026-07-20T10:00:00"}
const requested = requestedFields(card)
const changed = editedSchedule("2026-07-21", "11:00", "12:15")

test("controls initialize from the requested schedule", () => assert.deepEqual(requested, {date: "2026-07-20", startTime: "09:00", endTime: "10:00", schedule: {start: card.requested_start, end: card.requested_end}}))
test("decline preview and decision omit a candidate schedule", () => assert.equal(actionCandidate("decline", requested.schedule, changed), null))
test("accept preview and decision preserve requested-time semantics by omitting edits", () => assert.equal(actionCandidate("accept", requested.schedule, changed), null))
test("reschedule sends the edited date, start, and end", () => assert.deepEqual(actionCandidate("reschedule", requested.schedule, changed), changed.schedule))
test("unchanged schedule cannot be rescheduled", () => assert.equal(canReschedule(requested.schedule, editedSchedule(requested.date, requested.startTime, requested.endTime)), false))
test("invalid schedules are rejected", () => { const invalid = editedSchedule("2026-07-21", "12:00", "11:00"); assert.equal(invalid.valid, false); assert.equal(canReschedule(requested.schedule, invalid), false) })
test("schedule comparison ignores seconds precision", () => assert.equal(schedulesEqual(requested.schedule, {start: "2026-07-20T09:00", end: "2026-07-20T10:00"}), true))
test("temporary event follows a valid changed schedule", () => assert.deepEqual(candidateEvent(card, requested.schedule, changed), {id: "s1-candidate", title: "Planning (candidate)", ...changed.schedule, temporary: true}))
test("temporary event is absent for unchanged schedule", () => assert.equal(candidateEvent(card, requested.schedule, editedSchedule(requested.date, requested.startTime, requested.endTime)), null))
test("date selector uses actual dates from the study week", () => { const dates = weekDates("2026-07-20", requested.date); assert.equal(dates.length, 7); assert.equal(dates[0].value, "2026-07-20"); assert.equal(dates[6].value, "2026-07-26") })
test("compact UI has hover and focus preview handlers without preview buttons", () => { const source = readFileSync(fileURLToPath(new URL("./ChatbotPanel.jsx", import.meta.url)), "utf8"); assert.match(source, /onMouseEnter/); assert.match(source, /onFocus/); assert.doesNotMatch(source, />Preview values</); assert.doesNotMatch(source, /datetime-local/) })
test("reschedule refresh is debounced", () => { const source = readFileSync(fileURLToPath(new URL("./ChatbotPanel.jsx", import.meta.url)), "utf8"); assert.match(source, /setTimeout\([^]*350\)/) })
test("Escape closes the popover", () => { const source = readFileSync(fileURLToPath(new URL("./ChatbotPanel.jsx", import.meta.url)), "utf8"); assert.match(source, /event\.key === "Escape"/) })
test("stale preview responses are guarded", () => { const source = readFileSync(fileURLToPath(new URL("../../services/SessionContext.jsx", import.meta.url)), "utf8"); assert.match(source, /requestNumber === previewRequest\.current/) })

const blocking = [{id: "busy", title: "Team planning", start: "2026-07-21T11:30:00", end: "2026-07-21T12:30:00", blocks_time: true}]
test("Accept availability is backend-driven and conflict details are rendered", () => { const source = readFileSync(fileURLToPath(new URL("./ChatbotPanel.jsx", import.meta.url)), "utf8"); assert.match(source, /accept_available/); assert.match(source, /item\.title/) })
test("calendar state changes can enable Accept without restarting", () => assert.equal(scheduleConflicts([], requested.schedule).length, 0))
test("conflicting Reschedule candidates are invalid", () => assert.equal(scheduleConflicts(blocking, changed.schedule)[0].title, "Team planning"))
test("invalid candidates cannot trigger value previews", () => { const source = readFileSync(fileURLToPath(new URL("./ChatbotPanel.jsx", import.meta.url)), "utf8"); assert.match(source, /if \(conflicts\.length\)/) })
test("existing drag uses the calendar action API", () => { const source = readFileSync(fileURLToPath(new URL("./calendar.jsx", import.meta.url)), "utf8"); assert.match(source, /action_type: "reschedule_existing"/) })
test("locally invalid drag returns before API invocation", () => { const source = readFileSync(fileURLToPath(new URL("./calendar.jsx", import.meta.url)), "utf8"); assert.match(source, /oldEvent\.temporary \|\| slot\.conflicts\.length/) })
test("backend drag rejection rolls back the event", () => { const source = readFileSync(fileURLToPath(new URL("./calendar.jsx", import.meta.url)), "utf8"); assert.match(source, /ev\.id === oldEvent\.id \? oldEvent/) })
test("successful calendar actions apply authoritative state and revision", () => { const source = readFileSync(fileURLToPath(new URL("../../services/SessionContext.jsx", import.meta.url)), "utf8"); assert.match(source, /applyState\(data\)/); assert.match(source, /calendarActionLoading/) })
test("calendar changes clear stale previews", () => { const source = readFileSync(fileURLToPath(new URL("../../services/SessionContext.jsx", import.meta.url)), "utf8"); assert.match(source, /setPreview\(null\).*applyState\(data\)/s) })
test("temporary candidates never produce calendar actions", () => { const source = readFileSync(fileURLToPath(new URL("./calendar.jsx", import.meta.url)), "utf8"); assert.match(source, /if \(calEvent\.temporary\) return/); assert.match(source, /oldEvent\.temporary/) })
test("non-blocking and boundary-adjacent events do not conflict", () => { assert.equal(scheduleConflicts([{...blocking[0], blocks_time: false}], changed.schedule).length, 0); assert.equal(scheduleConflicts([{...blocking[0], start: changed.schedule.end, end: "2026-07-21T13:00:00"}], changed.schedule).length, 0) })

test("unified profile has no evidence-source toggle", () => {
  const source = readFileSync(fileURLToPath(new URL("./values.jsx", import.meta.url)), "utf8")
  assert.doesNotMatch(source, /viewMode|switchMode|values-view-toggle/)
  assert.doesNotMatch(source, />Conversation<|>Calendar actions</)
})
test("exactly one committed profile bubble collection is rendered", () => {
  const source = readFileSync(fileURLToPath(new URL("./values.jsx", import.meta.url)), "utf8")
  assert.equal((source.match(/className="value-bubble-wrap"/g) || []).length, 1)
})
test("conversation and action evidence share one array", () => {
  const source = readFileSync(fileURLToPath(new URL("../../services/SessionContext.jsx", import.meta.url)), "utf8")
  assert.match(source, /evidence: value\.evidence/)
  assert.doesNotMatch(source, /calendarEvents: value\.calendar_action_evidence/)
})
test("unified evidence items display source badges", () => {
  const source = readFileSync(fileURLToPath(new URL("./values.jsx", import.meta.url)), "utf8")
  assert.match(source, /value-evidence-source/)
  assert.match(source, /Conversation/)
  assert.match(source, /Calendar action/)
})
test("calendar event classes use backend value tones", () => {
  const source = readFileSync(fileURLToPath(new URL("./calendar.jsx", import.meta.url)), "utf8")
  assert.match(source, /ev\.value_mapping\?\.tone \?\? ev\.value_tone \?\? "neutral"/)
})
test("frontend category order does not control event color", () => {
  const source = readFileSync(fileURLToPath(new URL("./calendar.jsx", import.meta.url)), "utf8")
  assert.doesNotMatch(source, /CATEGORY_ORDER|toneForEvent|valueIndexForEvent/)
})
test("invalid styling still overrides semantic tones", () => {
  const source = readFileSync(fileURLToPath(new URL("./calendar.css", import.meta.url)), "utf8")
  assert.match(source, /\.calendar-event-invalid[^]*!important/)
})
test("temporary candidates preserve the incoming semantic tone", () => {
  const mappedCard = {...card, value_mapping: {tone: "rose"}, primary_value_id: "achievement_growth", value_tone: "rose"}
  assert.equal(candidateEvent(mappedCard, requested.schedule, changed).value_mapping.tone, "rose")
})
test("counterfactual previews remain anchored popovers", () => {
  const source = readFileSync(fileURLToPath(new URL("./ChatbotPanel.jsx", import.meta.url)), "utf8")
  assert.match(source, /ValuePreviewPopover/)
  assert.match(source, /createPortal/)
})
test("focused-value dimming was not imported", () => {
  const calendar = readFileSync(fileURLToPath(new URL("./calendar.jsx", import.meta.url)), "utf8")
  const css = readFileSync(fileURLToPath(new URL("./calendar.css", import.meta.url)), "utf8")
  assert.doesNotMatch(calendar, /focusedValueIndex/)
  assert.doesNotMatch(css, /calendar-event-dimmed/)
})
test("current value bubbles display their committed percentages", () => {
  const source = readFileSync(fileURLToPath(new URL("./values.jsx", import.meta.url)), "utf8")
  assert.match(source, /value\.relative_weight\.toFixed\(1\)/)
})
test("counterfactual and committed percentages use the same precision", () => {
  const source = readFileSync(fileURLToPath(new URL("./ChatbotPanel.jsx", import.meta.url)), "utf8")
  assert.match(source, /percentage\.toFixed\(1\)/)
  assert.doesNotMatch(source, /Math\.round\(value\.weight\)/)
})
