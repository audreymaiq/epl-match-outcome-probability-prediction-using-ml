'use client'

import { useParams } from 'next/navigation'
import Link from '@/components/competition-link'
import { useEffect, useState } from 'react'
import { useMatch, usePredict } from '@/lib/hooks'
import { ProbabilityBars } from '@/components/probability-bars'
import { TeamMark } from '@/components/team-mark'
import { ArrowLeft, MapPin, UserRound, UsersRound } from 'lucide-react'

function MatchStat({ label, home, away }: { label: string; home?: number | string | null; away?: number | string | null }) {
  return <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 border-b border-[var(--border)] py-3 last:border-0"><span className="text-right font-mono text-sm font-bold tabular-nums text-white">{home ?? '—'}</span><span className="min-w-28 text-center text-xs text-[var(--muted)]">{label}</span><span className="font-mono text-sm font-bold tabular-nums text-white">{away ?? '—'}</span></div>
}

export default function MatchDetailPage() {
  const params = useParams()
  const matchId = Number(params.id)
  const { data: match, isLoading, isError } = useMatch(matchId)
  const prediction = usePredict()
  const [currentTime, setCurrentTime] = useState<number | null>(null)

  useEffect(() => {
    const updateTime = () => setCurrentTime(Date.now())
    const initialUpdate = window.setTimeout(updateTime, 0)
    const interval = window.setInterval(updateTime, 60_000)
    return () => {
      window.clearTimeout(initialUpdate)
      window.clearInterval(interval)
    }
  }, [])

  if (isLoading) return <main className="page-frame space-y-4 py-12"><div className="surface-quiet h-56 animate-pulse" /><div className="surface-quiet h-64 animate-pulse" /></main>
  if (isError || !match) return <main className="page-frame py-16 text-center"><p className="text-lg font-bold text-white">Match could not be found</p><p className="mt-2 text-sm text-[var(--muted)]">The fixture may have been removed or the match service is unavailable.</p><Link className="button-secondary mt-5" href="/matches"><ArrowLeft size={14} /> Back to fixtures</Link></main>

  const finished = match.status === 'FINISHED'
  const matchDate = new Date(match.match_datetime)
  const canPredict = match.status === 'SCHEDULED' && currentTime !== null && matchDate.getTime() > currentTime
  return (
    <main className="page-frame pb-16 pt-8 sm:pt-12">
      <Link href="/matches" className="mb-6 inline-flex items-center gap-2 text-xs font-semibold text-[var(--muted)] transition hover:text-white"><ArrowLeft size={14} /> All fixtures</Link>
      <section className="relative overflow-hidden border-y border-white/[0.12] bg-[var(--surface)] px-5 py-8 sm:px-10 sm:py-10">
        <p className="eyebrow justify-center">{match.season_name}{match.match_week ? ` · Matchweek ${match.match_week}` : ''} · {finished ? 'Full time' : match.status.toLowerCase()}</p>
        <div className="mx-auto mt-8 grid max-w-4xl grid-cols-[1fr_auto_1fr] items-center gap-3 sm:gap-8"><div className="flex flex-col items-center gap-3 text-center sm:flex-row sm:text-left"><TeamMark team={match.home_team} size="lg" /><div><p className="text-base font-bold text-white sm:text-xl">{match.home_team.name}</p><p className="mt-1 text-xs text-[var(--muted)]">Home</p></div></div><div className="rounded-2xl border border-white/[0.1] bg-black/15 px-4 py-3 text-center sm:px-6">{finished ? <p className="font-mono text-3xl font-extrabold tabular-nums text-white sm:text-4xl">{match.home_goals ?? 0}<span className="px-2 text-[var(--subtle)]">:</span>{match.away_goals ?? 0}</p> : <p className="font-mono text-xl font-bold text-[var(--subtle)]">VS</p>}<p className="mt-1.5 text-[0.62rem] font-bold uppercase tracking-wider text-[var(--muted)]">{Number.isNaN(matchDate.getTime()) ? 'Date TBC' : matchDate.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}</p></div><div className="flex flex-col items-center gap-3 text-center sm:flex-row-reverse sm:text-right"><TeamMark team={match.away_team} size="lg" /><div><p className="text-base font-bold text-white sm:text-xl">{match.away_team.name}</p><p className="mt-1 text-xs text-[var(--muted)]">Away</p></div></div></div>
      </section>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <section className="surface p-5 sm:p-6"><div className="mb-5"><h2 className="text-lg font-bold text-white">Outcome probabilities</h2></div>{prediction.data ? <><ProbabilityBars probabilities={prediction.data.probabilities} predicted_outcome={prediction.data.predicted_outcome} homeTeam={match.home_team.name} awayTeam={match.away_team.name} /><div className="mt-5 flex flex-wrap justify-between gap-3 border-t border-[var(--border)] pt-4 text-xs"><span className="text-[var(--muted)]">Model confidence</span><span className="font-mono font-bold text-[var(--pl-green)]">{(prediction.data.confidence * 100).toFixed(0)}%</span><span className="text-[var(--muted)]">Version {prediction.data.model_version}</span></div></> : <div className="border-y border-dashed border-white/[0.12] py-6 text-center"><p className="text-sm text-[var(--muted)]">{canPredict ? 'Generate an estimate for this fixture.' : 'Pre-match predictions are available only for upcoming fixtures.'}</p>{canPredict && <button className="button-primary mt-4" disabled={prediction.isPending} onClick={() => prediction.mutate({ match_id: match.id })}>{prediction.isPending ? 'Calculating…' : 'Generate prediction'}</button>}{prediction.isError && <p role="alert" className="mt-3 text-xs text-[var(--danger)]">{(prediction.error as Error)?.message || 'Prediction service unavailable.'}</p>}</div>}<p className="mt-4 text-[0.68rem] leading-5 text-[var(--subtle)]">Probabilities are estimates and do not guarantee a match result.</p></section>
        <section className="surface p-5 sm:p-6"><h2 className="mb-4 text-lg font-bold text-white">Match information</h2><div className="space-y-4">{match.stadium?.name && <div className="flex gap-3"><MapPin size={16} className="mt-0.5 text-[var(--pl-green)]" /><div><p className="text-xs font-semibold text-white">{match.stadium.name}</p><p className="mt-1 text-xs text-[var(--muted)]">{match.stadium.city || 'Venue'}{match.stadium.capacity ? ` · Capacity ${match.stadium.capacity.toLocaleString()}` : ''}</p></div></div>}{match.referee?.name && <div className="flex gap-3"><UserRound size={16} className="mt-0.5 text-[var(--pl-green)]" /><div><p className="text-xs font-semibold text-white">{match.referee.name}</p><p className="mt-1 text-xs text-[var(--muted)]">Match official</p></div></div>}{match.attendance != null && <div className="flex gap-3"><UsersRound size={16} className="mt-0.5 text-[var(--pl-green)]" /><div><p className="text-xs font-semibold text-white">{match.attendance.toLocaleString()}</p><p className="mt-1 text-xs text-[var(--muted)]">Attendance</p></div></div>}{!match.stadium?.name && !match.referee?.name && match.attendance == null && <p className="text-sm text-[var(--muted)]">No additional match information is available.</p>}</div></section>
      </div>
      {finished && [match.home_possession, match.away_possession, match.home_shots, match.away_shots, match.home_shots_on_target, match.away_shots_on_target, match.home_corners, match.away_corners].some((value) => value != null) && <section className="surface mt-5 p-5 sm:p-6"><p className="eyebrow">By the numbers</p><h2 className="mb-4 mt-2 text-xl font-bold text-white">Match statistics</h2>{match.home_possession != null && <MatchStat label="Possession" home={`${match.home_possession}%`} away={match.away_possession != null ? `${match.away_possession}%` : null} />}{match.home_shots != null && <MatchStat label="Shots" home={match.home_shots} away={match.away_shots} />}{match.home_shots_on_target != null && <MatchStat label="Shots on target" home={match.home_shots_on_target} away={match.away_shots_on_target} />}{match.home_corners != null && <MatchStat label="Corners" home={match.home_corners} away={match.away_corners} />}</section>}
    </main>
  )
}
