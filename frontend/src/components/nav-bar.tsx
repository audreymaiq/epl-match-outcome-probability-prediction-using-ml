'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import { BarChart2, Home, Users, Trophy, Brain, Menu, X } from 'lucide-react'
import { useState } from 'react'

const navLinks = [
  { href: '/', label: 'Home', icon: Home },
  { href: '/matches', label: 'Matches', icon: Trophy },
  { href: '/teams', label: 'Teams', icon: Users },
  { href: '/predictions', label: 'Predictions', icon: BarChart2 },
  { href: '/model', label: 'Model', icon: Brain },
]

export function NavBar() {
  const pathname = usePathname()
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <nav className="sticky top-0 z-50 w-full shadow-md" style={{ backgroundColor: 'var(--pl-purple)' }}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo / Brand */}
          <Link href="/" className="flex items-center gap-2 group">
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm"
              style={{ backgroundColor: 'var(--pl-green)', color: 'var(--pl-purple)' }}
            >
              PL
            </div>
            <span className="text-white font-bold text-lg hidden sm:block tracking-tight">
              PL Predictions
            </span>
          </Link>

          {/* Desktop nav links */}
          <div className="hidden md:flex items-center gap-1">
            {navLinks.map(({ href, label, icon: Icon }) => {
              const active = pathname === href || (href !== '/' && pathname.startsWith(href))
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                    active
                      ? 'text-white'
                      : 'text-purple-200 hover:text-white hover:bg-white/10'
                  )}
                  style={active ? { backgroundColor: 'rgba(0, 255, 133, 0.2)', color: 'var(--pl-green)' } : {}}
                >
                  <Icon size={15} />
                  {label}
                </Link>
              )
            })}
          </div>

          {/* Mobile hamburger */}
          <button
            className="md:hidden text-white p-2 rounded-lg hover:bg-white/10"
            onClick={() => setMobileOpen((v) => !v)}
            aria-label="Toggle menu"
          >
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="md:hidden border-t border-white/10 px-4 pb-4 pt-2 space-y-1">
          {navLinks.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || (href !== '/' && pathname.startsWith(href))
            return (
              <Link
                key={href}
                href={href}
                onClick={() => setMobileOpen(false)}
                className={cn(
                  'flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                  active
                    ? 'text-white'
                    : 'text-purple-200 hover:text-white hover:bg-white/10'
                )}
                style={active ? { backgroundColor: 'rgba(0, 255, 133, 0.2)', color: 'var(--pl-green)' } : {}}
              >
                <Icon size={16} />
                {label}
              </Link>
            )
          })}
        </div>
      )}
    </nav>
  )
}
