import type { ProbabilityBreakdown } from '@/lib/types'

interface ProbabilityBarsProps {
  probabilities: ProbabilityBreakdown
  predicted_outcome: 'H' | 'D' | 'A'
  homeTeam?: string
  awayTeam?: string
  compact?: boolean
}

export function ProbabilityBars({ probabilities, predicted_outcome, homeTeam = 'Home', awayTeam = 'Away', compact = false }: ProbabilityBarsProps) {
  const bars = [
    { key: 'H', label: compact ? 'H' : homeTeam, title: 'Home win', value: probabilities.home_win, color: '#8bf0b2' },
    { key: 'D', label: compact ? 'D' : 'Draw', title: 'Draw', value: probabilities.draw, color: '#d2a7ff' },
    { key: 'A', label: compact ? 'A' : awayTeam, title: 'Away win', value: probabilities.away_win, color: '#82b5ff' },
  ]

  return (
    <div className={compact ? 'space-y-2' : 'space-y-4'}>
      {bars.map(({ key, label, title, value, color }) => {
        const percent = Math.max(0, Math.min(100, value * 100))
        const predicted = predicted_outcome === key
        return (
          <div key={key} className="grid grid-cols-[minmax(4.5rem,1fr)_3fr_auto] items-center gap-3">
            <div className="min-w-0">
              <p className={`truncate font-semibold ${compact ? 'text-[0.68rem]' : 'text-sm'} ${predicted ? 'text-white' : 'text-[var(--muted)]'}`}>{label}</p>
              {!compact && <p className="mt-0.5 text-[0.62rem] text-[var(--subtle)]">{title}</p>}
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-white/[0.08]" role="meter" aria-label={`${label} ${title} probability`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(percent)}>
              <div className="h-full rounded-full transition-[width] duration-500" style={{ width: `${percent}%`, backgroundColor: color, opacity: predicted ? 1 : 0.58 }} />
            </div>
            <span className={`w-10 text-right font-mono text-xs font-bold tabular-nums ${predicted ? 'text-[var(--pl-green)]' : 'text-[var(--muted)]'}`}>{Math.round(percent)}%</span>
          </div>
        )
      })}
    </div>
  )
}
