'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Suspense, useState, type ReactNode } from 'react'
import { CompetitionProvider } from '@/lib/competition'

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000, // 1 minute
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      })
  )

  return (
    <QueryClientProvider client={queryClient}><Suspense fallback={<p className="page-frame py-8 text-white">Loading match centre…</p>}><CompetitionProvider>{children}</CompetitionProvider></Suspense></QueryClientProvider>
  )
}
