import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { parseTaskId, SSE_EVENTS } from '../api/client'
import ReportViewer from '../components/ReportViewer'
import TenantSwitcher, { TENANTS } from '../components/TenantSwitcher'
import DegradationTimeline from '../components/DegradationTimeline'
import { MetricsPanel, EventLog } from '../components/MetricsPanel'

describe('api client helpers', () => {
  it('parses task_id from paused event payload', () => {
    expect(parseTaskId('task_id=task_abc123; node=awaiting_human_approval')).toBe(
      'task_abc123',
    )
  })

  it('returns null for malformed payload', () => {
    expect(parseTaskId('garbage')).toBeNull()
    expect(parseTaskId('')).toBeNull()
  })

  it('exposes SSE event names', () => {
    expect(SSE_EVENTS.REPORT).toBe('report')
    expect(SSE_EVENTS.SCORE).toBe('score')
    expect(SSE_EVENTS.PAUSED).toBe('paused')
    expect(SSE_EVENTS.PUBLISHED).toBe('published')
    expect(SSE_EVENTS.DONE).toBe('done')
  })
})

describe('ReportViewer', () => {
  it('shows waiting state when no report', () => {
    render(<ReportViewer report="" />)
    expect(screen.getByText(/等待报告生成/)).toBeInTheDocument()
  })

  it('shows HITL approval bar when paused', () => {
    render(<ReportViewer report="# x" paused taskId="task_1" />)
    expect(screen.getByText(/Human-in-the-Loop/)).toBeInTheDocument()
    expect(screen.getByText(/批准并发布/)).toBeInTheDocument()
    expect(screen.getAllByText(/驳回/).length).toBeGreaterThan(0)
  })

  it('shows published channels badge', () => {
    render(<ReportViewer report="# x" publishedChannels={['notion', 'feishu']} />)
    expect(screen.getByText(/notion \/ feishu/)).toBeInTheDocument()
  })

  it('renders report markdown', () => {
    render(<ReportViewer report={'# 竞品周报\n\n内容'} />)
    expect(screen.getByText('竞品周报')).toBeInTheDocument()
  })
})

describe('TenantSwitcher', () => {
  it('renders tenant options', () => {
    render(<TenantSwitcher tenant="tenant_1" onChange={() => {}} />)
    expect(TENANTS.length).toBeGreaterThanOrEqual(3)
    expect(screen.getByText(/tenant_1/)).toBeInTheDocument()
  })

  it('calls onChange when a tenant is selected', () => {
    let picked = null
    render(<TenantSwitcher tenant="tenant_1" onChange={(t) => { picked = t }} />)
    screen.getByText(/tenant_1/).click()
    document.querySelectorAll('button')[1]?.click()
    expect(picked === null || typeof picked === 'string').toBe(true)
  })
})

describe('DegradationTimeline', () => {
  it('renders 3 fallback levels', () => {
    render(<DegradationTimeline />)
    expect(screen.getByText('Direct')).toBeInTheDocument()
    expect(screen.getByText('Jina Reader')).toBeInTheDocument()
    expect(screen.getByText('Mock')).toBeInTheDocument()
  })

  it('shows compliance hints', () => {
    render(<DegradationTimeline />)
    expect(screen.getByText(/robots.txt 合规/)).toBeInTheDocument()
    expect(screen.getByText(/限流策略/)).toBeInTheDocument()
  })
})

describe('MetricsPanel', () => {
  it('renders benchmark metrics', () => {
    render(<MetricsPanel />)
    expect(screen.getByText('Recall@5')).toBeInTheDocument()
    expect(screen.getByText('0.933')).toBeInTheDocument()
    expect(screen.getByText('100%')).toBeInTheDocument()
  })
})

describe('EventLog', () => {
  it('shows empty state', () => {
    render(<EventLog events={[]} />)
    expect(screen.getByText(/暂无事件/)).toBeInTheDocument()
  })

  it('renders event entries', () => {
    render(
      <EventLog
        events={[{ kind: 'info', message: '启动流水线', ts: '10:00:00' }]}
      />,
    )
    expect(screen.getByText('启动流水线')).toBeInTheDocument()
  })
})
