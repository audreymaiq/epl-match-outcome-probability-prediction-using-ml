'use client'

import { useParams } from 'next/navigation'
import Link from 'next/link'
import { useTeam, useTeamForm, useTeamStats } from '@/lib/hooks'
import { FormBadges } from '@/components/form-badges'
import type { TeamSplitStats } from '@/lib/types'

function StatsTable({ label, stats }: { label: string; stats?: TeamSplitStats }) {
  if (!stats) return null
  const rows = [
    ['P', stats.played],
    ['W', stats.wins],
    ['D', stats.draws],
    ['L', stats.losses],
    ['GF', stats.goals_scored],
    ['GA', stats.goals_conceded],
    ['GD', stats.goal_difference > 0 ? `+${stats.goal_difference}` : stats.goal_difference],
    ['Pts', stats.points],
    ['Win %', `${(stats.win_rate * 100).toFixed(0)}%`],
  ]

  return (
    <div className="bg-white/5 border border-white/10 rounded-xl p-4">
      <h3 className="text-xs font-bold text-white/50 uppercase tracking-widest mb-3">{label}</h3>
      <div className="grid grid-cols-9 gap-1 text-center">
        {rows.map(([k, v]) => (
          <div key={String(k)} className="flex flex-col items-center">
            <span className="text-[9px] text-white/30 mb-1">{k}</span>
            <span className={`text-sm font-bold ${
              k === 'Pts' ? 'text-[#00ff85]' :
              k === 'GD' && Number(stats.goal_difference) > 0 ? 'text-green-400' :
              k === 'GD' && Number(stats.goal_difference) < 0 ? 'text-red-400' :
              'text-white'
            }`}>{v}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function TeamDetailPage() {
  const params = useParams()
  const teamId = Number(params.id)

  const { data: team, isLoading, isError } = useTeam(teamId)
  const { data: form } = useTeamForm(teamId)
  const { data: statsData } = useTeamStats(teamId)

  if (isLoading) {
    return (
      <main className="max-w-4xl mx-auto px-4 py-8 space-y-4">
        <div className="animate-pulse space-y-4">
          <div className="h-28 bg-white/5 rounded-2xl" />
          <div className="h-36 bg-white/5 rounded-2xl" />
          <div className="h-36 bg-white/5 rounded-2xl" />
        </div>
      </main>
    )
  }

  if (isError || !team) {
    return (
      <main className="max-w-4xl mx-auto px-4 py-8 text-center">
        <p className="text-red-400">Team not found.</p>
        <Link href="/teams" className="text-[#00ff85] text-sm mt-2 inline-block hover:underline">← Back to Teams</Link>
      </main>
    )
  }

  return (
    <main className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      <Link href="/teams" className="text-xs text-white/40 hover:text-white/70 transition-colors">
        ← Back to Teams
      </Link>

      {/* Header */}
      <div className="bg-white/5 border border-white/10 rounded-2xl p-6 flex items-center gap-5">
        <div className="w-16 h-16 rounded-full bg-[#3d195b] border-2 border-[#00ff85]/30 flex items-center justify-center text-white font-extrabold text-xl shrink-0">
          {team.short_name?.slice(0, 3) ?? team.name.slice(0, 3).toUpperCase()}
        </div>
        <div>
          <h1 className="text-2xl font-extrabold text-white">{team.name}</h1>
          {team.short_name && <p className="text-sm text-white/40">{team.short_name}</p>}
          <div className="flex gap-4 mt-2 text-xs text-white/30">
            {team.established_year && <span>Est. {team.established_year}</span>}
            {team.stadium_name && <span>🏟 {team.stadium_name}</span>}
            {team.stadium_capacity && <span>Capacity: {team.stadium_capacity.toLocaleString()}</span>}
          </div>
        </div>
      </div>

      {/* Season stats */}
      {statsData && (
        <div className="space-y-3">
          <h2 className="text-sm font-bold text-white/50 uppercase tracking-widest">
            Season Statistics - {statsData.season?.name ?? 'Current'}
          </h2>
          <StatsTable label="Overall" stats={statsData.overall} />
          <div className="grid md:grid-cols-2 gap-3">
            <StatsTable label="Home" stats={statsData.home} />
            <StatsTable label="Away" stats={statsData.away} />
          </div>
        </div>
      )}

      {/* Recent Form */}
      {form?.form && form.form.length > 0 && (
        <div className="bg-white/5 border border-white/10 rounded-2xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-white/70">Recent Form</h2>
            <span className="text-xs text-white/30">{form.form_string} ({form.points_last_5} pts)</span>
          </div>
          <FormBadges form={form.form.map(f => f.outcome).join('')} />
          <div className="mt-4 space-y-1.5">
            {form.form.slice(0, 5).map((f) => (
              <div key={f.match_id} className="flex items-center justify-between text-xs bg-white/5 rounded-lg px-3 py-2">
                <span className="text-white/30">{new Date(f.match_date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}</span>
                <span className="text-white/60">{f.location === 'Home' ? 'vs' : '@'} {f.opponent_name}</span>
                <span className="text-white font-semibold">{f.goals_scored}–{f.goals_conceded}</span>
                <span className={`w-5 h-5 rounded-full flex items-center justify-center font-bold text-[10px] ${
                  f.outcome === 'W' ? 'bg-green-500/20 text-green-400' :
                  f.outcome === 'D' ? 'bg-yellow-500/20 text-yellow-400' :
                  'bg-red-500/20 text-red-400'
                }`}>{f.outcome}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* H2H link */}
      <div className="bg-white/5 border border-white/10 rounded-2xl p-5 text-center">
        <p className="text-sm text-white/50 mb-3">Compare with another team</p>
        <Link
          href={`/matches?team_id=${teamId}`}
          className="inline-block bg-[#00ff85] text-[#3d195b] font-bold px-6 py-2.5 rounded-lg text-sm hover:bg-[#00ff85]/90 transition-all"
        >
          View All {team.name} Matches
        </Link>
      </div>
    </main>
  )
}
