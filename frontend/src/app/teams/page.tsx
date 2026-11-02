'use client'

import Link from 'next/link'
import { useTeams } from '@/lib/hooks'
import type { Team } from '@/lib/types'

const EPL_COLORS: Record<string, string> = {
  'Arsenal': '#EF0107',
  'Chelsea': '#034694',
  'Liverpool': '#C8102E',
  'Manchester City': '#6CABDD',
  'Manchester United': '#DA291C',
  'Tottenham': '#132257',
  'Newcastle': '#241F20',
  'Aston Villa': '#95BFE5',
  'Brighton': '#0057B8',
  'West Ham': '#7A263A',
  'Brentford': '#E30613',
  'Fulham': '#CC0000',
  'Crystal Palace': '#1B458F',
  'Wolves': '#FDB913',
  'Nottingham Forest': '#DD0000',
  'Everton': '#003399',
  'Bournemouth': '#DA291C',
  'Southampton': '#D71920',
  'Ipswich': '#3A64A3',
  'Leicester': '#003090',
}

function TeamCard({ team }: { team: Team }) {
  const accentColor = EPL_COLORS[team.name] ?? '#3d195b'

  return (
    <Link href={`/teams/${team.id}`}>
      <div className="bg-white/5 border border-white/10 rounded-2xl p-5 hover:bg-white/10 hover:border-white/20 transition-all group cursor-pointer flex flex-col items-center gap-3 text-center">
        <div
          className="w-16 h-16 rounded-full flex items-center justify-center text-white font-extrabold text-xl shadow-lg group-hover:scale-105 transition-transform"
          style={{ backgroundColor: accentColor }}
        >
          {team.short_name?.slice(0, 3) ?? team.name.slice(0, 3).toUpperCase()}
        </div>

        <div>
          <p className="text-sm font-bold text-white group-hover:text-[#00ff85] transition-colors">
            {team.name}
          </p>
          {team.short_name && (
            <p className="text-[10px] text-white/30 mt-0.5">{team.short_name}</p>
          )}
        </div>

        <span className="text-[10px] text-[#00ff85] opacity-0 group-hover:opacity-100 transition-opacity">
          View details →
        </span>
      </div>
    </Link>
  )
}

export default function TeamsPage() {
  const { data: teamsPage, isLoading, isError } = useTeams()
  const teams = teamsPage?.data ?? []

  return (
    <main className="max-w-6xl mx-auto px-4 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Premier League Teams</h1>
        {teams.length > 0 && (
          <span className="text-xs text-white/30">{teams.length} teams</span>
        )}
      </div>

      {isLoading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {Array.from({ length: 20 }).map((_, i) => (
            <div key={i} className="bg-white/5 border border-white/10 rounded-2xl h-36 animate-pulse" />
          ))}
        </div>
      ) : isError ? (
        <div className="text-center py-16 text-red-400">Failed to load teams. API may be offline.</div>
      ) : teams.length ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {teams.map((t: Team) => <TeamCard key={t.id} team={t} />)}
        </div>
      ) : (
        <div className="text-center py-16 text-white/30">No teams found.</div>
      )}
    </main>
  )
}
