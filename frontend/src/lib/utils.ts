import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { format, parseISO, isValid } from 'date-fns'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function getOutcomeLabel(outcome: string) {
  return outcome === 'H' ? 'Home Win' : outcome === 'D' ? 'Draw' : 'Away Win'
}

export function getConfidenceBadgeColor(confidence: string) {
  return confidence === 'high'
    ? 'bg-green-100 text-green-800'
    : confidence === 'medium'
    ? 'bg-yellow-100 text-yellow-800'
    : 'bg-red-100 text-red-800'
}

export function getResultColor(result: 'W' | 'D' | 'L') {
  return result === 'W'
    ? 'bg-green-500 text-white'
    : result === 'D'
    ? 'bg-yellow-400 text-white'
    : 'bg-red-500 text-white'
}

export function formatMatchDate(dateStr: string) {
  try {
    const date = parseISO(dateStr)
    if (!isValid(date)) return dateStr
    return format(date, 'EEE dd MMM yyyy, HH:mm')
  } catch {
    return dateStr
  }
}

export function formatShortDate(dateStr: string) {
  try {
    const date = parseISO(dateStr)
    if (!isValid(date)) return dateStr
    return format(date, 'dd MMM')
  } catch {
    return dateStr
  }
}

export function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`
}

export function getOutcomeTextColor(outcome: 'H' | 'D' | 'A') {
  return outcome === 'H'
    ? 'text-green-600'
    : outcome === 'D'
    ? 'text-yellow-600'
    : 'text-blue-600'
}
