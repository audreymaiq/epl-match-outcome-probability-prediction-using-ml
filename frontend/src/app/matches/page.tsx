'use client'

import { useCompetition } from '@/lib/competition'

import { Suspense, useMemo, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { CalendarDays, Search, SlidersHorizontal } from 'lucide-react'
import { useMatches, useTeams } from '@/lib/hooks'
import { PageHeading } from '@/components/page-heading'
import { MatchCard } from '@/components/match-card'
import type { MatchesParams, Team } from '@/lib/types'

function MatchesView({ initialTeam }: { initialTeam: string }) {
  const { competition } = useCompetition()
  const [status, setStatus] = useState('')
  const [teamId, setTeamId] = useState(initialTeam)
  const [season, setSeason] = useState('')
  const [page, setPage] = useState(1)
  const { data: teamsResponse } = useTeams()
  const teams = teamsResponse?.data ?? []
  const params: MatchesParams = useMemo(() => ({ status: status || undefined, season: season || undefined, team_id: teamId ? Number(teamId) : undefined, page, page_size: 20 }), [page, season, status, teamId])
  const { data, isLoading, isError } = useMatches(params)
  const matches = data?.data ?? []
  const pagination = data?.pagination
  const totalPages = pagination?.total_pages ?? 1

  function update<T>(setter: (value: T) => void, value: T) { setter(value); setPage(1) }

  return (
    <main className="page-frame pb-16 pt-8 sm:pt-12">
      <PageHeading eyebrow={competition?.name || 'Football'} title="Fixtures" description="Browse matches by club, season or status." action={pagination ? <div className="border-l border-[var(--border)] pl-4 text-right"><p className="font-mono text-lg font-bold text-white">{pagination.total.toLocaleString()}</p><p className="text-[0.65rem] text-[var(--muted)]">matches found</p></div> : undefined} />
      <section className="surface-quiet mb-6 p-4 sm:p-5" aria-label="Match filters">
        <div className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[var(--muted)]"><SlidersHorizontal size={14} /> Refine fixtures</div>
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="relative"><span className="sr-only">Club</span><Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--subtle)]" /><select className="field-control pl-9" value={teamId} onChange={(event) => update(setTeamId, event.target.value)}><option value="">All clubs</option>{teams.map((team: Team) => <option key={team.id} value={team.id}>{team.name}</option>)}</select></label>
          <label><span className="sr-only">Status</span><select className="field-control" value={status} onChange={(event) => update(setStatus, event.target.value)}><option value="">All match statuses</option><option value="SCHEDULED">Upcoming</option><option value="FINISHED">Finished</option><option value="POSTPONED">Postponed</option></select></label>
          <label><span className="sr-only">Season</span><input className="field-control" inputMode="text" placeholder="Season, e.g. 2024/2025" value={season} onChange={(event) => update(setSeason, event.target.value)} /></label>
        </div>
      </section>
      {isLoading ? <div className="grid gap-3 md:grid-cols-2">{Array.from({ length: 8 }, (_, index) => <div key={index} className="surface-quiet h-36 animate-pulse" />)}</div> : isError ? <div role="alert" className="surface-quiet p-8 text-center"><p className="font-semibold text-white">Fixtures could not be loaded</p><p className="mt-1 text-sm text-[var(--muted)]">The match service may be temporarily unavailable. Try again in a moment.</p></div> : matches.length ? <div className="grid gap-3 md:grid-cols-2">{matches.map((match) => <MatchCard key={match.id} match={match} />)}</div> : <div className="surface-quiet p-12 text-center"><CalendarDays className="mx-auto text-[var(--subtle)]" size={22} /><p className="mt-3 font-semibold text-white">No matches match these filters</p><p className="mt-1 text-sm text-[var(--muted)]">Clear one or more filters to see more fixtures.</p></div>}
      {totalPages > 1 && <nav className="mt-8 flex items-center justify-center gap-3" aria-label="Match pages"><button className="button-secondary" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>Previous</button><span className="px-2 text-xs tabular-nums text-[var(--muted)]">Page {page} of {totalPages}</span><button className="button-secondary" disabled={page >= totalPages} onClick={() => setPage((current) => Math.min(totalPages, current + 1))}>Next</button></nav>}
    </main>
  )
}

function MatchesContent() {
  const query = useSearchParams()
  const initialTeam = query.get('team_id') || ''
  return <MatchesView key={initialTeam} initialTeam={initialTeam} />
}

export default function MatchesPage() {
  return <Suspense fallback={<main className="page-frame py-12"><div className="surface-quiet h-48 animate-pulse" /></main>}><MatchesContent /></Suspense>
}
