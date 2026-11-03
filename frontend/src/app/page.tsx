'use client'

import Link from 'next/link'
import { useState } from 'react'
import { ArrowRight, CalendarDays, ChevronRight } from 'lucide-react'
import { useMatches, useTeams, usePredict, useModelInfo, useSeasons } from '@/lib/hooks'
import { MatchCard } from '@/components/match-card'
import { ProbabilityBars } from '@/components/probability-bars'
import type { Team } from '@/lib/types'

function defaultKickoff() {
  const date = new Date()
  date.setDate(date.getDate() + 1)
  date.setHours(15, 0, 0, 0)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}T${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function MatchEstimator() {
  const { data: teamsPage, isLoading: teamsLoading } = useTeams()
  const { data: modelInfo } = useModelInfo()
  const { data: seasons = [] } = useSeasons()
  const modelReady = modelInfo?.status === 'loaded'
  const teams = teamsPage?.data ?? []
  const prediction = usePredict()
  const [homeId, setHomeId] = useState('')
  const [awayId, setAwayId] = useState('')
  const [matchDate, setMatchDate] = useState(defaultKickoff)
  const [seasonName, setSeasonName] = useState('')
  const [matchWeek, setMatchWeek] = useState('1')
  const selectedSeason = seasons.includes(seasonName) ? seasonName : seasons[0] || ''

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!modelReady || !homeId || !awayId || homeId === awayId || !selectedSeason || !matchWeek) return
    const kickoff = new Date(matchDate)
    if (!Number.isFinite(kickoff.getTime()) || kickoff.getTime() <= Date.now()) return
    prediction.mutate({
      home_team_id: Number(homeId),
      away_team_id: Number(awayId),
      match_datetime: kickoff.toISOString(),
      season_name: selectedSeason,
      match_week: Number(matchWeek),
    })
  }

  return (
    <section className="surface p-5 sm:p-6" aria-labelledby="estimator-title">
      <div className="mb-5 border-b border-[var(--border)] pb-4">
        <p className="eyebrow">Match estimator</p>
        <h2 id="estimator-title" className="mt-2 text-lg font-bold text-white">Estimate an outcome</h2>
        <p className="mt-1 text-xs leading-5 text-[var(--muted)]">Choose two clubs to see the model&apos;s probabilities.</p>
      </div>
      <form onSubmit={submit} className="space-y-3">
        <label className="block space-y-1.5"><span className="data-label">Home club</span><select className="field-control" value={homeId} onChange={(event) => { setHomeId(event.target.value); prediction.reset() }} required disabled={teamsLoading}><option value="">{teamsLoading ? 'Loading clubs…' : 'Select a club'}</option>{teams.map((team: Team) => <option key={team.id} value={team.id}>{team.name}</option>)}</select></label>
        <label className="block space-y-1.5"><span className="data-label">Away club</span><select className="field-control" value={awayId} onChange={(event) => { setAwayId(event.target.value); prediction.reset() }} required disabled={teamsLoading}><option value="">Select a club</option>{teams.filter((team: Team) => String(team.id) !== homeId).map((team: Team) => <option key={team.id} value={team.id}>{team.name}</option>)}</select></label>
        <label className="block space-y-1.5"><span className="data-label">Kickoff in your time zone</span><input className="field-control" type="datetime-local" value={matchDate} onChange={(event) => { setMatchDate(event.target.value); prediction.reset() }} required /></label>
        <label className="block space-y-1.5"><span className="data-label">Season</span><select className="field-control" value={selectedSeason} onChange={(event) => { setSeasonName(event.target.value); prediction.reset() }} required disabled={!seasons.length}><option value="">Select a season</option>{seasons.map((season) => <option key={season} value={season}>{season}</option>)}</select></label>
        <label className="block space-y-1.5"><span className="data-label">Matchweek</span><input className="field-control" type="number" min="1" max="38" value={matchWeek} onChange={(event) => { setMatchWeek(event.target.value); prediction.reset() }} required /></label>
        <button className="button-primary w-full" type="submit" disabled={!modelReady || !homeId || !awayId || !selectedSeason || !matchWeek || prediction.isPending}>{prediction.isPending ? 'Calculating…' : modelReady ? 'Show probabilities' : 'Model not installed'}<ArrowRight size={15} /></button>
      </form>
      {prediction.isError && <p role="alert" className="mt-4 border-l-2 border-[var(--danger)] bg-[rgba(255,139,145,.07)] p-3 text-xs leading-5 text-[var(--danger)]">The estimate could not be generated. The prediction service may be unavailable.</p>}
      {prediction.data && <div className="mt-5 border-t border-[var(--border)] pt-5"><div className="mb-4 flex items-baseline justify-between gap-3"><div><p className="data-label">Most likely result</p><p className="mt-1 text-sm font-bold text-white">{prediction.data.predicted_outcome === 'H' ? `${prediction.data.home_team_name} win` : prediction.data.predicted_outcome === 'A' ? `${prediction.data.away_team_name} win` : 'Draw'}</p></div><span className="font-mono text-sm font-bold tabular-nums text-[var(--pl-green)]">{(prediction.data.confidence * 100).toFixed(0)}%</span></div><ProbabilityBars probabilities={prediction.data.probabilities} predicted_outcome={prediction.data.predicted_outcome} homeTeam={prediction.data.home_team_name} awayTeam={prediction.data.away_team_name} compact /><p className="mt-4 text-[0.68rem] leading-5 text-[var(--subtle)]">Estimates are based on historical data and do not guarantee a result.</p></div>}
    </section>
  )
}

export default function HomePage() {
  const { data, isLoading, isError } = useMatches({ status: 'SCHEDULED', page_size: 6 })
  const matches = data?.data ?? []

  return (
    <main className="page-frame pb-16 pt-7 sm:pt-10">
      <section className="mb-9 border-y border-white/[0.12] py-7 sm:py-9">
        <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
          <div>
            <p className="eyebrow">England · Premier League</p>
            <h1 className="mt-3 text-4xl font-extrabold leading-none tracking-[-0.045em] text-white sm:text-6xl">Match centre</h1>
            <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--muted)]">Fixtures, results and match outcome probabilities for the Premier League.</p>
          </div>
          <Link href="/matches" className="button-secondary self-start sm:self-auto">All fixtures <ArrowRight size={15} /></Link>
        </div>
      </section>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
        <section aria-labelledby="fixtures-title">
          <div className="mb-4 flex items-end justify-between gap-4 border-b border-[var(--border)] pb-3"><div><p className="eyebrow">Schedule</p><h2 id="fixtures-title" className="mt-1.5 text-xl font-bold text-white">Upcoming fixtures</h2></div><Link href="/matches" className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--pl-green)] hover:text-white">Full list <ChevronRight size={14} /></Link></div>
          {isLoading ? <div className="grid gap-3 sm:grid-cols-2">{Array.from({ length: 4 }, (_, index) => <div key={index} className="surface-quiet h-36 animate-pulse" />)}</div> : isError ? <div className="surface-quiet p-6 text-sm text-[var(--danger)]">Fixtures could not be loaded. Please try again shortly.</div> : matches.length ? <div className="grid gap-3 sm:grid-cols-2">{matches.map((match) => <MatchCard key={match.id} match={match} />)}</div> : <div className="surface-quiet p-8 text-center"><CalendarDays className="mx-auto text-[var(--subtle)]" size={20} /><p className="mt-3 text-sm font-semibold text-white">No upcoming fixtures</p><p className="mt-1 text-xs text-[var(--muted)]">View the full schedule for completed and postponed matches.</p><Link href="/matches" className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-[var(--pl-green)]">Browse fixtures <ArrowRight size={13} /></Link></div>}
        </section>
        <aside><MatchEstimator /></aside>
      </div>
      <p className="mt-10 border-t border-[var(--border)] pt-4 text-center text-[0.68rem] leading-5 text-[var(--subtle)]">Match outcome probabilities are estimates, not guarantees.</p>
    </main>
  )
}
