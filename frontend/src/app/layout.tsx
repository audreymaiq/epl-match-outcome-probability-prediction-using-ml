import type { Metadata } from 'next'
import './globals.css'
import { Providers } from './providers'
import { NavBar } from '@/components/nav-bar'

export const metadata: Metadata = {
  title: {
    default: 'PL Predictions',
    template: '%s | PL Predictions',
  },
  description: 'Premier League match outcome probability predictions powered by machine learning.',
  keywords: ['Premier League', 'football', 'predictions', 'machine learning', 'match outcomes'],
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen flex flex-col">
        <Providers>
          <NavBar />
          <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
            {children}
          </main>
          <footer
            className="mt-auto border-t py-6 text-center text-sm text-gray-500"
            style={{ borderColor: 'var(--card-border)' }}
          >
            <p>
              PL Predictions &mdash; Built with Next.js 14 &amp; Machine Learning
            </p>
            <p className="mt-1 text-xs opacity-60">
              For entertainment purposes only. Not affiliated with the Premier League.
            </p>
          </footer>
        </Providers>
      </body>
    </html>
  )
}
