'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useMatches } from '@/lib/hooks'
import { ProbabilityBars } from '@/components/probability-bars'
import type { MatchListItem, MatchesParams } from '@/lib/types'

const SEASONS = [
  { value: '2024/25', label: '2024/25' },
  { value: '2023/24', label: '2023/24' },
  { value: '2022/23', label: '2022/23' },
]

const STATUS_OPTIONS = [
  { value: '', label: 'All Matches' },
  { value: 'SCHEDULED', label: 'Upcoming' },
  { value: 'FINISHED', label: 'Finished' },
]

function StatusBadge({ status }: { status: string }) {
  const cfg: Record<string, string> = {
    SCHEDULED: 'bg-[#00ff85]/20 text-[#00ff85] border-[#00ff85]/30',
    LIVE: 'bg-red-500/20 text-red-400 border-red-500/30',
    FINISHED: 'bg-white/10 text-white/40 border-white/10',
    POSTPONED: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  }
  return (
    <span className={`text-[9px] font-bold uppercase px-2 py-0.5 rounded-full border ${cfg[status] ?? 'bg-white/10 text-white/40'}`}>
      {status}
    </span>
  )
}

function MatchRow({ match }: { match: MatchListItem }) {
  const isFinished = match.status === 'FINISHED'
  return (
    <Link href={`/matches/${match.id}`}>
      <div className="bg-white/5 border border-white/10 rounded-xl p-4 hover:bg-white/10 transition-all">
        <div className="flex items-center justify-between gap-4">
          {/* GW + Status */}
          <div className="flex flex-col items-center gap-1 min-w-[44px]">
            <span className="text-[10px] text-white/30 font-medium">GW{match.match_week}</span>
            <StatusBadge status={match.status} />
          </div>

          {/* Teams */}
          <div className="flex-1 flex items-center gap-3 min-w-0">
            <span className="text-sm font-semibold text-white text-right flex-1 truncate">
              {match.home_team.name}
            </span>
            <div className="text-center min-w-[52px] shrink-0">
              {isFinished ? (
                <span className="text-base font-bold text-white">
                  {match.home_goals} – {match.away_goals}
                </span>
              ) : (
                <span className="text-xs text-white/30">vs</span>
              )}
            </div>
            <span className="text-sm font-semibold text-white text-left flex-1 truncate">
              {match.away_team.name}
            </span>
          </div>

          {/* Date */}
          <div className="text-[10px] text-white/30 text-right min-w-[72px] hidden md:block">
            {new Date(match.match_datetime).toLocaleDateString('en-GB', {
              day: 'numeric', month: 'short',
            })}
          </div>
        </div>
      </div>
    </Link>
  )
}

export default function MatchesPage() {
  const [statusFilter, setStatusFilter] = useState('')
  const [season, setSeason] = useState<string | undefined>(undefined)
  const [page, setPage] = useState(1)

  const params: MatchesParams = {
    status: statusFilter || undefined,
    season,
    page,
    page_size: 20,
  }

  const { data, isLoading, isError } = useMatches(params)

  const matches = data?.data ?? []
  const pagination = data?.pagination
  const totalPages = pagination?.total_pages ?? 1

  const selectCls = "bg-white/5 border border-white/20 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#00ff85] transition-colors"

  return (
    <main className="max-w-5xl mx-auto px-4 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Matches</h1>
        {pagination && (
          <span className="text-xs text-white/30">{pagination.total.toLocaleString()} total</span>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <select
          className={selectCls}
          value={statusFilter}
          onChange={e => { setStatusFilter(e.target.value); setPage(1) }}
        >
          {STATUS_OPTIONS.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <select
          className={selectCls}
          value={season ?? ''}
          onChange={e => { setSeason(e.target.value || undefined); setPage(1) }}
        >
          <option value="">All Seasons</option>
          {SEASONS.map(s => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </select>
      </div>

      {/* Match list */}
      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="bg-white/5 border border-white/10 rounded-xl h-16 animate-pulse" />
          ))}
        </div>
      ) : isError ? (
        <div className="text-center py-16 text-red-400">Failed to load matches. API may be offline.</div>
      ) : matches.length > 0 ? (
        <div className="space-y-2">
          {matches.map((m: MatchListItem) => <MatchRow key={m.id} match={m} />)}
        </div>
      ) : (
        <div className="text-center py-16 text-white/30">No matches found.</div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 pt-4">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white disabled:opacity-30 hover:bg-white/10 transition-colors"
          >
            ← Prev
          </button>
          <span className="text-sm text-white/40">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white disabled:opacity-30 hover:bg-white/10 transition-colors"
          >
            Next →
          </button>
        </div>
      )}
    </main>
  )
}
