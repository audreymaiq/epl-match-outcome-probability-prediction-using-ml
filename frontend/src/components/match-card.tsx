import Link from 'next/link'
import type { MatchListItem } from '@/lib/types'
import { TeamMark } from '@/components/team-mark'

const dateFormat: Intl.DateTimeFormatOptions = { weekday: 'short', day: 'numeric', month: 'short' }

export function MatchCard({ match }: { match: MatchListItem }) {
  const finished = match.status === 'FINISHED'
  const postponed = match.status === 'POSTPONED'
  const date = new Date(match.match_datetime)
  return (
    <Link href={`/matches/${match.id}`} className="surface-quiet group block p-4 transition-colors hover:border-white/20 hover:bg-[var(--surface-raised)] sm:p-5">
      <div className="mb-4 flex items-center justify-between gap-3 border-b border-[var(--border)] pb-2.5">
        <span className="text-[0.68rem] font-semibold text-[var(--muted)]">{match.match_week ? `Matchweek ${match.match_week}` : match.season_name}</span>
        <span className={`text-[0.62rem] font-bold uppercase tracking-wider ${finished ? 'text-[var(--muted)]' : postponed ? 'text-[var(--warning)]' : 'text-[var(--pl-green)]'}`}>
          {postponed ? 'Postponed' : finished ? 'Full time' : 'Scheduled'}
        </span>
      </div>
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 sm:gap-4">
        <div className="flex min-w-0 items-center gap-2 sm:gap-3">
          <TeamMark team={match.home_team} size="sm" />
          <span className="truncate text-sm font-bold text-white">{match.home_team.short_name || match.home_team.name}</span>
        </div>
        <div className="min-w-[3.75rem] text-center">
          {finished ? <span className="font-mono text-xl font-extrabold tabular-nums text-white">{match.home_goals ?? 0}<span className="px-1.5 text-[var(--subtle)]">:</span>{match.away_goals ?? 0}</span> : <span className="text-xs font-bold uppercase tracking-widest text-[var(--subtle)]">{postponed ? 'TBD' : 'vs'}</span>}
        </div>
        <div className="flex min-w-0 flex-row-reverse items-center gap-2 text-right sm:gap-3">
          <TeamMark team={match.away_team} size="sm" />
          <span className="truncate text-sm font-bold text-white">{match.away_team.short_name || match.away_team.name}</span>
        </div>
      </div>
      <div className="mt-4 flex items-center justify-between text-xs text-[var(--muted)]">
        <time dateTime={match.match_datetime}>{Number.isNaN(date.getTime()) ? 'Date to be confirmed' : `${date.toLocaleDateString('en-GB', dateFormat)}${finished || postponed ? '' : ` · ${date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}`}`}</time>
        <span className="text-[0.62rem] text-[var(--subtle)] group-hover:text-[var(--pl-green)]">View match</span>
      </div>
    </Link>
  )
}
