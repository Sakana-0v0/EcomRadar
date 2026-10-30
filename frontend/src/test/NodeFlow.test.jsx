import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import NodeFlow, { NODES } from '../components/NodeFlow'

describe('NodeFlow', () => {
  it('renders all 6 pipeline nodes', () => {
    render(<NodeFlow />)
    expect(NODES).toHaveLength(6)
    for (const n of NODES) {
      expect(screen.getByText(n.label)).toBeInTheDocument()
    }
  })

  it('marks the active node distinctly', () => {
    render(<NodeFlow activeNode="rag" />)
    expect(screen.getByText('RAG')).toBeInTheDocument()
  })

  it('shows paused badge when paused', () => {
    render(<NodeFlow paused />)
    expect(screen.getByText(/等待人工审批/)).toBeInTheDocument()
  })

  it('shows active node badge when running', () => {
    render(<NodeFlow activeNode="writer" />)
    expect(screen.getByText(/writer/)).toBeInTheDocument()
  })

  it('node order matches backend PIPELINE_ORDER', () => {
    const ids = NODES.map((n) => n.id)
    expect(ids).toEqual([
      'scraper',
      'extractor',
      'rag',
      'writer',
      'evaluator',
      'publisher',
    ])
  })

  it('shows retry hint on evaluator node', () => {
    render(<NodeFlow />)
    expect(screen.getByText(/重试/)).toBeInTheDocument()
  })
})
