/**
 * 轻量 Markdown 渲染器 (零依赖).
 *
 * 支持: 标题 / 段落 / 粗体 / 斜体 / 行内代码 / 有序无序列表 /
 *       表格 / 引用 / 分隔线 / 代码块
 *
 * 与后端 app/services/publisher/markdown_to_blocks.py 的元素集一致.
 */
import React from 'react'

function renderInline(text, keyPrefix) {
  const nodes = []
  const pattern = /(\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`)/g
  let last = 0
  let match
  let idx = 0

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) {
      nodes.push(text.slice(last, match.index))
    }
    const key = `${keyPrefix}-i${idx++}`
    if (match[2]) {
      nodes.push(
        <strong key={key} className="font-semibold text-white">
          {match[2]}
        </strong>,
      )
    } else if (match[3]) {
      nodes.push(
        <em key={key} className="italic text-ink-300">
          {match[3]}
        </em>,
      )
    } else if (match[4]) {
      nodes.push(
        <code key={key} className="rounded bg-ink-800 px-1.5 py-0.5 font-mono text-xs text-radar-200">
          {match[4]}
        </code>,
      )
    }
    last = pattern.lastIndex
  }
  if (last < text.length) nodes.push(text.slice(last))
  return nodes
}

function splitRow(line) {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((c) => c.trim())
}

const isTableSep = (line) => /^\s*\|?[\s:-]*-{2,}[\s:|-]*\|?\s*$/.test(line)

export default function Markdown({ content }) {
  if (!content) return null

  const lines = content.split('\n')
  const blocks = []
  let i = 0
  let key = 0

  while (i < lines.length) {
    const line = lines[i]
    const trimmed = line.trim()

    if (!trimmed) {
      i++
      continue
    }

    // 代码块
    if (trimmed.startsWith('```')) {
      const buf = []
      i++
      while (i < lines.length && !lines[i].trim().startsWith('```')) {
        buf.push(lines[i])
        i++
      }
      i++
      blocks.push(
        <pre
          key={`c${key++}`}
          className="my-3 overflow-x-auto rounded-lg border border-ink-800 bg-ink-950 p-3 font-mono text-xs leading-relaxed text-ink-200"
        >
          {buf.join('\n')}
        </pre>,
      )
      continue
    }

    // 表格
    if (trimmed.startsWith('|') && i + 1 < lines.length && isTableSep(lines[i + 1])) {
      const header = splitRow(trimmed)
      i += 2
      const rows = []
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        rows.push(splitRow(lines[i].trim()))
        i++
      }
      blocks.push(
        <div key={`t${key++}`} className="my-3 overflow-x-auto rounded-lg border border-ink-800">
          <table className="w-full border-collapse text-xs">
            <thead>
              <tr>
                {header.map((h, hi) => (
                  <th
                    key={hi}
                    className="border-b border-ink-700 bg-ink-800/80 px-2.5 py-2 text-left font-semibold text-ink-100"
                  >
                    {renderInline(h, `th${hi}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => (
                <tr key={ri} className={ri % 2 === 1 ? 'bg-ink-900/40' : ''}>
                  {header.map((_, ci) => (
                    <td key={ci} className="border-b border-ink-800 px-2.5 py-2 align-top text-ink-200">
                      {renderInline(row[ci] ?? '', `td${ri}-${ci}`)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      )
      continue
    }

    // 标题
    const h = /^(#{1,6})\s+(.*)$/.exec(trimmed)
    if (h) {
      const level = h[1].length
      const content2 = h[2]
      const cls = [
        'my-3 font-bold text-white',
        level === 1 ? 'border-b border-ink-800 pb-2 text-xl' : '',
        level === 2 ? 'mt-5 text-base text-radar-300' : '',
        level === 3 ? 'mt-4 text-sm text-ink-100' : '',
        level >= 4 ? 'mt-3 text-xs text-ink-300' : '',
      ]
        .filter(Boolean)
        .join(' ')
      const Tag = `h${Math.min(level, 6)}`
      blocks.push(
        <Tag key={`h${key++}`} className={cls}>
          {renderInline(content2, `h${key}`)}
        </Tag>,
      )
      i++
      continue
    }

    // 分隔线
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      blocks.push(<hr key={`hr${key++}`} className="my-4 border-ink-800" />)
      i++
      continue
    }

    // 引用
    if (trimmed.startsWith('>')) {
      const buf = []
      while (i < lines.length && lines[i].trim().startsWith('>')) {
        buf.push(lines[i].trim().replace(/^>\s?/, ''))
        i++
      }
      blocks.push(
        <blockquote
          key={`q${key++}`}
          className="my-3 border-l-2 border-radar-600 pl-3 text-ink-300 italic"
        >
          {renderInline(buf.join(' '), `q${key}`)}
        </blockquote>,
      )
      continue
    }

    // 列表
    const ul = /^[-*+]\s+(.*)$/.exec(trimmed)
    const ol = /^(\d+)\.\s+(.*)$/.exec(trimmed)
    if (ul || ol) {
      const ordered = Boolean(ol)
      const items = []
      while (i < lines.length) {
        const t = lines[i].trim()
        const mu = /^[-*+]\s+(.*)$/.exec(t)
        const mo = /^(\d+)\.\s+(.*)$/.exec(t)
        if (ordered && mo) items.push(mo[2])
        else if (!ordered && mu) items.push(mu[1])
        else break
        i++
      }
      const Tag = ordered ? 'ol' : 'ul'
      blocks.push(
        <Tag key={`l${key++}`} className="my-2 list-disc space-y-1 pl-5 marker:text-ink-500">
          {items.map((it, ii) => (
            <li key={ii}>{renderInline(it, `li${ii}`)}</li>
          ))}
        </Tag>,
      )
      continue
    }

    // 段落
    const buf = []
    while (
      i < lines.length &&
      lines[i].trim() &&
      !lines[i].trim().startsWith('#') &&
      !lines[i].trim().startsWith('|') &&
      !lines[i].trim().startsWith('>') &&
      !/^[-*+]\s+/.test(lines[i].trim()) &&
      !/^\d+\.\s+/.test(lines[i].trim()) &&
      !lines[i].trim().startsWith('```')
    ) {
      buf.push(lines[i].trim())
      i++
    }
    if (buf.length) {
      blocks.push(
        <p key={`p${key++}`} className="my-2 leading-relaxed text-ink-200">
          {renderInline(buf.join(' '), `p${key}`)}
        </p>,
      )
    } else {
      i++
    }
  }

  return <div className="md-body">{blocks}</div>
}
