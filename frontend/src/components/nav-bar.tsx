'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useState } from 'react'
import { Menu, X } from 'lucide-react'

const navLinks = [
  { href: '/matches', label: 'Fixtures' },
  { href: '/teams', label: 'Clubs' },
  { href: '/predictions', label: 'Predictions' },
  { href: '/model', label: 'About the model' },
]

export function NavBar() {
  const pathname = usePathname()
  const [mobileOpen, setMobileOpen] = useState(false)

  function isActive(href: string) {
    return href === '/' ? pathname === '/' : pathname === href || pathname.startsWith(`${href}/`)
  }

  return (
    <header className="sticky top-0 z-40 border-b border-white/[0.1] bg-[#100d16]">
      <div className="page-frame flex min-h-[4.25rem] items-center justify-between gap-5">
        <Link href="/" className="flex shrink-0 items-center gap-2.5" aria-label="Matchday home">
          <span className="grid h-9 w-9 place-items-center bg-[var(--pl-purple)] font-mono text-sm font-black tracking-tighter text-white">90</span>
          <span className="leading-none">
            <span className="block text-[0.88rem] font-black tracking-[0.08em] text-white">MATCHDAY</span>
            <span className="mt-1.5 block text-[0.58rem] font-semibold uppercase tracking-[0.11em] text-[var(--subtle)]">Premier League</span>
          </span>
        </Link>

        <nav aria-label="Main navigation" className="hidden h-[4.25rem] items-stretch gap-6 md:flex">
          <Link href="/" aria-current={isActive('/') ? 'page' : undefined} className={`flex items-center border-b-2 px-1 text-xs font-bold transition-colors ${isActive('/') ? 'border-[var(--pl-green)] text-white' : 'border-transparent text-[var(--muted)] hover:text-white'}`}>Overview</Link>
          {navLinks.map(({ href, label }) => <Link key={href} href={href} aria-current={isActive(href) ? 'page' : undefined} className={`flex items-center border-b-2 px-1 text-xs font-bold transition-colors ${isActive(href) ? 'border-[var(--pl-green)] text-white' : 'border-transparent text-[var(--muted)] hover:text-white'}`}>{label}</Link>)}
        </nav>

        <button type="button" className="grid h-10 w-10 place-items-center border border-white/10 text-white hover:bg-white/[0.06] md:hidden" onClick={() => setMobileOpen((open) => !open)} aria-label={mobileOpen ? 'Close navigation menu' : 'Open navigation menu'} aria-expanded={mobileOpen} aria-controls="mobile-navigation">{mobileOpen ? <X size={18} /> : <Menu size={18} />}</button>
      </div>

      {mobileOpen && <nav id="mobile-navigation" aria-label="Mobile navigation" className="border-t border-white/[0.1] bg-[#100d16] px-4 py-2 md:hidden"><div className="page-frame grid grid-cols-2">{[{ href: '/', label: 'Overview' }, ...navLinks].map(({ href, label }) => <Link key={href} href={href} onClick={() => setMobileOpen(false)} aria-current={isActive(href) ? 'page' : undefined} className={`border-b border-white/[0.07] px-2 py-3 text-sm font-semibold ${isActive(href) ? 'text-[var(--pl-green)]' : 'text-[var(--muted)]'}`}>{label}</Link>)}</div></nav>}
    </header>
  )
}
