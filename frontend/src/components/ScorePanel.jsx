/**
 * 5 维度质量评分雷达图 + 评分条.
 *
 * 对应后端 app/services/evaluator.py DIMENSION_WEIGHTS:
 * factuality 25% / structure 25% / price_comparison 20%
 * sku_coverage 15% / action_quality 15%
 */
import { useMemo } from 'react'

export const DIMENSIONS = [
  { key: 'factuality', label: '事实忠实度', weight: 0.25, color: '#598bff' },
  { key: 'structure', label: '结构完整性', weight: 0.25, color: '#8eb4ff' },
  { key: 'price_comparison', label: '价格对比完整性', weight: 0.2, color: '#3362ff' },
  { key: 'sku_coverage', label: 'SKU 覆盖度', weight: 0.15, color: '#1c3df5' },
  { key: 'action_quality', label: '行动建议质量', weight: 0.15, color: '#bcd2ff' },
]

export const THRESHOLD = 75

function RadarChart({ values, size = 220 }) {
  const cx = size / 2
  const cy = size / 2
  const radius = size / 2 - 38
  const n = DIMENSIONS.length

  const pointAt = (index, ratio) => {
    const angle = (Math.PI * 2 * index) / n - Math.PI / 2
    return [cx + Math.cos(angle) * radius * ratio, cy + Math.sin(angle) * radius * ratio]
  }

  const path = (ratios) =>
    ratios.map((r, i) => `${i === 0 ? 'M' : 'L'}${pointAt(i, r).join(',')}`).join(' ') + ' Z'

  const rings = [0.25, 0.5, 0.75, 1]
  const dataRatios = DIMENSIONS.map((d) => Math.max(0.04, values[d.key] ?? 0))

  return (
    <svg width={size} height={size} className="shrink-0">
      {rings.map((r) => (
        <path
          key={r}
          d={path(DIMENSIONS.map(() => r))}
          fill="none"
          stroke="#1f2733"
          strokeWidth="1"
        />
      ))}
      {DIMENSIONS.map((d, i) => {
        const [x, y] = pointAt(i, 1)
        return <line key={d.key} x1={cx} y1={cy} x2={x} y2={y} stroke="#1f2733" strokeWidth="1" />
      })}

      <path d={path(dataRatios)} fill="rgba(51,98,255,0.18)" stroke="#598bff" strokeWidth="2" />

      {DIMENSIONS.map((d, i) => {
        const [x, y] = pointAt(i, dataRatios[i])
        return <circle key={d.key} cx={x} cy={y} r="3.5" fill={d.color} />
      })}

      {DIMENSIONS.map((d, i) => {
        const [x, y] = pointAt(i, 1.22)
        return (
          <text
            key={d.key}
            x={x}
            y={y}
            textAnchor="middle"
            dominantBaseline="middle"
            className="fill-ink-400"
            style={{ fontSize: 9 }}
          >
            {d.label}
          </text>
        )
      })}
    </svg>
  )
}

export default function ScorePanel({ score = 0, dimensions = {}, passed = null, onRetry }) {
  const values = useMemo(() => {
    const out = {}
    for (const d of DIMENSIONS) out[d.key] = dimensions[d.key] ?? 0
    return out
  }, [dimensions])

  const effectivePass = passed !== null ? passed : score >= THRESHOLD
  const ratio = Math.min(1, score / 100)

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">质量评分 · 5 维度</span>
        {effectivePass ? (
          <span className="tag bg-emerald-500/15 text-emerald-300">✓ 通过门控 (≥{THRESHOLD})</span>
        ) : (
          <span className="tag bg-rose-500/15 text-rose-300">✗ 低于阈值 → 重试</span>
        )}
      </div>

      <div className="flex flex-col items-center gap-3 p-4 sm:flex-row sm:items-start">
        <RadarChart values={values} />

        <div className="w-full flex-1 space-y-2.5">
          <div className="flex items-baseline gap-2">
            <span className="text-4xl font-bold tabular-nums text-white">{score}</span>
            <span className="text-sm text-ink-500">/ 100</span>
          </div>

          <div className="h-1.5 w-full overflow-hidden rounded-full bg-ink-800">
            <div
              className={`h-full rounded-full transition-all duration-700 ${
                effectivePass ? 'bg-emerald-500' : 'bg-rose-500'
              }`}
              style={{ width: `${ratio * 100}%` }}
            />
          </div>

          {DIMENSIONS.map((d) => {
            const v = values[d.key] ?? 0
            return (
              <div key={d.key} className="flex items-center gap-2">
                <span className="w-24 shrink-0 truncate text-[11px] text-ink-400">{d.label}</span>
                <div className="h-1 flex-1 overflow-hidden rounded-full bg-ink-800">
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{ width: `${v * 100}%`, background: d.color }}
                  />
                </div>
                <span className="w-9 shrink-0 text-right text-[10px] tabular-nums text-ink-500">
                  {(v * 100).toFixed(0)}%
                </span>
                <span className="w-8 shrink-0 text-right text-[10px] text-ink-600">
                  {(d.weight * 100).toFixed(0)}%
                </span>
              </div>
            )
          })}

          {onRetry && (
            <button type="button" onClick={onRetry} className="btn-ghost mt-1 w-full">
              ↻ 触发 Writer 重写
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
