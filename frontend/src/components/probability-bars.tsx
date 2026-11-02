import { cn } from '@/lib/utils'
import type { ProbabilityBreakdown } from '@/lib/types'

interface ProbabilityBarsProps {
  probabilities: ProbabilityBreakdown
  predicted_outcome: 'H' | 'D' | 'A'
  homeTeam?: string
  awayTeam?: string
  compact?: boolean
}

export function ProbabilityBars({
  probabilities,
  predicted_outcome,
  homeTeam = 'Home',
  awayTeam = 'Away',
  compact = false,
}: ProbabilityBarsProps) {
  const homePct = Math.round(probabilities.home_win * 100)
  const drawPct = Math.round(probabilities.draw * 100)
  const awayPct = Math.round(probabilities.away_win * 100)

  const bars = [
    {
      key: 'H',
      label: compact ? 'H' : homeTeam,
      sublabel: compact ? undefined : 'Home Win',
      pct: homePct,
      color: 'bg-green-500',
      textColor: 'text-green-700',
      trackColor: 'bg-green-100',
    },
    {
      key: 'D',
      label: 'Draw',
      sublabel: compact ? undefined : 'Draw',
      pct: drawPct,
      color: 'bg-yellow-400',
      textColor: 'text-yellow-700',
      trackColor: 'bg-yellow-100',
    },
    {
      key: 'A',
      label: compact ? 'A' : awayTeam,
      sublabel: compact ? undefined : 'Away Win',
      pct: awayPct,
      color: 'bg-blue-500',
      textColor: 'text-blue-700',
      trackColor: 'bg-blue-100',
    },
  ]

  return (
    <div className={cn('space-y-2', compact ? 'gap-1.5' : 'gap-2')}>
      {bars.map(({ key, label, sublabel, pct, color, textColor, trackColor }) => {
        const isPredicted = predicted_outcome === key
        return (
          <div key={key} className="flex items-center gap-2">
            {/* Label */}
            <div className={cn('text-xs font-medium truncate', compact ? 'w-6' : 'w-24', textColor)}>
              {compact ? (
                <span className="font-bold">{label}</span>
              ) : (
                <div>
                  <div className="font-semibold truncate">{label}</div>
                  {sublabel && label !== sublabel && (
                    <div className="text-gray-400 text-[10px]">{sublabel}</div>
                  )}
                </div>
              )}
            </div>

            {/* Bar track */}
            <div className={cn('flex-1 h-5 rounded-full overflow-hidden', trackColor)}>
              <div
                className={cn('h-full rounded-full transition-all duration-700', color, isPredicted && 'opacity-100')}
                style={{ width: `${pct}%`, opacity: isPredicted ? 1 : 0.65 }}
              />
            </div>

            {/* Percent + predicted indicator */}
            <div className="flex items-center gap-1 min-w-[42px]">
              <span className={cn('text-xs font-bold', textColor)}>{pct}%</span>
              {isPredicted && (
                <span
                  className="w-1.5 h-1.5 rounded-full inline-block"
                  style={{ backgroundColor: 'var(--pl-green)' }}
                  title="Predicted outcome"
                />
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
