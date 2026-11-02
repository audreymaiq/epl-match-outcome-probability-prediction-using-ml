'use client'

import { useState } from 'react'
import Link from 'next/link'
import { usePredictions } from '@/lib/hooks'
import type { PredictionRecord } from '@/lib/types'

function ResultChip({ isCorrect }: { isCorrect?: boolean | null }) {
  if (isCorrect === undefined || isCorrect === null) {
    return <span className="text-white/20 text-xs">-</span>
  }
  return (
    <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
      isCorrect ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
    }`}>
      {isCorrect ? '✓' : '✗'}
    </span>
  )
}

function OutcomeLabel({ outcome }: { outcome?: string }) {
  if (!outcome) return <span className="text-white/20">-</span>
  const cfg: Record<string, string> = {
    H: 'text-green-400',
    D: 'text-yellow-400',
    A: 'text-blue-400',
  }
  const labels: Record<string, string> = { H: 'Home Win', D: 'Draw', A: 'Away Win' }
  return <span className={`text-xs font-semibold ${cfg[outcome] ?? 'text-white/40'}`}>{labels[outcome] ?? outcome}</span>
}

function confidenceFromProbs(h: number, d: number, a: number): { value: number; label: string; color: string } {
  const max = Math.max(h, d, a)
  if (max >= 0.60) return { value: max, label: 'High', color: 'text-[#00ff85]' }
  if (max >= 0.45) return { value: max, label: 'Medium', color: 'text-yellow-400' }
  return { value: max, label: 'Low', color: 'text-white/30' }
}

export default function PredictionsPage() {
  const [page, setPage] = useState(1)
  const { data, isLoading, isError } = usePredictions({ page, page_size: 25 })

  // Compute overall accuracy from visible data (backend could also provide this)
  const records = data?.data ?? []
  const evaluated = records.filter((r: PredictionRecord) => r.was_correct !== null && r.was_correct !== undefined)
  const correct = evaluated.filter((r: PredictionRecord) => r.was_correct)
  const accuracy = evaluated.length > 0 ? correct.length / evaluated.length : undefined
  const totalRecords = data?.pagination?.total ?? 0
  const totalPages = data?.pagination?.total_pages ?? 1

  return (
    <main className="max-w-5xl mx-auto px-4 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Prediction History</h1>
        {data && (
          <span className="text-xs text-white/30">{totalRecords.toLocaleString()} predictions</span>
        )}
      </div>

      {/* Accuracy summary */}
      {accuracy !== undefined && (
        <div className="bg-white/5 border border-white/10 rounded-2xl p-5 flex items-center gap-6">
          <div className="text-center">
            <div className="text-3xl font-extrabold text-[#00ff85]">
              {(accuracy * 100).toFixed(1)}%
            </div>
            <div className="text-xs text-white/40 mt-1">Page Accuracy</div>
          </div>
          <div className="text-xs text-white/30 leading-relaxed max-w-xs">
            Accuracy measured on completed matches where actual outcome is known.
            EPL baseline (always predict home win) ≈ 46%.
          </div>
        </div>
      )}

      {/* Table */}
      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="h-12 bg-white/5 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : isError ? (
        <div className="text-center py-16 text-red-400">Failed to load predictions.</div>
      ) : records.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] uppercase text-white/30 border-b border-white/10">
                <th className="text-left py-2 pr-4">Match</th>
                <th className="text-left py-2 pr-4">Date</th>
                <th className="text-left py-2 pr-4">Predicted</th>
                <th className="text-left py-2 pr-4">Confidence</th>
                <th className="text-left py-2 pr-4">Probs (H/D/A)</th>
                <th className="text-left py-2 pr-4">Actual</th>
                <th className="text-left py-2">Result</th>
              </tr>
            </thead>
            <tbody>
              {records.map((rec: PredictionRecord) => {
                const conf = confidenceFromProbs(rec.home_win_prob, rec.draw_prob, rec.away_win_prob)
                return (
                  <tr key={rec.id} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                    <td className="py-3 pr-4">
                      <Link href={`/matches/${rec.match_id}`} className="text-white hover:text-[#00ff85] transition-colors font-medium">
                        {rec.home_team_name} vs {rec.away_team_name}
                      </Link>
                    </td>
                    <td className="py-3 pr-4 text-white/40 whitespace-nowrap text-xs">
                      {new Date(rec.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: '2-digit' })}
                    </td>
                    <td className="py-3 pr-4">
                      <OutcomeLabel outcome={rec.predicted_outcome} />
                    </td>
                    <td className="py-3 pr-4">
                      <span className={`text-xs capitalize ${conf.color}`}>
                        {conf.label} ({(conf.value * 100).toFixed(0)}%)
                      </span>
                    </td>
                    <td className="py-3 pr-4 text-xs text-white/40 font-mono whitespace-nowrap">
                      {(rec.home_win_prob * 100).toFixed(0)}% /&nbsp;
                      {(rec.draw_prob * 100).toFixed(0)}% /&nbsp;
                      {(rec.away_win_prob * 100).toFixed(0)}%
                    </td>
                    <td className="py-3 pr-4">
                      <OutcomeLabel outcome={rec.actual_outcome} />
                    </td>
                    <td className="py-3">
                      <ResultChip isCorrect={rec.was_correct} />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-center py-16 text-white/30">
          No predictions yet. Run the API and make some predictions!
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 pt-2">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white disabled:opacity-30 hover:bg-white/10 transition-colors"
          >
            ← Prev
          </button>
          <span className="text-sm text-white/40">Page {page} of {totalPages}</span>
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
