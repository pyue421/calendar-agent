import React from 'react'
import {beforeEach, expect, it, vi} from 'vitest'
import {render, screen} from '@testing-library/react'

let session
vi.mock('../../services/SessionContext', () => ({useSession: () => session}))
import ChatbotPanel from './ChatbotPanel'

beforeEach(() => {
  session = {sessionId: 's1', current_round: 0, total_rounds: 15, round_status: 'onboarding', loading: false,
    awaiting_rationale: false, onboarding_status: 'active', onboarding_progress: {answered_core: 2, total_core: 6},
    onboarding_question_id: 'protected_commitments', onboardingLoading: false, onboardingError: null,
    onboardingAssistantMessage: null, onboarding_turns: null, event: null,
    sendOnboardingMessage: vi.fn(), skipOnboardingQuestion: vi.fn(), useNeutralPrior: vi.fn(),
    startRound: vi.fn(), sendChat: vi.fn(), setCandidateEvent: vi.fn(), clearPreview: vi.fn()}
})

it('keeps skip and neutral controls without a manual finish control', () => {
  render(<ChatbotPanel />)
  expect(screen.getByRole('button', {name: 'Skip question'})).toBeInTheDocument()
  expect(screen.getByRole('button', {name: 'Continue with a neutral starting model'})).toBeInTheDocument()
  expect(screen.queryByRole('button', {name: /Finish onboarding/i})).not.toBeInTheDocument()
  expect(screen.queryByRole('button', {name: /Start Round 1/i})).not.toBeInTheDocument()
})

it('restores the active scenario and reflection prompt', () => {
  session = {...session, onboarding_status: 'complete', round_status: 'awaiting_rationale', current_round: 1,
    awaiting_rationale: true, event: {scenario_id: 'scenario-1', description: 'Restored scheduling request',
      title: 'Request', requested_start: '2026-01-05T09:00:00', requested_end: '2026-01-05T10:00:00', committedAction: 'accept'},
    can_start_round: true, week_start: '2026-01-05', calendarEvents: [], active_request_conflicts: [], accept_available: true}
  render(<ChatbotPanel />)
  expect(screen.getByText('Restored scheduling request')).toBeInTheDocument()
  expect(screen.getByText('What mattered most to you in making that decision?')).toBeInTheDocument()
})
