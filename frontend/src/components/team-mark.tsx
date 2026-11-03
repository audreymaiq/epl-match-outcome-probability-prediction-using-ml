'use client'

import { useState } from 'react'
import type { TeamBrief } from '@/lib/types'

const CLUB_COLORS: Record<string, string> = {
  arsenal: '#ef3340', chelsea: '#1765ad', liverpool: '#c8102e',
  'manchester city': '#6cabdd', 'manchester united': '#da291c',
  tottenham: '#132257', newcastle: '#343434', 'aston villa': '#8e1b40',
  brighton: '#0057b8', 'west ham': '#7a263a', brentford: '#c8102e',
  fulham: '#5c5c5c', 'crystal palace': '#1b458f', wolves: '#fdb913',
  'nottingham forest': '#dd0000', everton: '#003399', bournemouth: '#da291c',
  southampton: '#d71920', ipswich: '#3a64a3', leicester: '#003090',
}

export function TeamMark({ team, size = 'md' }: { team: Pick<TeamBrief, 'name' | 'short_name' | 'logo_url'>; size?: 'sm' | 'md' | 'lg' }) {
  const [imageFailed, setImageFailed] = useState(false)
  const dimensions = size === 'lg' ? 'h-16 w-16' : size === 'sm' ? 'h-9 w-9' : 'h-12 w-12'
  const initials = (team.short_name || team.name).replace(/[^a-z0-9 ]/gi, '').split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toUpperCase()
  return (
    <span className={`relative grid ${dimensions} shrink-0 place-items-center overflow-hidden rounded-2xl border border-white/10 bg-[#241c2c] text-xs font-extrabold tracking-wide text-white`}>
      <span className="absolute inset-0 grid place-items-center" style={{ backgroundColor: CLUB_COLORS[team.name.toLowerCase()] || '#45304f' }}>{initials || 'FC'}</span>
      {team.logo_url && !imageFailed && (
        <span className="absolute inset-0 grid place-items-center bg-[#17121e] p-1.5">
          {/* External club logos have provider-specific hosts and use a local fallback. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={team.logo_url} alt="" className="h-full w-full object-contain" onError={() => setImageFailed(true)} />
        </span>
      )}
    </span>
  )
}
