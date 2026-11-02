'use client'

import { useModelInfo, useModelPerformance } from '@/lib/hooks'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine
} from 'recharts'
import type { ModelPerformance } from '@/lib/types'

function MetricCard({
  label, value, sub, highlight = false,
}: {
  label: string
  value: string
  sub?: string
  highlight?: boolean
}) {
  return (
    <div className={`rounded-2xl p-5 border text-center ${
      highlight
        ? 'bg-[#00ff85]/10 border-[#00ff85]/30'
        : 'bg-white/5 border-white/10'
    }`}>
      <div className={`text-3xl font-extrabold ${highlight ? 'text-[#00ff85]' : 'text-white'}`}>
        {value}
      </div>
      <div className="text-xs text-white/50 mt-1 font-medium">{label}</div>
      {sub && <div className="text-[10px] text-white/25 mt-0.5">{sub}</div>}
    </div>
  )
}

function PerformanceChart({ data }: { data: ModelPerformance[] }) {
  if (!data.length) return null
  const chartData = data.map(d => ({
    week: d.week,
    accuracy: Math.round(d.accuracy * 100),
    predictions: d.predictions_made,
  }))

  return (
    <div className="bg-white/5 border border-white/10 rounded-2xl p-5">
      <h2 className="text-sm font-bold text-white/70 mb-5">Weekly Accuracy</h2>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={chartData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis
            dataKey="week"
            tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 10 }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            unit="%"
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1a0930',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: '8px',
              fontSize: '12px',
            }}
            labelStyle={{ color: 'rgba(255,255,255,0.5)' }}
            itemStyle={{ color: '#00ff85' }}
            formatter={(v: number) => [`${v}%`, 'Accuracy']}
          />
          {/* EPL home-win baseline ~46% */}
          <ReferenceLine
            y={46}
            stroke="rgba(255,255,255,0.15)"
            strokeDasharray="4 4"
            label={{ value: 'Baseline 46%', position: 'insideTopLeft', fill: 'rgba(255,255,255,0.2)', fontSize: 10 }}
          />
          <Line
            type="monotone"
            dataKey="accuracy"
            stroke="#00ff85"
            strokeWidth={2}
            dot={{ fill: '#00ff85', r: 3 }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export default function ModelPage() {
  const { data: info, isLoading: infoLoading } = useModelInfo()
  const { data: performance } = useModelPerformance()

  return (
    <main className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      <h1 className="text-2xl font-bold text-white">Model Info</h1>

      {infoLoading ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-24 bg-white/5 border border-white/10 rounded-2xl animate-pulse" />
          ))}
        </div>
      ) : info ? (
        <>
          {/* Key metrics */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <MetricCard label="Accuracy" value={`${(info.accuracy * 100).toFixed(1)}%`} sub="Walk-forward CV" highlight />
            <MetricCard label="Log-Loss" value={info.log_loss.toFixed(3)} sub="Lower = better" />
            <MetricCard label="Training Samples" value={info.training_samples.toLocaleString()} sub="EPL matches" />
            <MetricCard label="Calibration" value={info.calibration_slope?.toFixed(2) ?? 'N/A'} sub="Slope → 1.0 = perfect" />
          </div>

          {/* Model details */}
          <div className="grid md:grid-cols-2 gap-5">
            <div className="bg-white/5 border border-white/10 rounded-2xl p-5 space-y-3">
              <h2 className="text-sm font-bold text-white/70">Model Architecture</h2>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between py-1.5 border-b border-white/5">
                  <span className="text-white/40">Version</span>
                  <span className="text-white font-mono">{info.version}</span>
                </div>
                <div className="flex justify-between py-1.5 border-b border-white/5">
                  <span className="text-white/40">Algorithm</span>
                  <span className="text-white">{info.algorithm}</span>
                </div>
                <div className="flex justify-between py-1.5 border-b border-white/5">
                  <span className="text-white/40">Trained At</span>
                  <span className="text-white">
                    {new Date(info.trained_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
                  </span>
                </div>
                <div className="flex justify-between py-1.5">
                  <span className="text-white/40">Features</span>
                  <span className="text-white">{info.features.length} total</span>
                </div>
              </div>
            </div>

            {/* Feature list */}
            <div className="bg-white/5 border border-white/10 rounded-2xl p-5">
              <h2 className="text-sm font-bold text-white/70 mb-3">Feature Groups</h2>
              {info.features.length > 0 ? (
                <div className="flex flex-wrap gap-1.5 max-h-48 overflow-y-auto scrollbar-thin">
                  {info.features.map((f: string) => (
                    <span
                      key={f}
                      className="text-[10px] bg-white/10 text-white/60 px-2 py-1 rounded font-mono"
                    >
                      {f}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-white/30 text-xs">No feature list available.</p>
              )}
            </div>
          </div>
        </>
      ) : (
        <div className="bg-white/5 border border-white/10 rounded-2xl p-8 text-center">
          <p className="text-white/30 text-sm">Model info unavailable.</p>
          <p className="text-white/20 text-xs mt-1">Train and save a model first.</p>
        </div>
      )}

      {/* Performance over time */}
      {performance && performance.length > 0 && (
        <PerformanceChart data={performance} />
      )}

      {/* About */}
      <div className="bg-white/5 border border-white/10 rounded-2xl p-5">
        <h2 className="text-sm font-bold text-white/70 mb-3">About This Model</h2>
        <div className="text-xs text-white/40 space-y-2 leading-relaxed">
          <p>
            <strong className="text-white/60">Ensemble (stacking):</strong> XGBoost + LightGBM + CatBoost as base learners,
            Logistic Regression as meta-learner. Isotonic calibration applied to ensure probabilities are well-calibrated.
          </p>
          <p>
            <strong className="text-white/60">Validation:</strong> Walk-forward cross-validation only (time-series safe).
            No random splits. Min. 2 training seasons before first test fold.
          </p>
          <p>
            <strong className="text-white/60">Features (60+):</strong> ELO ratings, rolling form (last 5/10), H2H stats,
            season home/away splits, Dixon-Coles attack/defense strength, squad availability,
            referee bias, rest/fatigue, streaks, derby detection, European competition fatigue.
          </p>
          <p>
            <strong className="text-white/60">Target:</strong> ≥55% accuracy, log-loss &lt; 1.00. EPL baseline
            (always predict home win) ≈ 46%.
          </p>
        </div>
      </div>
    </main>
  )
}

