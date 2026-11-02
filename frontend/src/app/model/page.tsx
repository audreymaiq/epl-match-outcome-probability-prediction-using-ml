'use client'

import { useModelInfo, useModelPerformance } from '@/lib/hooks'
import { PageHeading } from '@/components/page-heading'

function Metric({ label, value, detail, accent = false }: { label: string; value: string; detail: string; accent?: boolean }) {
  return <div className="border-t border-[var(--border)] py-4"><p className="data-label">{label}</p><p className={`mt-2 font-mono text-2xl font-bold tabular-nums sm:text-3xl ${accent ? 'text-[var(--pl-green)]' : 'text-white'}`}>{value}</p><p className="mt-1 text-xs leading-5 text-[var(--muted)]">{detail}</p></div>
}

export default function ModelPage() {
  const { data: info, isLoading, isError } = useModelInfo()
  const { data: performance } = useModelPerformance()
  const metrics = info?.cv_metrics ?? {}
  const accuracy = metrics.mean_accuracy
  const logLoss = metrics.mean_log_loss
  const features = info?.feature_names ?? []
  const loaded = info?.status === 'loaded'

  return (
    <main className="page-frame pb-16 pt-8 sm:pt-12">
      <PageHeading eyebrow="Method" title="Prediction model" description="Model status, validation metrics and observed prediction performance." />
      {isLoading ? <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{Array.from({ length: 4 }, (_, index) => <div key={index} className="h-28 animate-pulse border-t border-[var(--border)] bg-white/[0.025]" />)}</div> : isError ? <div role="alert" className="border-l-2 border-[var(--danger)] bg-[var(--surface)] p-5 text-sm text-[var(--danger)]">Model metadata is temporarily unavailable.</div> : loaded ? <>
        <section className="mb-7 flex flex-wrap items-center justify-between gap-3 border-l-4 border-[var(--pl-green)] bg-[var(--surface)] px-4 py-3"><div><p className="text-sm font-bold text-white">Model loaded</p><p className="mt-1 text-xs text-[var(--muted)]">{info?.algorithm || 'Ensemble'} · version {info?.version || 'unversioned'}</p></div><span className="text-xs font-semibold text-[var(--pl-green)]">Ready for predictions</span></section>
        <section className="mb-8 grid gap-x-6 sm:grid-cols-2 lg:grid-cols-4"><Metric label="Walk-forward baseline accuracy" value={typeof accuracy === 'number' ? `${(accuracy * 100).toFixed(1)}%` : '—'} detail={`Mean across chronological folds using ${info?.cv_evaluation_model ?? 'an unspecified baseline'}`} accent /><Metric label="Mean baseline log loss" value={typeof logLoss === 'number' ? logLoss.toFixed(3) : '—'} detail="Lower values indicate better probability estimates" /><Metric label="Model features" value={String(info?.n_features ?? features.length ?? '—')} detail="Inputs used by the loaded estimator" /><Metric label="Validation folds" value={String(info?.walk_forward_folds ?? '—')} detail="Chronological evaluation windows" /></section>
        <div className="grid gap-8 lg:grid-cols-[.8fr_1.2fr]">
          <section className="border-t border-[var(--border)] pt-4"><h2 className="text-base font-bold text-white">Recorded results</h2><p className="mt-1 text-xs text-[var(--muted)]">Saved predictions compared with completed matches</p><dl className="mt-5 divide-y divide-[var(--border)]"><div className="flex justify-between py-3"><dt className="text-sm text-[var(--muted)]">Predictions recorded</dt><dd className="font-mono text-sm font-bold text-white">{performance?.total_predictions ?? 0}</dd></div><div className="flex justify-between py-3"><dt className="text-sm text-[var(--muted)]">Matches evaluated</dt><dd className="font-mono text-sm font-bold text-white">{performance?.evaluated ?? 0}</dd></div><div className="flex justify-between py-3"><dt className="text-sm text-[var(--muted)]">Observed accuracy</dt><dd className="font-mono text-sm font-bold text-[var(--pl-green)]">{typeof performance?.accuracy === 'number' ? `${(performance.accuracy * 100).toFixed(1)}%` : '—'}</dd></div></dl>{performance?.note && <p className="mt-3 text-xs text-[var(--warning)]">{performance.note}</p>}</section>
          <section className="border-t border-[var(--border)] pt-4"><h2 className="text-base font-bold text-white">Features used</h2><p className="mt-1 text-xs text-[var(--muted)]">Names provided by the loaded model</p>{features.length ? <ul className="mt-5 grid max-h-72 grid-cols-1 gap-x-8 overflow-y-auto sm:grid-cols-2">{features.map((feature) => <li key={feature} className="border-b border-white/[0.06] py-2 font-mono text-[0.68rem] text-[var(--muted)]">{feature}</li>)}</ul> : <p className="mt-5 text-sm text-[var(--muted)]">The backend reports {info?.n_features ?? 0} features but does not provide their names.</p>}</section>
        </div>
        <p className="mt-8 border-t border-[var(--border)] pt-4 text-xs leading-5 text-[var(--subtle)]">Validation scores describe historical results on chronological data. Probabilities are estimates and do not guarantee future match outcomes.</p>
      </> : <section className="border-y border-[var(--border)] py-7"><p className="text-base font-bold text-white">No model is loaded</p><p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted)]">The API is reachable, but it has not loaded a trained model. Fixtures and club statistics remain available; predictions require a model artifact.</p></section>}
    </main>
  )
}
