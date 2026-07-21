// Maps calendar events to value-profile entries. Both the default weights
// and the backend's ledger (models.py to_weights) assign tones in the same
// order — green, rose, amber, cyan, violet — so a value's index is enough
// to know its tone. Events are matched to values by category:
//   work → value 1, social → value 2, personal → value 3, health → value 4,
//   anything else (obligation, unknown) → value 5.
export const VALUE_TONES = ["green", "rose", "amber", "cyan", "violet"]

const CATEGORY_ORDER = ["work", "social", "personal", "health"]

export function valueIndexForEvent(event, valueCount = 5) {
  const idx = CATEGORY_ORDER.indexOf(event.category || "work")
  if (idx === -1) return Math.min(4, valueCount - 1)
  return Math.min(idx, valueCount - 1)
}

export function toneForEvent(event, valueCount = 5) {
  return VALUE_TONES[valueIndexForEvent(event, valueCount)]
}
