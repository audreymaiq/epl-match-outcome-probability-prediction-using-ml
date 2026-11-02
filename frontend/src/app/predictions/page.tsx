'use client'

import Link from 'next/link'
import { useState } from 'react'
import { ArrowLeft, ArrowRight, ChartNoAxesCombined, CircleCheck, CircleX } from 'lucide-react'
import { usePredictions } from '@/lib/hooks'
import { PageHeading } from '@/components/page-heading'
import type { PredictionRecord } from '@/lib/types'

const outcomeName: Record<string, string> = { H: 'Home win', D: 'Draw', A: 'Away win' }

export default function PredictionsPage() {
  const [page, setPage] = useState(1)
  const { data, isLoading, isError } = usePredictions({ page, page_size: 25 })
  const records = data?.data ?? []
  const evaluated = records.filter((record: PredictionRecord) => record.was_correct != null)
  const correct = evaluated.filter((record: PredictionRecord) => record.was_correct).length
  const accuracy = evaluated.length ? correct / evaluated.length : null
  const totalPages = data?.pagination.total_pages ?? 1

  return (
    <main className="page-frame pb-16 pt-8 sm:pt-12">
      <PageHeading eyebrow="Results" title="Prediction history" description="Review saved predictions alongside completed match results." action={data ? <div className="border-l border-[var(--border)] pl-4 text-right"><p className="font-mono text-lg font-bold text-white">{data.pagination.total.toLocaleString()}</p><p className="text-[0.65rem] text-[var(--muted)]">predictions</p></div> : undefined} />
      {accuracy != null && <section className="mb-5 grid gap-3 sm:grid-cols-[auto_1fr] sm:items-center"><div className="surface flex items-center gap-4 p-5"><span className="grid h-11 w-11 place-items-center rounded-xl bg-[rgba(139,240,178,.1)] text-[var(--pl-green)]"><ChartNoAxesCombined size={19} /></span><div><p className="font-mono text-2xl font-bold text-[var(--pl-green)]">{(accuracy * 100).toFixed(1)}%</p><p className="text-[0.65rem] text-[var(--muted)]">Accuracy on this page</p></div></div><p className="px-2 text-xs leading-5 text-[var(--muted)]">Calculated from {evaluated.length} completed matches shown on this page. Upcoming fixtures are not included.</p></section>}
      {isLoading ? <div className="space-y-2">{Array.from({ length: 8 }, (_, index) => <div key={index} className="surface-quiet h-20 animate-pulse" />)}</div> : isError ? <div role="alert" className="surface-quiet p-8 text-center"><p className="font-semibold text-white">Prediction history is unavailable</p><p className="mt-1 text-sm text-[var(--muted)]">The service could not return saved predictions.</p></div> : records.length ? <div className="space-y-3">{records.map((record: PredictionRecord) => <article key={record.id} className="surface-quiet grid gap-4 p-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:p-5"><div className="min-w-0"><div className="flex flex-wrap items-center gap-x-3 gap-y-1"><Link href={`/matches/${record.match_id}`} className="truncate text-sm font-bold text-white transition hover:text-[var(--pl-green)]">{record.home_team_name} <span className="text-[var(--subtle)]">vs</span> {record.away_team_name}</Link><span className="text-[0.65rem] text-[var(--subtle)]">{new Date(record.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}</span></div><div className="mt-3 flex flex-wrap items-center gap-2"><span className="rounded-md bg-white/[0.06] px-2 py-1 text-[0.65rem] font-semibold text-[var(--muted)]">Predicted: {outcomeName[record.predicted_outcome] || record.predicted_outcome}</span>{record.actual_outcome && <span className="rounded-md bg-white/[0.06] px-2 py-1 text-[0.65rem] font-semibold text-[var(--muted)]">Result: {outcomeName[record.actual_outcome] || record.actual_outcome}</span>}{record.was_correct === true && <span className="inline-flex items-center gap-1 text-[0.65rem] font-semibold text-[var(--pl-green)]"><CircleCheck size={13} /> Correct</span>}{record.was_correct === false && <span className="inline-flex items-center gap-1 text-[0.65rem] font-semibold text-[var(--danger)]"><CircleX size={13} /> Incorrect</span>}</div></div><div className="grid grid-cols-3 gap-3 border-t border-[var(--border)] pt-3 font-mono text-xs tabular-nums sm:border-l sm:border-t-0 sm:pl-5 sm:pt-0"><Probability label="Home" value={record.home_win_prob} /><Probability label="Draw" value={record.draw_prob} /><Probability label="Away" value={record.away_win_prob} /></div></article>)}</div> : <div className="surface p-10 text-center"><ChartNoAxesCombined className="mx-auto text-[var(--subtle)]" /><p className="mt-4 font-semibold text-white">No predictions recorded yet</p><p className="mt-1 text-sm text-[var(--muted)]">Choose an upcoming fixture and generate a prediction to start your history.</p><Link href="/matches" className="button-primary mt-5">Browse fixtures <ArrowRight size={15} /></Link></div>}
      {totalPages > 1 && <nav className="mt-8 flex items-center justify-center gap-3" aria-label="Prediction history pages"><button className="button-secondary" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}><ArrowLeft size={14} /> Previous</button><span className="px-2 text-xs tabular-nums text-[var(--muted)]">Page {page} of {totalPages}</span><button className="button-secondary" disabled={page >= totalPages} onClick={() => setPage((current) => Math.min(totalPages, current + 1))}>Next <ArrowRight size={14} /></button></nav>}
    </main>
  )
}

function Probability({ label, value }: { label: string; value: number }) {
  return <div><p className="text-[0.58rem] uppercase tracking-wide text-[var(--subtle)]">{label}</p><p className="mt-1 font-bold text-white">{(value * 100).toFixed(0)}%</p></div>
}
