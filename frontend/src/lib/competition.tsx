'use client'

import { createContext, useContext, Fragment, type ReactNode } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { getCompetitions } from './api'

export interface Competition {
  slug: string
  name: string
  country: string
  timezone: string
  rounds: number
  is_default?: boolean
}

interface Selection {
  league: string
  ready: boolean
  competition?: Competition
  competitions: Competition[]
  select: (slug: string) => void
}

const defaultLeague = process.env.NEXT_PUBLIC_DEFAULT_LEAGUE || 'epl'
const Context = createContext<Selection>({ league: defaultLeague, ready: false, competitions: [], select: () => {} })

export function withCompetition(href: string, league: string) {
  if (!href.startsWith('/') || href.startsWith('//')) return href
  const url = new URL(href, 'http://localhost')
  url.searchParams.set('league', league)
  return `${url.pathname}${url.search}${url.hash}`
}

export function CompetitionProvider({ children }: { children: ReactNode }) {
  const requested = useSearchParams().get('league')
  const router = useRouter()
  const registry = useQuery({ queryKey: ['competitions'], queryFn: () => getCompetitions().then((response) => response.data) })
  const league = requested || registry.data?.find((item) => item.is_default)?.slug || defaultLeague
  const competitions = registry.data ?? []
  const competition = competitions.find((item) => item.slug === league)
  function select(slug: string) {
    if (!competitions.some((item) => item.slug === slug)) return
    router.push(withCompetition('/', slug))
  }
  return <Context.Provider value={{ league, ready: !!competition, competition, competitions, select }}>
    {(registry.isError || (registry.isSuccess && !competition)) && <div role="alert" className="page-frame my-5 border border-[var(--danger)] p-4 text-sm text-white">
      {registry.isError ? 'Competitions could not be loaded.' : 'This competition is not configured.'}
      <button type="button" className="button-secondary ml-4" onClick={() => registry.isError ? void registry.refetch() : router.push('/')}>{registry.isError ? 'Try again' : 'Open match centre'}</button>
    </div>}
    <Fragment key={league}>{children}</Fragment>
  </Context.Provider>
}

export const useCompetition = () => useContext(Context)
