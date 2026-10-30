/**
 * 三级降级链路可视化.
 *
 * 展示 Scraper 的降级策略:
 *   direct (直接 HTTP) → jina (第三方 reader) → mock (本地兜底)
 *
 * 以及反爬合规组件: robots.txt 检查 + 令牌桶限流.
 */
const LEVELS = [
  {
    id: 'direct',
    label: 'Direct',
    cn: '直接抓取',
    desc: 'httpx + 浏览器 Headers + UA 池轮换',
    color: 'emerald',
  },
  {
    id: 'jina',
    label: 'Jina Reader',
    cn: '第三方兜底',
    desc: 'r.jina.ai 渲染, 绕过 JS 页面',
    color: 'amber',
  },
  {
    id: 'mock',
    label: 'Mock',
    cn: '本地兜底',
    desc: '虚构商品数据, 保证流程不中断',
    color: 'rose',
  },
]

const COLOR = {
  emerald: {
    ring: 'border-emerald-600/60',
    bg: 'bg-emerald-500/10',
    text: 'text-emerald-300',
    dot: 'bg-emerald-500',
  },
  amber: {
    ring: 'border-amber-600/60',
    bg: 'bg-amber-500/10',
    text: 'text-amber-300',
    dot: 'bg-amber-500',
  },
  rose: {
    ring: 'border-rose-600/60',
    bg: 'bg-rose-500/10',
    text: 'text-rose-300',
    dot: 'bg-rose-500',
  },
}

export default function DegradationTimeline({ activeLevel = null, attempts = [] }) {
  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">抓取降级链路 · 反爬合规</span>
        <span className="tag bg-ink-800 text-ink-400">direct → jina → mock</span>
      </div>

      <div className="space-y-2 p-4">
        {LEVELS.map((lvl, i) => {
          const c = COLOR[lvl.color]
          const isActive = activeLevel === lvl.id
          const wasTried = attempts.includes(lvl.id)
          return (
            <div
              key={lvl.id}
              className={`flex items-start gap-3 rounded-lg border px-3 py-2.5 transition-all duration-300 ${
                isActive ? `${c.ring} ${c.bg}` : 'border-ink-800 bg-ink-950/40'
              }`}
            >
              <span
                className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${
                  isActive ? `${c.bg} ${c.text} ${c.ring} border` : 'border border-ink-700 bg-ink-900 text-ink-600'
                }`}
              >
                {i + 1}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-semibold ${isActive ? c.text : 'text-ink-300'}`}>
                    {lvl.label}
                  </span>
                  <span className="text-[10px] text-ink-600">{lvl.cn}</span>
                  {wasTried && !isActive && (
                    <span className="tag bg-ink-800 text-[9px] text-ink-500">已尝试</span>
                  )}
                  {isActive && (
                    <span className={`tag ${c.bg} ${c.text} text-[9px]`}>生效中</span>
                  )}
                </div>
                <div className="mt-0.5 text-[10px] leading-tight text-ink-500">{lvl.desc}</div>
              </div>
            </div>
          )
        })}

        <div className="mt-3 grid grid-cols-2 gap-2 border-t border-ink-800 pt-3">
          <div className="rounded-lg bg-ink-950/50 px-3 py-2">
            <div className="text-[10px] text-ink-500">robots.txt 合规</div>
            <div className="mt-0.5 text-[11px] text-emerald-400">RFC 9309 ✓ · 最长匹配优先</div>
          </div>
          <div className="rounded-lg bg-ink-950/50 px-3 py-2">
            <div className="text-[10px] text-ink-500">限流策略</div>
            <div className="mt-0.5 text-[11px] text-radar-400">令牌桶 ≤ 1 req/s · 域名隔离</div>
          </div>
        </div>
      </div>
    </div>
  )
}
