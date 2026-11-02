'use client'

import Link from 'next/link'
import { useMemo, useState } from 'react'
import { Search, Shield, ArrowUpRight } from 'lucide-react'
import { useTeams } from '@/lib/hooks'
import { PageHeading } from '@/components/page-heading'
import { TeamMark } from '@/components/team-mark'
import type { Team } from '@/lib/types'

export default function TeamsPage() {
  const [search, setSearch] = useState('')
  const { data, isLoading, isError } = useTeams()
  const teams = data?.data ?? []
  const totalTeams = data?.pagination.total
  const filteredTeams = useMemo(() => teams.filter((team: Team) => team.name.toLowerCase().includes(search.trim().toLowerCase())), [search, teams])

  return (
    <main className="page-frame pb-16 pt-8 sm:pt-12">
      <PageHeading eyebrow="Premier League" title="Clubs" description="Open a club profile to view recent form, season statistics and fixtures." action={totalTeams != null ? <div className="border-l border-[var(--border)] pl-4 text-right"><p className="font-mono text-lg font-bold text-white">{totalTeams}</p><p className="text-[0.65rem] text-[var(--muted)]">clubs</p></div> : undefined} />
      <div className="mb-6 max-w-md"><label className="relative block"><span className="sr-only">Search clubs</span><Search size={16} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--subtle)]" /><input className="field-control pl-10" type="search" placeholder="Find a club" value={search} onChange={(event) => setSearch(event.target.value)} /></label></div>
      {isLoading ? <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">{Array.from({ length: 12 }, (_, index) => <div key={index} className="surface-quiet h-40 animate-pulse" />)}</div> : isError ? <div role="alert" className="surface-quiet p-8 text-center text-sm text-[var(--danger)]">Club data could not be loaded. Please try again shortly.</div> : filteredTeams.length ? <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">{filteredTeams.map((team: Team) => <Link key={team.id} href={`/teams/${team.id}`} className="surface-quiet group flex min-h-40 flex-col justify-between overflow-hidden p-4 transition-colors hover:border-white/20 hover:bg-[var(--surface-raised)] sm:p-5"><TeamMark team={team} size="lg" /><div className="mt-5 flex items-end justify-between gap-2"><div className="min-w-0"><p className="truncate text-sm font-bold text-white">{team.name}</p><p className="mt-1 truncate text-[0.68rem] text-[var(--muted)]">{team.stadium_name || team.short_name || 'Premier League club'}</p></div><ArrowUpRight size={15} className="shrink-0 text-[var(--subtle)] transition group-hover:text-[var(--pl-green)]" /></div></Link>)}</div> : <div className="surface-quiet p-12 text-center"><Shield className="mx-auto text-[var(--subtle)]" /><p className="mt-3 font-semibold text-white">No clubs found</p><p className="mt-1 text-sm text-[var(--muted)]">Try a different search.</p></div>}
    </main>
  )
}
