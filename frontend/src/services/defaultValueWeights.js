// Placeholder value profile shown before the backend has any real
// value_weights (i.e. before the first "Complete Round" call). Shared so the
// values panel and the chatbot's decision-preview bubbles agree on a
// baseline instead of drifting out of sync with their own copies.
export const DEFAULT_VALUE_WEIGHTS = [
  {
    label: "Wellbeing",
    weight: 20,
    tone: "green",
    evidence: [{ id: "d1", text: "Waiting on your first conversation", round: 0 }],
    calendarEvents: [{ id: "d1c", text: "Waiting on your first calendar action", round: 0 }],
  },
  {
    label: "Achievement & Growth",
    weight: 20,
    tone: "rose",
    evidence: [{ id: "y1", text: "Keep chatting to surface this value", round: 0 }],
    calendarEvents: [{ id: "y1c", text: "Accept or decline events to surface this value", round: 0 }],
  },
  {
    label: "Relationships & Care",
    weight: 20,
    tone: "amber",
    evidence: [{ id: "v1", text: "Keep chatting to surface this value", round: 0 }],
    calendarEvents: [{ id: "v1c", text: "Accept or decline events to surface this value", round: 0 }],
  },
  {
    label: "Autonomy & Privacy",
    weight: 20,
    tone: "cyan",
    evidence: [{ id: "t1", text: "Keep chatting to surface this value", round: 0 }],
    calendarEvents: [{ id: "t1c", text: "Accept or decline events to surface this value", round: 0 }],
  },
  {
    label: "Value 5",
    weight: 20,
    tone: "violet",
    evidence: [{ id: "a1", text: "Keep chatting to surface this value", round: 0 }],
    calendarEvents: [{ id: "a1c", text: "Accept or decline events to surface this value", round: 0 }],
  },
]
