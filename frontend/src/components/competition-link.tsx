'use client'

import Link from 'next/link'
import type { ComponentProps } from 'react'
import { useCompetition, withCompetition } from '@/lib/competition'

export default function CompetitionLink({ href, ...props }: ComponentProps<typeof Link>) {
  const { league } = useCompetition()
  return <Link href={typeof href === 'string' ? withCompetition(href, league) : href} {...props} />
}
