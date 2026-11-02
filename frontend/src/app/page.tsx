'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useMatches, useModelInfo, useTeams, usePredict } from '@/lib/hooks'
import { ProbabilityBars } from '@/components/probability-bars'
import type { MatchListItem, Team, PagedResponse } from '@/lib/types'

// ── Outcome badge ────────────────────────────────────────────────────────────
function OutcomeBadge({ outcome }: { outcome?: string }) {
  if (!outcome) return null
  const cfg: Record<string, { label: string; cls: string }> = {
    H: { label: 'Home Win', cls: 'bg-green-500/20 text-green-400 border border-green-500/30' },
    D: { label: 'Draw', cls: 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30' },
    A: { label: 'Away Win', cls: 'bg-blue-500/20 text-blue-400 border border-blue-500/30' },
  }
  const { label, cls } = cfg[outcome] ?? { label: outcome, cls: 'bg-white/10 text-white/40' }
  return (
    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider ${cls}`}>
      {label}
    </span>
  )
}

// ── Match card ───────────────────────────────────────────────────────────────
function MatchCard({ match }: { match: MatchListItem }) {
  const isFinished = match.status === 'FINISHED'

  return (
    <Link href={`/matches/${match.id}`}>
      <div className="bg-white/5 border border-white/10 rounded-xl p-4 hover:bg-white/10 hover:border-white/20 transition-all cursor-pointer group">
        {/* Status + Week */}
        <div className="flex items-center justify-between mb-3">
          <span className="text-[10px] text-white/40 font-medium uppercase tracking-widest">
            GW{match.match_week}
          </span>
          <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${
            isFinished ? 'bg-white/10 text-white/40' :
            match.status === 'LIVE' ? 'bg-red-500/20 text-red-400' :
            'bg-[#00ff85]/20 text-[#00ff85]'
          }`}>
            {match.status}
          </span>
        </div>

        {/* Teams + Score */}
        <div className="flex items-center justify-between gap-2 mb-3">
          <span className="text-sm font-semibold text-white text-right flex-1 truncate">
            {match.home_team.name}
          </span>
          <div className="text-center min-w-[52px]">
            {isFinished ? (
              <span className="text-lg font-bold text-white">
                {match.home_goals ?? 0} – {match.away_goals ?? 0}
              </span>
            ) : (
              <span className="text-xs text-white/30">vs</span>
            )}
          </div>
          <span className="text-sm font-semibold text-white text-left flex-1 truncate">
            {match.away_team.name}
          </span>
        </div>

        {/* Actual outcome (finished) */}
        {isFinished && (
          <div className="flex justify-center mt-1">
            <OutcomeBadge outcome={match.outcome} />
          </div>
        )}

        {/* Date */}
        <div className="text-[10px] text-white/30 text-center mt-3">
          {new Date(match.match_datetime).toLocaleDateString('en-GB', {
            weekday: 'short', day: 'numeric', month: 'short', year: 'numeric',
          })}
        </div>
      </div>
    </Link>
  )
}

// ── Stat card ────────────────────────────────────────────────────────────────
function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-white/5 border border-white/10 rounded-xl p-4 text-center">
      <div className="text-2xl font-bold text-[#00ff85]">{value}</div>
      <div className="text-xs text-white/60 mt-1 font-medium">{label}</div>
      {sub && <div className="text-[10px] text-white/30 mt-0.5">{sub}</div>}
    </div>
  )
}

// ── Quick Predict form ───────────────────────────────────────────────────────
function QuickPredict() {
  const { data: teamsPage } = useTeams()
  const teams = teamsPage?.data ?? []
  const { mutate: predict, data: result, isPending, reset } = usePredict()
  const [homeId, setHomeId] = useState('')
  const [awayId, setAwayId] = useState('')
  const [matchDate, setMatchDate] = useState(
    new Date().toISOString().slice(0, 10)
  )

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!homeId || !awayId || homeId === awayId) return
    predict({
      home_team_id: Number(homeId),
      away_team_id: Number(awayId),
      match_datetime: `${matchDate}T15:00:00Z`,
    })
  }

  const confidenceLabel = (c: number) =>
    c >= 0.6 ? 'high' : c >= 0.45 ? 'medium' : 'low'

  const selectCls = "w-full bg-white/5 border border-white/20 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#00ff85] transition-colors"

  return (
    <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
      <h2 className="text-lg font-bold text-white mb-4">⚡ Quick Predict</h2>
      <form onSubmit={handleSubmit} className="space-y-3">
        <select className={selectCls} value={homeId} onChange={e => { setHomeId(e.target.value); reset() }}>
          <option value="">Select Home Team</option>
          {teams.map((t: Team) => (
            <option key={t.id} value={t.id}>{t.name}</option>
          ))}
        </select>
        <select className={selectCls} value={awayId} onChange={e => { setAwayId(e.target.value); reset() }}>
          <option value="">Select Away Team</option>
          {teams.filter((t: Team) => String(t.id) !== homeId).map((t: Team) => (
            <option key={t.id} value={t.id}>{t.name}</option>
          ))}
        </select>
        <input
          type="date"
          className={selectCls}
          value={matchDate}
          onChange={e => setMatchDate(e.target.value)}
        />
        <button
          type="submit"
          disabled={!homeId || !awayId || homeId === awayId || isPending}
          className="w-full bg-[#00ff85] text-[#3d195b] font-bold py-2.5 rounded-lg text-sm hover:bg-[#00ff85]/90 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
        >
          {isPending ? 'Predicting…' : 'Predict Outcome'}
        </button>
      </form>

      {result && (
        <div className="mt-4 pt-4 border-t border-white/10">
          <ProbabilityBars
            probabilities={result.probabilities}
            predicted_outcome={result.predicted_outcome}
            homeTeam={result.home_team_name}
            awayTeam={result.away_team_name}
          />
          <p className="text-[10px] text-white/30 text-center mt-3">
            Confidence: <span className="text-white/60 capitalize">{confidenceLabel(result.confidence)}</span>
            {' '}({(result.confidence * 100).toFixed(0)}%)
          </p>
        </div>
      )}
    </div>
  )
}

// ── Home page ────────────────────────────────────────────────────────────────
export default function HomePage() {
  const { data: matchesPage, isLoading } = useMatches({ status: 'SCHEDULED', page_size: 6 })
  const { data: model } = useModelInfo()

  const matches = matchesPage?.data ?? []

  return (
    <main className="max-w-7xl mx-auto px-4 py-8 space-y-10">
      {/* Hero */}
      <section className="text-center py-10">
        <div className="inline-flex items-center gap-2 bg-[#00ff85]/10 border border-[#00ff85]/30 rounded-full px-4 py-1.5 mb-5">
          <span className="text-[#00ff85] text-xs font-bold uppercase tracking-widest">AI-Powered</span>
        </div>
        <h1 className="text-4xl md:text-5xl font-extrabold text-white mb-3 leading-tight">
          Premier League<br />
          <span className="text-[#00ff85]">Match Predictions</span>
        </h1>
        <p className="text-white/50 max-w-lg mx-auto text-sm leading-relaxed">
          Stacking ensemble (XGBoost + LightGBM + CatBoost) trained on ELO ratings,
          rolling form, H2H, squad availability, and 60+ features.
        </p>
      </section>

      {/* Model stats */}
      {model && (
        <section>
          <h2 className="text-sm font-bold text-white/50 uppercase tracking-widest mb-3">Model Performance</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard label="Accuracy" value={`${(model.accuracy * 100).toFixed(1)}%`} sub="Walk-forward CV" />
            <StatCard label="Log-Loss" value={model.log_loss.toFixed(3)} sub="Lower = better" />
            <StatCard label="Training Samples" value={model.training_samples.toLocaleString()} sub="EPL matches" />
            <StatCard label="Model Version" value={model.version} sub={`v${model.algorithm}`} />
          </div>
        </section>
      )}

      <div className="grid md:grid-cols-3 gap-8">
        {/* Upcoming Matches */}
        <div className="md:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-white/50 uppercase tracking-widest">Upcoming Matches</h2>
            <Link href="/matches" className="text-xs text-[#00ff85] hover:underline">View all →</Link>
          </div>
          {isLoading ? (
            <div className="grid sm:grid-cols-2 gap-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="bg-white/5 border border-white/10 rounded-xl h-36 animate-pulse" />
              ))}
            </div>
          ) : matches.length > 0 ? (
            <div className="grid sm:grid-cols-2 gap-3">
              {matches.map((m: MatchListItem) => <MatchCard key={m.id} match={m} />)}
            </div>
          ) : (
            <div className="text-center py-16 text-white/30 text-sm">
              No upcoming matches found.
            </div>
          )}
        </div>

        {/* Quick Predict sidebar */}
        <div className="space-y-4">
          <QuickPredict />
          <div className="bg-white/5 border border-white/10 rounded-2xl p-4">
            <h3 className="text-xs font-bold text-white/50 uppercase tracking-widest mb-3">Navigate</h3>
            <nav className="space-y-1">
              {[
                { href: '/matches', label: '📅 All Matches' },
                { href: '/teams', label: '🛡️ Teams' },
                { href: '/predictions', label: '📊 Prediction History' },
                { href: '/model', label: '🤖 Model Info' },
              ].map(({ href, label }) => (
                <Link
                  key={href}
                  href={href}
                  className="flex items-center px-3 py-2 rounded-lg text-sm text-white/70 hover:bg-white/10 hover:text-white transition-colors"
                >
                  {label}
                </Link>
              ))}
            </nav>
          </div>
        </div>
      </div>
    </main>
  )
}
