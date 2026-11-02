import type { Metadata } from 'next'
import './globals.css'
import { Providers } from './providers'
import { NavBar } from '@/components/nav-bar'

export const metadata: Metadata = {
  title: {
    default: 'Matchday | Premier League',
    template: '%s | Matchday',
  },
  description: 'Premier League fixtures, results, club form and match outcome probabilities.',
  keywords: ['Premier League', 'football', 'fixtures', 'team form', 'match probabilities'],
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body className="flex min-h-screen flex-col">
        <Providers>
          <NavBar />
          <div className="flex-1">{children}</div>
          <footer className="mt-auto border-t border-[var(--border)] bg-[#100d16]/70">
            <div className="page-frame flex flex-col gap-2 py-6 text-xs text-[var(--subtle)] sm:flex-row sm:items-center sm:justify-between">
              <p className="font-semibold tracking-wide text-[var(--muted)]">MATCHDAY <span className="font-normal text-[var(--subtle)]">/ Premier League</span></p>
              <p>Independent match data and probability estimates.</p>
            </div>
          </footer>
        </Providers>
      </body>
    </html>
  )
}
