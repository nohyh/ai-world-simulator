import { useEffect, useRef, useState } from 'react'
import { fetchJson, postSSE } from '../api.js'
import { useStore } from '../store.js'
import Icon from './Icon.jsx'

const CIRCLED = ['①', '②', '③', '④', '⑤', '⑥']

export default function StoryTab() {
  const worldId = useStore((s) => s.worldId)
  const bumpWorlds = useStore((s) => s.bumpWorlds)
  const [turns, setTurns] = useState(null)
  const [streamText, setStreamText] = useState('')
  const [streamAction, setStreamAction] = useState(null)
  const [choices, setChoices] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [header, setHeader] = useState({ time: '', place: '' })
  const [input, setInput] = useState('')
  const logRef = useRef(null)
  const abortRef = useRef(null)
  const submittingRef = useRef(false)

  const scrollBottom = () => {
    requestAnimationFrame(() => {
      if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
    })
  }

  // 离开页面 / 切世界时中断流
  useEffect(() => () => { abortRef.current?.abort() }, [])

  const applyDone = (ev) => {
    const history = ev.history || {}
    setTurns(history.turns || [])
    const last = (history.turns || []).slice(-1)[0]
    if (last) {
      setHeader((h) => ({ ...h, time: last.time_display, place: last.meta?.place || h.place }))
      setChoices(last.meta?.choices || [])
    }
    setStreamAction(null)
    setStreamText('')
    setBusy(false)
    bumpWorlds()
  }

  const runSSE = async (url, body) => {
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setBusy(true)
    setError('')
    try {
      await postSSE(url, body, {
        delta: (ev) => { setStreamText((s) => s + ev.text); scrollBottom() },
        meta: (ev) => {
          setChoices(ev.meta?.choices || [])
          if (ev.meta?.place) setHeader((h) => ({ ...h, place: ev.meta.place }))
        },
        done: applyDone,
        error: (ev) => { setError(ev.message || '生成失败'); setBusy(false); setStreamAction(null); setStreamText('') },
      }, ctrl.signal)
    } catch (e) {
      if (e.name !== 'AbortError') {
        setError(e.message)
        setBusy(false)
        setStreamAction(null)
      }
    } finally {
      abortRef.current = null
      submittingRef.current = false
    }
  }

  // 载入历史；无开篇则流式生成
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const h = await fetchJson(`/api/game/${worldId}/history`)
        if (cancelled) return
        setTurns(h.turns)
        if (h.turns.length > 0) {
          const last = h.turns[h.turns.length - 1]
          setHeader({ time: last.time_display, place: last.meta?.place || '' })
          setChoices(last.meta?.choices || [])
        } else {
          setHeader({ time: '', place: '' })
          setStreamText('')
          await runSSE(`/api/game/${worldId}/start`, {})
        }
      } catch (e) {
        if (!cancelled) setError(e.message)
      }
    })()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [worldId])

  const act = async (text) => {
    const v = (text ?? input).trim()
    if (!v || busy || submittingRef.current) return
    submittingRef.current = true
    setInput('')
    setChoices([])
    setStreamAction(v)
    setStreamText('')
    scrollBottom()
    await runSSE(`/api/game/${worldId}/action`, { input: v })
  }

  const retryOpening = () => {
    setError('')
    setTurns(null)
    setStreamText('')
    setStreamAction(null)
    setChoices([])
    runSSE(`/api/game/${worldId}/start`, {})
  }

  const showComposer = !busy && turns !== null

  return (
    <div className="story">
      <div className="story-head">
        {header.time && <span className="mono chip">{header.time}</span>}
        {header.place && <span className="chip dim">{header.place}</span>}
      </div>

      <div className="story-log" ref={logRef}>
        {(turns || []).map((t, i) => (
          <div key={i} className="turn">
            {t.player_action
              ? <div className="player-action"><span className="pa-label">你</span>{t.player_action}</div>
              : <div className="turn-open mono">· 开局 ·</div>}
            <div className="narrative">{t.narrative}</div>
          </div>
        ))}
        {streamAction !== null && (
          <div className="turn">
            <div className="player-action"><span className="pa-label">你</span>{streamAction}</div>
            <div className="narrative">{streamText}<span className="cursor">▍</span></div>
          </div>
        )}
        {streamAction === null && streamText && (
          <div className="turn">
            <div className="narrative">{streamText}<span className="cursor">▍</span></div>
          </div>
        )}
        {turns === null && !error && <div className="sidebar-hint">载入世界……</div>}
        {turns === null && error && (
          <div className="story-retry">
            <div className="error">{error}</div>
            <button type="button" className="btn primary" onClick={retryOpening}>重试开场</button>
          </div>
        )}
      </div>

      {busy && (
        <div className="story-generation mono">
          <span className="generation-dot" /> 正在生成剧情<span className="dots">…</span>
        </div>
      )}

      {showComposer && (
        <div className="composer">
          <div className="composer-inner">
            {error && <div className="error">{error}</div>}
            {!busy && choices.length > 0 && (
              <div className="choices">
                <div className="choices-label mono">选择一个行动，或在下方自由输入</div>
                {choices.map((c, j) => (
                  <button type="button" key={j} className="choice" onClick={() => act(c)}>
                    {CIRCLED[j]} {c}
                  </button>
                ))}
              </div>
            )}
            <div className="composer-card">
              <div className="composer-input-row">
                <textarea
                  rows={2}
                  value={input}
                  placeholder="输入你自己的行动……（Enter 发送，Shift+Enter 换行）"
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      act()
                    }
                  }}
                />
              </div>
              <div className="composer-toolbar">
                <button type="button" className="composer-add" aria-label="更多操作"><Icon name="plus" size={16} /></button>
                <span className="composer-mode"><Icon name="workspace" size={15} /> 世界状态 <span className="chevron"><Icon name="chevronDown" size={13} /></span></span>
                <span className="composer-spacer" />
                <span className="composer-model">记忆已连接 <span className="chevron"><Icon name="chevronDown" size={13} /></span></span>
                <button className="send-round" aria-label="发送" disabled={!input.trim()} onClick={() => act()}><Icon name="send" size={16} /></button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
