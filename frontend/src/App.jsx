import { useCallback, useEffect, useRef, useState } from 'react'
import { DEFAULT_TENANT, parseTaskId, resumeTask, streamReport } from './api/client'
import NodeFlow from './components/NodeFlow'
import ScorePanel from './components/ScorePanel'
import ReportViewer from './components/ReportViewer'
import TenantSwitcher from './components/TenantSwitcher'
import DegradationTimeline from './components/DegradationTimeline'
import { EventLog, MetricsPanel } from './components/MetricsPanel'

const DEMO_URLS = [
  'https://item.jd.com/100012345678.html',
  'https://detail.tmall.com/item.htm?id=655000012345',
  'https://mobile.yangkeduo.com/goods.html?goods_id=123456789',
]

const now = () => new Date().toLocaleTimeString('zh-CN', { hour12: false })

export default function App() {
  const [tenant, setTenant] = useState(DEFAULT_TENANT)
  const [running, setRunning] = useState(false)
  const [report, setReport] = useState('')
  const [score, setScore] = useState(0)
  const [dimensions, setDimensions] = useState({})
  const [passed, setPassed] = useState(null)
  const [activeNode, setActiveNode] = useState(null)
  const [visited, setVisited] = useState([])
  const [paused, setPaused] = useState(false)
  const [taskId, setTaskId] = useState(null)
  const [published, setPublished] = useState([])
  const [events, setEvents] = useState([])
  const [degradeLevel, setDegradeLevel] = useState(null)
  const [attempts, setAttempts] = useState([])
  const esRef = useRef(null)

  const log = useCallback((kind, message) => {
    setEvents((prev) => [...prev.slice(-99), { kind, message, ts: now() }])
  }, [])

  const reset = useCallback(() => {
    setReport('')
    setScore(0)
    setDimensions({})
    setPassed(null)
    setActiveNode(null)
    setVisited([])
    setPaused(false)
    setTaskId(null)
    setPublished([])
    setDegradeLevel(null)
    setAttempts([])
  }, [])

  useEffect(() => () => esRef.current?.close(), [])

  const markNode = useCallback((id) => {
    setActiveNode(id)
    setVisited((prev) => (prev.includes(id) ? prev : [...prev, id]))
  }, [])

  const handleReport = useCallback((data) => {
    setReport((prev) => (prev ? `${prev}\n${data}` : data))
    markNode('writer')
  }, [markNode])

  const handleScore = useCallback((value) => {
    setScore(value)
    setPassed(value >= 75)
    markNode('evaluator')
  }, [markNode])

  const handlePaused = useCallback((data) => {
    const tid = parseTaskId(data)
    setTaskId(tid)
    setPaused(true)
    setActiveNode('publisher')
    log('warn', `流程已暂停, 等待人工审批 (task_id=${tid})`)
  }, [log])

  const handlePublished = useCallback((data) => {
    const channels = data ? data.split(',').filter(Boolean) : []
    setPublished(channels)
    markNode('publisher')
    log('success', `报告已推送到: ${channels.join(' / ') || '(无)'}`)
  }, [log, markNode])

  const handleDone = useCallback((tid) => {
    setRunning(false)
    setActiveNode(null)
    log('success', `任务完成 (task_id=${tid || taskId || '-'})`)
  }, [log, taskId])

  const handleError = useCallback((msg) => {
    setRunning(false)
    log('error', msg)
  }, [log])

  const start = useCallback(() => {
    if (running) return
    reset()
    setRunning(true)
    setAttempts(['direct'])
    setDegradeLevel('direct')
    markNode('scraper')
    log('info', `启动流水线 · tenant=${tenant} · ${DEMO_URLS.length} 个 URL`)

    const es = streamReport(DEMO_URLS, tenant, {
      onReport: handleReport,
      onScore: handleScore,
      onPaused: handlePaused,
      onPublished: handlePublished,
      onDone: handleDone,
      onError: handleError,
    })
    esRef.current = es
  }, [
    running, reset, tenant, markNode, log,
    handleReport, handleScore, handlePaused, handlePublished, handleDone, handleError,
  ])

  const approve = useCallback(async () => {
    if (!taskId) return
    try {
      log('info', `提交审批: approved=true`)
      await resumeTask(taskId, true, tenant)
      setPaused(false)
      log('success', '审批通过, Publisher 执行中')
    } catch (e) {
      log('error', `审批失败: ${e.message}`)
    }
  }, [taskId, tenant, log])

  const reject = useCallback(async () => {
    if (!taskId) return
    try {
      log('info', `提交审批: approved=false`)
      await resumeTask(taskId, false, tenant)
      setPaused(false)
      log('warn', '审批驳回, 已跳过发布')
    } catch (e) {
      log('error', `驳回失败: ${e.message}`)
    }
  }, [taskId, tenant, log])

  return (
    <div className="min-h-screen bg-ink-950">
      {/* ---------- Header ---------- */}
      <header className="sticky top-0 z-30 border-b border-ink-800 bg-ink-950/90 backdrop-blur">
        <div className="mx-auto flex max-w-[1600px] items-center gap-4 px-5 py-3">
          <div className="flex items-center gap-2.5">
            <div className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-radar-600/20 ring-1 ring-radar-500/40">
              <span className="text-base">📡</span>
              {running && (
                <span className="absolute inset-0 animate-pulse-ring rounded-xl ring-1 ring-radar-500/60" />
              )}
            </div>
            <div>
              <div className="text-sm font-bold leading-tight text-white">EcomRadar</div>
              <div className="text-[10px] leading-tight text-ink-500">
                多智能体电商竞品监控研报系统
              </div>
            </div>
          </div>

          <div className="ml-auto flex items-center gap-2.5">
            <TenantSwitcher tenant={tenant} onChange={setTenant} disabled={running} />
            <button type="button" onClick={start} disabled={running} className="btn-primary">
              {running ? '⏳ 运行中…' : '▶ 启动流水线'}
            </button>
          </div>
        </div>
      </header>

      {/* ---------- Body ---------- */}
      <main className="mx-auto max-w-[1600px] space-y-4 px-5 py-5">
        <NodeFlow
          activeNode={activeNode}
          visited={visited}
          paused={paused}
        />

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_380px]">
          {/* 左列 */}
          <div className="space-y-4">
            <ReportViewer
              report={report}
              paused={paused}
              taskId={taskId}
              onApprove={approve}
              onReject={reject}
              publishedChannels={published}
            />
          </div>

          {/* 右列 */}
          <div className="space-y-4">
            <ScorePanel score={score} dimensions={dimensions} passed={passed} />
            <DegradationTimeline activeLevel={degradeLevel} attempts={attempts} />
            <MetricsPanel />
            <EventLog events={events} />
          </div>
        </div>

        <footer className="pb-6 pt-2 text-center text-[10px] text-ink-700">
          EcomRadar · LangGraph 6 节点状态机 · MCP 双通道推送 · 混合检索 ·{' '}
          <a
            href="https://github.com/Sakana-0v0/EcomRadar"
            target="_blank"
            rel="noreferrer"
            className="text-ink-600 underline decoration-ink-800 underline-offset-2 hover:text-radar-400"
          >
            GitHub
          </a>
        </footer>
      </main>
    </div>
  )
}
