'use client'

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'

interface EloDataPoint {
  date: string
  elo: number
  opponent?: string
}

interface EloChartProps {
  data: EloDataPoint[]
  teamName: string
  height?: number
}

export function EloChart({ data, teamName, height = 200 }: EloChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-white/20 text-xs">
        No ELO history available
      </div>
    )
  }

  // Find min/max for domain padding
  const elos = data.map((d) => d.elo)
  const minElo = Math.min(...elos)
  const maxElo = Math.max(...elos)
  const padding = 50
  const domain: [number, number] = [
    Math.floor((minElo - padding) / 50) * 50,
    Math.ceil((maxElo + padding) / 50) * 50,
  ]

  return (
    <div>
      <p className="text-xs text-white/40 mb-3">
        {teamName} ELO Rating History
      </p>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis
            dataKey="date"
            tick={{ fill: 'rgba(255,255,255,0.25)', fontSize: 9 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: string) =>
              new Date(v).toLocaleDateString('en-GB', { month: 'short', year: '2-digit' })
            }
          />
          <YAxis
            domain={domain}
            tick={{ fill: 'rgba(255,255,255,0.25)', fontSize: 9 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1a0930',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: '8px',
              fontSize: '11px',
            }}
            labelStyle={{ color: 'rgba(255,255,255,0.5)', fontSize: 10 }}
            itemStyle={{ color: '#00ff85' }}
            labelFormatter={(label: string) =>
              new Date(label).toLocaleDateString('en-GB', {
                day: 'numeric',
                month: 'short',
                year: 'numeric',
              })
            }
            formatter={(value: number) => [value.toFixed(0), 'ELO']}
          />
          {/* Average ELO reference */}
          <ReferenceLine
            y={1500}
            stroke="rgba(255,255,255,0.12)"
            strokeDasharray="4 4"
            label={{
              value: '1500',
              position: 'insideTopRight',
              fill: 'rgba(255,255,255,0.2)',
              fontSize: 9,
            }}
          />
          <Line
            type="monotone"
            dataKey="elo"
            stroke="#00ff85"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, fill: '#00ff85', stroke: '#3d195b', strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

