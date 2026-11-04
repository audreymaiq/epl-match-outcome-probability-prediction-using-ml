import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({ loaded: false, mutate: vi.fn() }))
vi.mock('@/lib/competition', () => ({
  useCompetition: () => ({ league: 'test', competition: { name: 'Test league', country: 'Country', rounds: 46 } }),
  withCompetition: (href: string) => href,
}))
vi.mock('@/lib/hooks', () => ({
  useMatches: () => ({ data: { data: [] }, isLoading: false, isError: false }),
  useTeams: () => ({ data: { data: [{ id: 1, name: 'Home club' }, { id: 2, name: 'Away club' }] }, isLoading: false }),
  useSeasons: () => ({ data: ['2024/2025'] }),
  useModelInfo: () => ({ data: { status: state.loaded ? 'loaded' : 'not_loaded' } }),
  usePredict: () => ({ mutate: state.mutate, reset: vi.fn(), isPending: false, isError: false }),
}))
import HomePage from './page'

beforeEach(() => { state.loaded = false; state.mutate.mockReset() })

describe('Prediction form', () => {
  it('disables prediction when no model is active', () => {
    render(<HomePage />)
    expect(screen.getByRole('button', { name: /Model not installed/ })).toBeDisabled()
  })

  it('uses configured rounds and sends local kickoff as a timezone-aware timestamp', () => {
    state.loaded = true
    render(<HomePage />)
    fireEvent.change(screen.getByLabelText('Home club'), { target: { value: '1' } })
    fireEvent.change(screen.getByLabelText('Away club'), { target: { value: '2' } })
    const kickoff = '2031-08-15T19:30'
    fireEvent.change(screen.getByLabelText('Kickoff in your time zone'), { target: { value: kickoff } })
    const round = screen.getByLabelText('Matchweek')
    expect(round).toHaveAttribute('max', '46')
    fireEvent.change(round, { target: { value: '40' } })
    fireEvent.click(screen.getByRole('button', { name: /Show probabilities/ }))
    expect(state.mutate).toHaveBeenCalledWith(expect.objectContaining({
      home_team_id: 1, away_team_id: 2, season_name: '2024/2025', match_week: 40,
      match_datetime: new Date(kickoff).toISOString(),
    }))
  })
})
