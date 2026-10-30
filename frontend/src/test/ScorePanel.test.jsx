import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import ScorePanel, { DIMENSIONS, THRESHOLD } from '../components/ScorePanel'

describe('ScorePanel', () => {
  it('renders 5 dimensions with weights summing to 1', () => {
    render(<ScorePanel score={80} dimensions={{}} />)
    expect(DIMENSIONS).toHaveLength(5)
    const total = DIMENSIONS.reduce((s, d) => s + d.weight, 0)
    expect(total).toBeCloseTo(1.0, 5)
  })

  it('shows the score', () => {
    render(<ScorePanel score={86} dimensions={{}} />)
    expect(screen.getByText('86')).toBeInTheDocument()
  })

  it('shows passed badge when score >= threshold', () => {
    render(<ScorePanel score={THRESHOLD} dimensions={{}} />)
    expect(screen.getByText(/通过门控/)).toBeInTheDocument()
  })

  it('shows retry badge when score < threshold', () => {
    render(<ScorePanel score={60} dimensions={{}} />)
    expect(screen.getByText(/低于阈值/)).toBeInTheDocument()
  })

  it('renders all dimension labels', () => {
    render(<ScorePanel score={80} dimensions={{}} />)
    for (const d of DIMENSIONS) {
      // 标签在雷达图 SVG 与进度条中各出现一次
      expect(screen.getAllByText(d.label).length).toBeGreaterThan(0)
    }
  })

  it('shows retry button only when onRetry provided', () => {
    const { unmount } = render(<ScorePanel score={80} dimensions={{}} />)
    expect(screen.queryByText(/触发 Writer 重写/)).not.toBeInTheDocument()
    unmount()

    render(<ScorePanel score={80} dimensions={{}} onRetry={() => {}} />)
    expect(screen.getByText(/触发 Writer 重写/)).toBeInTheDocument()
  })
})
