import React, {useEffect} from 'react'
import {beforeEach, expect, it, vi} from 'vitest'
import {act, fireEvent, render, screen, waitFor} from '@testing-library/react'
import SessionProvider, {useSession} from './SessionContext'

const profile = ['wellbeing', 'achievement_growth', 'relationships_care', 'autonomy_privacy', 'responsibility_fairness']
  .map(id => ({id, label: id, relative_weight: .2, evidence: []}))

function Harness({snapshots}) {
  const session = useSession()
  useEffect(() => { snapshots.push({status: session.onboarding_status, profile: session.currentProfile.length, round: session.current_round}) },
    [session.onboarding_status, session.currentProfile.length, session.current_round, snapshots])
  return <><button onClick={() => session.sendOnboardingMessage('final answer')}>answer</button>
    <button onClick={() => session.skipOnboardingQuestion('rescheduling_concerns')}>skip</button>
    <span data-testid="round">{session.current_round}</span></>
}

function response(body) { return Promise.resolve({ok: true, json: () => Promise.resolve(body)}) }

beforeEach(() => { localStorage.setItem('calendar_session_id', 's1'); vi.restoreAllMocks() })

it.each([['answer', '/messages'], ['skip', '/skip-question']])('automatically completes after final %s exactly once', async (button, terminalPath) => {
  const calls = []
  globalThis.fetch = vi.fn((url) => {
    calls.push(url)
    if (url.endsWith('/state')) return response({session_id: 's1', onboarding_status: 'active', onboarding_question_id: 'rescheduling_concerns',
      onboarding_assistant_message: 'Last question', current_round: 0, total_rounds: 15, round_status: 'onboarding', current_profile: [], calendar: []})
    if (url.endsWith(terminalPath)) return response({onboarding_status: 'active', question_id: null, can_complete: true, assistant_message: 'Preparing'})
    if (url.endsWith('/onboarding/complete')) return response({onboarding_status: 'complete', question_id: null, can_complete: true,
      assistant_message: 'Thanks. We can now begin.', current_profile: profile, profile_status: 'initialized', profile_source: 'onboarding_conversation',
      profile_stage: 'conversation_initial', profile_version: 1, initial_profile_version: 1, current_round: 0})
    if (url.endsWith('/events/next')) return response({onboarding_status: 'complete', current_round: 1, total_rounds: 15,
      round_status: 'awaiting_decision', active_event: {scenario_id: 'scenario-1', description: 'Request'}, event: {scenario_id: 'scenario-1', description: 'Request'}, current_profile: profile})
    throw new Error(`Unexpected URL ${url}`)
  })
  const snapshots = []
  render(<SessionProvider><Harness snapshots={snapshots}/></SessionProvider>)
  await screen.findByText('0')
  await act(async () => { fireEvent.click(screen.getByRole('button', {name: button})); fireEvent.click(screen.getByRole('button', {name: button})) })
  await waitFor(() => expect(screen.getByTestId('round')).toHaveTextContent('1'))
  expect(calls.filter(url => url.endsWith('/onboarding/complete'))).toHaveLength(1)
  expect(calls.filter(url => url.endsWith('/events/next'))).toHaveLength(1)
  expect(snapshots.some(item => item.status === 'complete' && item.profile === 5 && item.round === 0)).toBe(true)
})
