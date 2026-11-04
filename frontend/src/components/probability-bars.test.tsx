import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ProbabilityBars } from './probability-bars'

describe('Outcome probabilities', () => {
  it('keeps each probability attached to its team and exposes accessible values', () => {
    render(<ProbabilityBars probabilities={{ home_win: 0.51, draw: 0.28, away_win: 0.21 }} predicted_outcome="H" homeTeam="Arsenal" awayTeam="Everton" />)
    expect(screen.getByRole('meter', { name: 'Arsenal Home win probability' })).toHaveAttribute('aria-valuenow', '51')
    expect(screen.getByRole('meter', { name: 'Draw Draw probability' })).toHaveAttribute('aria-valuenow', '28')
    expect(screen.getByRole('meter', { name: 'Everton Away win probability' })).toHaveAttribute('aria-valuenow', '21')
    expect(screen.getByText('51%')).toBeVisible()
  })
})
