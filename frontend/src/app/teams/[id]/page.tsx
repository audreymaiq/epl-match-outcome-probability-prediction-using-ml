'use client'

import { useParams } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, ArrowRight, MapPin, Search, Trophy } from 'lucide-react'
import { useTeam, useTeamForm, useTeamStats } from '@/lib/hooks'
import { FormBadges } from '@/components/form-badges'
import { TeamMark } from '@/components/team-mark'
import type { TeamSplitStats } from '@/lib/types'

function SplitCard({ title, stats }: { title: string; stats?: TeamSplitStats }) {
  if (!stats) return null
  const cells = [
    ['P', stats.played], ['W', stats.wins], ['D', stats.draws], ['L', stats.losses],
    ['GF', stats.goals_scored], ['GA', stats.goals_conceded],
    ['GD', stats.goal_difference > 0 ? `+${stats.goal_difference}` : stats.goal_difference],
    ['Pts', stats.points], ['Win %', `${(stats.win_rate * 100).toFixed(0)}%`],
  ]
  return <section className="surface-quiet overflow-hidden"><h3 className="px-4 pt-4 text-sm font-bold text-white">{title}</h3><div className="overflow-x-auto"><table className="mt-3 min-w-[620px] w-full text-center text-xs"><thead><tr className="border-b border-[var(--border)] text-[0.62rem] uppercase tracking-wide text-[var(--muted)]">{cells.map(([label]) => <th key={String(label)} scope="col" className="px-3 py-2 font-semibold">{label}</th>)}</tr></thead><tbody><tr>{cells.map(([label, value]) => <td key={String(label)} className={`px-3 py-3 font-mono font-bold tabular-nums ${label === 'Pts' ? 'text-[var(--pl-green)]' : 'text-white'}`}>{value}</td>)}</tr></tbody></table></div></section>
}

export default function TeamDetailPage() {
  const params = useParams()
  const teamId = Number(params.id)
  const { data: team, isLoading, isError } = useTeam(teamId)
  const { data: form } = useTeamForm(teamId)
  const { data: statsData } = useTeamStats(teamId)

  if (isLoading) return <main className="page-frame space-y-4 py-12"><div className="surface-quiet h-48 animate-pulse" /><div className="surface-quiet h-48 animate-pulse" /></main>
  if (isError || !team) return <main className="page-frame py-16 text-center"><p className="text-lg font-bold text-white">Club profile unavailable</p><p className="mt-2 text-sm text-[var(--muted)]">Check the club link or try again shortly.</p><Link className="button-secondary mt-5" href="/teams"><ArrowLeft size={14} /> All clubs</Link></main>

  return (
    <main className="page-frame pb-16 pt-8 sm:pt-12">
      <Link href="/teams" className="mb-6 inline-flex items-center gap-2 text-xs font-semibold text-[var(--muted)] hover:text-white"><ArrowLeft size={14} /> All clubs</Link>
      <section className="surface mb-6 overflow-hidden p-5 sm:p-8"><div className="flex flex-col gap-6 sm:flex-row sm:items-center"><TeamMark team={team} size="lg" /><div className="min-w-0 flex-1"><p className="eyebrow">Club profile</p><h1 className="mt-2 text-3xl font-extrabold tracking-tight text-white sm:text-4xl">{team.name}</h1><div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-xs text-[var(--muted)]">{team.short_name && <span>{team.short_name}</span>}{team.established_year && <span>Founded {team.established_year}</span>}{team.stadium_name && <span className="inline-flex items-center gap-1.5"><MapPin size={13} />{team.stadium_name}</span>}{team.stadium_capacity != null && <span>Capacity {team.stadium_capacity.toLocaleString()}</span>}</div></div><Link className="button-primary" href={`/matches?team_id=${team.id}`}>View fixtures <ArrowRight size={15} /></Link></div></section>
      {statsData && <section className="mb-6"><div className="mb-4 flex items-end justify-between"><div><p className="eyebrow">Season report</p><h2 className="mt-2 text-xl font-bold text-white">{statsData.season?.name || 'Season'} statistics</h2></div><Trophy size={18} className="text-[var(--pl-green)]" /></div><div className="space-y-3"><SplitCard title="Overall" stats={statsData.overall} /><div className="grid gap-3 lg:grid-cols-2"><SplitCard title="Home" stats={statsData.home} /><SplitCard title="Away" stats={statsData.away} /></div></div></section>}
      {form?.form?.length ? <section className="surface p-5 sm:p-6"><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="eyebrow">Recent results</p><h2 className="mt-2 text-xl font-bold text-white">Last five matches</h2></div><div className="text-right"><p className="font-mono text-lg font-bold text-[var(--pl-green)]">{form.points_last_5} pts</p><p className="text-[0.65rem] text-[var(--muted)]">{form.form_string}</p></div></div><div className="mt-4"><FormBadges form={form.form.map((entry) => entry.outcome).join('')} /></div><div className="mt-5 divide-y divide-white/[0.07]">{form.form.slice(0, 5).map((entry) => <Link key={entry.match_id} href={`/matches/${entry.match_id}`} className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0"><span className="w-16 shrink-0 text-xs text-[var(--muted)]">{new Date(entry.match_date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}</span><span className="min-w-0 flex-1 truncate text-xs font-medium text-white">{entry.location === 'Home' ? 'vs' : 'at'} {entry.opponent_name}</span><span className="font-mono text-xs font-bold tabular-nums text-white">{entry.goals_scored} : {entry.goals_conceded}</span><span className={`grid h-7 w-7 shrink-0 place-items-center rounded-lg text-xs font-bold ${entry.outcome === 'W' ? 'bg-[rgba(139,240,178,.12)] text-[var(--pl-green)]' : entry.outcome === 'D' ? 'bg-[rgba(244,200,106,.12)] text-[var(--warning)]' : 'bg-[rgba(255,139,145,.12)] text-[var(--danger)]'}`}>{entry.outcome}</span></Link>)}</div></section> : <section className="surface-quiet p-5"><p className="text-sm font-semibold text-white">Recent form unavailable</p><p className="mt-1 text-xs text-[var(--muted)]">No completed matches have been recorded for this season.</p></section>}
      {!statsData && <p className="mt-5 text-center text-xs text-[var(--subtle)]"><Search className="mr-1 inline" size={13} />Season statistics are not available right now.</p>}
    </main>
  )
}
