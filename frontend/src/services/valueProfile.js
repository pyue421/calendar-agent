export const VALUE_IDS = [
  "wellbeing",
  "achievement_growth",
  "relationships_care",
  "autonomy_privacy",
  "responsibility_fairness",
]

const TONES = {wellbeing: "green", achievement_growth: "rose", relationships_care: "amber",
  autonomy_privacy: "cyan", responsibility_fairness: "violet"}

export function normalizeValueProfile(profile, expectedScale = null) {
  if (!Array.isArray(profile) || profile.length !== VALUE_IDS.length) return null
  const byId = new Map()
  for (const value of profile) {
    if (!value || !VALUE_IDS.includes(value.id) || byId.has(value.id)) return null
    const weight = value.relative_weight ?? value.weight ?? value.posterior_mean
    if (!Number.isFinite(weight) || weight < 0) return null
    byId.set(value.id, {...value, weight, tone: value.tone || TONES[value.id], evidence: value.evidence || [
      ...(value.conversation_evidence || []), ...(value.calendar_action_evidence || []),
    ]})
  }
  const normalized = VALUE_IDS.map(id => byId.get(id))
  const total = normalized.reduce((sum, value) => sum + value.weight, 0)
  const scale = total > 2 ? 100 : 1
  const tolerance = scale === 100 ? 2 : 0.02
  if (Math.abs(total - scale) > tolerance || (expectedScale && scale !== expectedScale)) return null
  return {profile: normalized, scale}
}

export function bubbleSize(weight) {
  return 62 + Math.min(100, Math.max(0, weight)) * 1.9
}
