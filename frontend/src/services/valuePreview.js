// Lightweight, fully client-side estimate of how a pending calendar decision
// (accept / decline / postpone) might shift the participant's value profile.
// This is a UX preview only — it does not touch the backend value ledger,
// which only recomputes for real via the Advocate/Challenger/Synthesizer
// pipeline at "Complete Round". The estimate is deterministic (same event +
// action always produces the same numbers) so hovering back and forth
// between options is stable rather than flickering.

function hashSeed(str) {
  let h = 0
  for (let i = 0; i < str.length; i++) {
    h = (h * 31 + str.charCodeAt(i)) | 0
  }
  return h
}

function noise(seed) {
  const x = Math.sin(seed) * 43758.5453
  return x - Math.floor(x) // [0, 1)
}

/**
 * @param {Array<{label:string, weight:number}>} weights current value weights
 * @param {string} eventId id of the event being decided on (seeds the estimate)
 * @param {"accept"|"decline"|"postpone"} action
 * @returns {Array<{label:string, weight:number}>} same shape, weight replaced with the preview
 */
export function previewWeightsForAction(weights, eventId, action) {
  if (!weights || weights.length === 0) return weights
  const n = weights.length
  const avg = 100 / n
  const seedBase = hashSeed(`${eventId || "evt"}|${action}`)

  const raw = weights.map((v, i) => {
    const jitter = (noise(seedBase + i * 7.13) - 0.5) * 6
    let target = v.weight
    if (action === "accept") {
      // Leaning in: reinforce values already above average, ease off the rest.
      target = v.weight + (v.weight - avg) * 0.35
    } else if (action === "decline") {
      // Pushing back: pull toward the values currently under-represented.
      target = v.weight - (v.weight - avg) * 0.35
    } else if (action === "postpone") {
      // Undecided: nudge gently toward equilibrium rather than committing.
      target = v.weight + (avg - v.weight) * 0.15
    }
    return Math.max(4, target + jitter)
  })

  const sum = raw.reduce((a, b) => a + b, 0)
  const normalized = raw.map((w) => Math.round((w / sum) * 100))

  // Rounding can drift the total off 100 — correct it on the largest bucket.
  const drift = 100 - normalized.reduce((a, b) => a + b, 0)
  if (drift !== 0) {
    const maxIdx = normalized.indexOf(Math.max(...normalized))
    normalized[maxIdx] += drift
  }

  return weights.map((v, i) => ({ ...v, weight: normalized[i] }))
}
