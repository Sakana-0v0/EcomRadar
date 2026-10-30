/**
 * 多租户切换器 + 限流状态展示.
 *
 * 切换 tenant 后触发新的请求, 可观察:
 * - 不同租户的独立凭证 / 独立限流配额
 * - 超过 10 req/min 时后端返回 429
 */
import { useState } from 'react'

export const TENANTS = [
  { id: 'tenant_1', label: '声立方品牌', quota: '10 req/min', note: '主租户' },
  { id: 'tenant_2', label: '慕斯美妆', quota: '10 req/min', note: '美妆租户' },
  { id: 'tenant_3', label: '数码优品', quota: '10 req/min', note: '3C 租户' },
  { id: 'tenant_overflow', label: '压测租户', quota: '10 req/min', note: '易触发 429' },
]

export default function TenantSwitcher({ tenant, onChange, disabled, lastStatus }) {
  const [open, setOpen] = useState(false)
  const current = TENANTS.find((t) => t.id === tenant) || TENANTS[0]

  return (
    <div className="relative">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        className="btn-ghost min-w-[190px] justify-between"
      >
        <span className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-radar-400" />
          <span className="text-left">
            <span className="block text-[10px] leading-tight text-ink-500">租户</span>
            <span className="block text-xs leading-tight text-ink-100">
              {current.label} · {current.id}
            </span>
          </span>
        </span>
        <span className="text-[10px] text-ink-500">▾</span>
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-20 mt-1 w-64 overflow-hidden rounded-lg border border-ink-700 bg-ink-900 shadow-2xl shadow-black/50">
            {TENANTS.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => {
                  onChange(t.id)
                  setOpen(false)
                }}
                className={`flex w-full items-center justify-between px-3 py-2 text-left text-xs transition-colors hover:bg-ink-800 ${
                  t.id === tenant ? 'bg-ink-800 text-radar-300' : 'text-ink-300'
                }`}
              >
                <span>
                  <span className="block">{t.label}</span>
                  <span className="block font-mono text-[10px] text-ink-600">{t.id}</span>
                </span>
                <span className="text-right">
                  <span className="block text-[10px] text-ink-500">{t.quota}</span>
                  <span className="block text-[10px] text-ink-600">{t.note}</span>
                </span>
              </button>
            ))}
          </div>
        </>
      )}

      {lastStatus && (
        <div className="mt-1 text-[10px] text-ink-600">
          {lastStatus}
        </div>
      )}
    </div>
  )
}
