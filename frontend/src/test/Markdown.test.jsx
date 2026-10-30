import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import Markdown from '../components/Markdown'

describe('Markdown', () => {
  it('renders nothing for empty content', () => {
    const { container } = render(<Markdown content="" />)
    expect(container.innerHTML).toBe('')
  })

  it('renders h1', () => {
    render(<Markdown content={'# 竞品周报'} />)
    expect(screen.getByText('竞品周报')).toBeInTheDocument()
  })

  it('renders h2', () => {
    render(<Markdown content={'## Executive Summary'} />)
    expect(screen.getByText('Executive Summary')).toBeInTheDocument()
  })

  it('renders paragraphs', () => {
    render(<Markdown content={'这是一段普通文本内容'} />)
    expect(screen.getByText('这是一段普通文本内容')).toBeInTheDocument()
  })

  it('renders bold as strong element', () => {
    const { container } = render(<Markdown content={'**粗体文字**'} />)
    expect(container.querySelector('strong')).not.toBeNull()
    expect(screen.getByText('粗体文字')).toBeInTheDocument()
  })

  it('renders inline code', () => {
    const { container } = render(<Markdown content={'`code_snippet`'} />)
    expect(container.querySelector('code')).not.toBeNull()
  })

  it('renders unordered list', () => {
    const { container } = render(<Markdown content={'- 项目一\n- 项目二'} />)
    expect(container.querySelectorAll('li')).toHaveLength(2)
  })

  it('renders ordered list', () => {
    const { container } = render(<Markdown content={'1. 第一条\n2. 第二条'} />)
    expect(container.querySelectorAll('ol li')).toHaveLength(2)
  })

  it('renders table with header and rows', () => {
    const md = ['| 品牌 | 价格 |', '|------|------|', '| 小度 | 329 |', '| 天猫 | 263 |'].join(
      '\n',
    )
    const { container } = render(<Markdown content={md} />)
    expect(container.querySelector('table')).not.toBeNull()
    expect(container.querySelectorAll('th')).toHaveLength(2)
    expect(container.querySelectorAll('tbody tr')).toHaveLength(2)
  })

  it('renders blockquote', () => {
    const { container } = render(<Markdown content={'> 引用内容'} />)
    expect(container.querySelector('blockquote')).not.toBeNull()
  })

  it('renders horizontal rule', () => {
    const { container } = render(<Markdown content={'---'} />)
    expect(container.querySelector('hr')).not.toBeNull()
  })

  it('renders full competitor report structure', () => {
    const md = [
      '# 竞品周报 - 智能音箱',
      '',
      '## Executive Summary',
      '',
      '本周天猫精灵降价 12%。',
      '',
      '## 竞品矩阵对比',
      '',
      '| 品牌 | 价格 |',
      '|------|------|',
      '| 小度 | 329 |',
      '',
      '## 行动建议',
      '',
      '**1. 错位定价** — 音质升级',
    ].join('\n')
    const { container } = render(<Markdown content={md} />)
    expect(container.querySelector('table')).not.toBeNull()
    expect(container.querySelector('strong')).not.toBeNull()
    expect(screen.getByText('竞品周报 - 智能音箱')).toBeInTheDocument()
  })
})
