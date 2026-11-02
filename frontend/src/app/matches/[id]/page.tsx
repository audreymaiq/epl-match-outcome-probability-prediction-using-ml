'use client'

import { useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { useMatch, usePredict } from '@/lib/hooks'
import { ProbabilityBars } from '@/components/probability-bars'
import { FormBadges } from '@/components/form-badges'
import type { MatchDetail, PredictResponse } from '@/lib/types'

function InfoRow({ label, value }: { label: string; value?: string | number | null }) {
  if (!value && value !== 0) return null
  return (
    <div className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
      <span className="text-xs text-white/40">{label}</span>
      <span className="text-xs font-medium text-white">{value}</span>
    </div>
  )
}

function confidenceLabel(c: number): string {
  return c >= 0.6 ? 'high' : c >= 0.45 ? 'medium' : 'low'
}

function confidenceColor(c: number): string {
  return c >= 0.6 ? 'text-[#00ff85]' : c >= 0.45 ? 'text-yellow-400' : 'text-white/50'
}

export default function MatchDetailPage() {
  const params = useParams()
  const matchId = Number(params.id)
  const { data: match, isLoading, isError } = useMatch(matchId)
  const { mutate: predict, data: prediction, isPending, reset } = usePredict()
  const [hasPredicted, setHasPredicted] = useState(false)

  const handlePredict = () => {
    if (!match) return
    predict(
      {
        home_team_id: match.home_team.id,
        away_team_id: match.away_team.id,
        match_datetime: match.match_datetime,
      },
      { onSuccess: () => setHasPredicted(true) }
    )
  }

  const displayPrediction: PredictResponse | undefined = prediction ?? undefined

  if (isLoading) {
    return (
      <main className="max-w-4xl mx-auto px-4 py-8">
        <div className="animate-pulse space-y-4">
          <div className="h-32 bg-white/5 rounded-2xl" />
          <div className="h-64 bg-white/5 rounded-2xl" />
        </div>
      </main>
    )
  }

  if (isError || !match) {
    return (
      <main className="max-w-4xl mx-auto px-4 py-8 text-center">
        <p className="text-red-400">Match not found or API is offline.</p>
        <Link href="/matches" className="text-[#00ff85] text-sm mt-2 inline-block hover:underline">← Back to Matches</Link>
      </main>
    )
  }

  const isFinished = match.status === 'FINISHED'

  return (
    <main className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      {/* Back */}
      <Link href="/matches" className="text-xs text-white/40 hover:text-white/70 transition-colors">
        ← Back to Matches
      </Link>

      {/* Match header */}
      <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
        <div className="flex items-center gap-2 mb-5 justify-center">
          <span className="text-xs text-white/30 font-medium">GW{match.match_week}</span>
          <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${
            isFinished ? 'bg-white/10 text-white/40' :
            match.status === 'LIVE' ? 'bg-red-500/20 text-red-400' :
            'bg-[#00ff85]/20 text-[#00ff85]'
          }`}>{match.status}</span>
        </div>
        <div className="flex items-center justify-center gap-6">
          <div className="text-center flex-1">
            <p className="text-xl font-bold text-white">{match.home_team.name}</p>
            <p className="text-xs text-white/30 mt-1">Home</p>
          </div>
          <div className="text-center">
            {isFinished ? (
              <span className="text-4xl font-extrabold text-white">
                {match.home_goals} – {match.away_goals}
              </span>
            ) : (
              <span className="text-4xl font-extrabold text-white/20">vs</span>
            )}
          </div>
          <div className="text-center flex-1">
            <p className="text-xl font-bold text-white">{match.away_team.name}</p>
            <p className="text-xs text-white/30 mt-1">Away</p>
          </div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Prediction panel */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-5 space-y-4">
          <h2 className="text-sm font-bold text-white/70">AI Prediction</h2>
          {displayPrediction ? (
            <>
              <ProbabilityBars
                probabilities={displayPrediction.probabilities}
                predicted_outcome={displayPrediction.predicted_outcome}
                homeTeam={match.home_team.name}
                awayTeam={match.away_team.name}
              />
              <div className="flex items-center justify-between text-xs pt-2 border-t border-white/10">
                <span className="text-white/30">Confidence</span>
                <span className={`capitalize font-semibold ${confidenceColor(displayPrediction.confidence)}`}>
                  {confidenceLabel(displayPrediction.confidence)} ({(displayPrediction.confidence * 100).toFixed(0)}%)
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-white/30">Model version</span>
                <span className="text-white/50">{displayPrediction.model_version}</span>
              </div>
            </>
          ) : (
            <div className="text-center py-8">
              <p className="text-white/30 text-sm mb-4">No prediction yet</p>
              <button
                onClick={handlePredict}
                disabled={isPending}
                className="bg-[#00ff85] text-[#3d195b] font-bold px-6 py-2.5 rounded-lg text-sm hover:bg-[#00ff85]/90 disabled:opacity-40 transition-all"
              >
                {isPending ? 'Predicting…' : 'Get Prediction'}
              </button>
            </div>
          )}
        </div>

        {/* Match info */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-5 space-y-1">
          <h2 className="text-sm font-bold text-white/70 mb-3">Match Info</h2>
          <InfoRow label="Date" value={new Date(match.match_datetime).toLocaleString('en-GB', { dateStyle: 'full', timeStyle: 'short' })} />
          <InfoRow label="Stadium" value={match.stadium?.name} />
          <InfoRow label="Referee" value={match.referee?.name} />
          <InfoRow label="Season" value={match.season_name} />
          <InfoRow label="Match Week" value={match.match_week ? `Gameweek ${match.match_week}` : undefined} />
          {isFinished && match.attendance && <InfoRow label="Attendance" value={match.attendance.toLocaleString()} />}
        </div>
      </div>

      {/* Match stats (finished only) */}
      {isFinished && (match.home_possession || match.home_shots) && (
        <div className="bg-white/5 border border-white/10 rounded-2xl p-5">
          <h2 className="text-sm font-bold text-white/70 mb-4">Match Statistics</h2>
          <div className="space-y-2">
            {match.home_possession != null && (
              <StatRow label="Possession" home={`${match.home_possession}%`} away={`${match.away_possession}%`} />
            )}
            {match.home_shots != null && (
              <StatRow label="Shots" home={match.home_shots} away={match.away_shots} />
            )}
            {match.home_shots_on_target != null && (
              <StatRow label="Shots on Target" home={match.home_shots_on_target} away={match.away_shots_on_target} />
            )}
            {match.home_corners != null && (
              <StatRow label="Corners" home={match.home_corners} away={match.away_corners} />
            )}
          </div>
        </div>
      )}
    </main>
  )
}

function StatRow({ label, home, away }: { label: string; home?: number | string | null; away?: number | string | null }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-white font-medium w-16 text-right">{home ?? '-'}</span>
      <span className="text-white/40 flex-1 text-center">{label}</span>
      <span className="text-white font-medium w-16 text-left">{away ?? '-'}</span>
    </div>
  )
}
