import React from 'react'
import {beforeEach, describe, expect, it, vi} from 'vitest'
import {fireEvent, render, screen, waitFor} from '@testing-library/react'

let session
vi.mock('../../services/SessionContext', () => ({useSession: () => session}))
import ValuesPanel from './values'

const ids = ['wellbeing', 'achievement_growth', 'relationships_care', 'autonomy_privacy', 'responsibility_fairness']

describe('conversation-initial value profile', () => {
  beforeEach(() => {
    session = {
      valueWeights: ids.map((id, index) => ({id, label: `Priority ${index + 1}`, weight: .2, tone: 'green', evidence: []})),
      previewValueWeights: null, previewLoading: false, activePreviewTransition: null,
      latestActionTransition: null, latestRoundTransition: null,
      profile_source: 'onboarding_conversation', profile_stage: 'conversation_initial', profile_version: 1,
      initial_profile_version: 1, initial_profile_displayed: false, current_round: 0,
      logInitialProfileViewed: vi.fn().mockResolvedValue({}), logProfileInteraction: vi.fn().mockResolvedValue({}),
    }
  })

  it('renders five qualified, non-numerical initial bubbles and logs exposure once', async () => {
    const {rerender} = render(<ValuesPanel />)
    expect(screen.getByRole('heading', {name: 'Initial scheduling priorities'})).toBeInTheDocument()
    expect(screen.getByText(/preliminary interpretation/)).toBeVisible()
    expect(screen.getAllByRole('button', {name: /View evidence/})).toHaveLength(5)
    expect(screen.queryByText(/\d+%/)).not.toBeInTheDocument()
    await waitFor(() => expect(session.logInitialProfileViewed).toHaveBeenCalledTimes(1))
    rerender(<ValuesPanel />)
    expect(session.logInitialProfileViewed).toHaveBeenCalledTimes(1)
  })

  it('logs opening evidence and closing the modal', async () => {
    render(<ValuesPanel />)
    fireEvent.click(screen.getByRole('button', {name: 'View evidence for Priority 1'}))
    expect(session.logProfileInteraction).toHaveBeenCalledWith(expect.objectContaining({event_type: 'value_bubble_opened', value_id: 'wellbeing'}))
    expect(session.logProfileInteraction).toHaveBeenCalledWith(expect.objectContaining({event_type: 'value_evidence_opened', value_id: 'wellbeing'}))
    fireEvent.click(screen.getByRole('button', {name: 'Close'}))
    expect(session.logProfileInteraction).toHaveBeenCalledWith(expect.objectContaining({event_type: 'value_modal_closed', value_id: 'wellbeing'}))
  })
})
