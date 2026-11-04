import { render, screen, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { AxiosAdapter } from 'axios'
import api from './api'
import { CompetitionProvider, withCompetition } from './competition'
import { useMatches } from './hooks'

vi.mock('next/navigation', async () => {
  const { useSyncExternalStore } = await import('react')
  return {
    useRouter: () => ({ push: vi.fn() }),
    useSearchParams: () => new URLSearchParams(useSyncExternalStore(
      (callback) => { window.addEventListener('popstate', callback); return () => window.removeEventListener('popstate', callback) },
      () => window.location.search,
      () => '',
    )),
  }
})

const originalAdapter = api.defaults.adapter
afterEach(() => { api.defaults.adapter = originalAdapter; window.history.replaceState({}, '', '/') })

function Probe() {
  const { data } = useMatches()
  return <p>{data?.data[0]?.home_team.name || 'Waiting'}</p>
}

describe('Competition scope', () => {
  it('preserves existing filters and hashes in internal links', () => {
    expect(withCompetition('/matches?team_id=5#results', 'other')).toBe('/matches?team_id=5&league=other#results')
    expect(withCompetition('https://example.com', 'other')).toBe('https://example.com')
  })

  it('sends the URL scope to the API and separates cached results after a scope change', async () => {
    const scopes: string[] = []
    const adapter: AxiosAdapter = async (config) => {
      const registry = config.url === '/api/v1/leagues'
      if (!registry) scopes.push(config.params.league)
      return { status: 200, statusText: 'OK', config, headers: {}, data: registry ? [
        { slug: 'epl', name: 'Premier League', country: 'England', rounds: 38, timezone: 'Europe/London', is_default: true },
        { slug: 'other', name: 'Another league', country: 'Elsewhere', rounds: 46, timezone: 'UTC' },
      ] : { data: [{ id: 1, home_team: { name: config.params.league === 'epl' ? 'EPL club' : 'Other club' } }], pagination: { total: 1 } } }
    }
    api.defaults.adapter = adapter
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><CompetitionProvider><Probe /></CompetitionProvider></QueryClientProvider>)
    expect(await screen.findByText('EPL club')).toBeVisible()
    act(() => { window.history.replaceState({}, '', '/?league=other'); window.dispatchEvent(new PopStateEvent('popstate')) })
    expect(await screen.findByText('Other club')).toBeVisible()
    await waitFor(() => expect(scopes).toEqual(['epl', 'other']))
    expect(client.getQueryData(['epl', 'matches', undefined])).toBeDefined()
    expect(client.getQueryData(['other', 'matches', undefined])).toBeDefined()
    client.clear()
  })
})
