import { useEffect, useState } from 'react'
import { fetchJson } from '../api.js'
import { useStore } from '../store.js'

function renderBeats(turn) {
  if (!turn.beats?.length) return <p className="history-line narration">{turn.narrative || '（没有可显示的叙事）'}</p>
  return turn.beats.map((beat, index) => {
    const text = beat.text || ''
    if (beat.type === 'dialogue') {
      return (
        <div className="history-dialogue-block" key={`${index}-${text}`}>
          {beat.speaker && <div className="history-speaker">{beat.speaker}</div>}
          <div className="history-dialogue">{text}</div>
        </div>
      )
    }
    return <p className="history-line narration" key={`${index}-${text}`}>{text}</p>
  })
}

export default function HistoryTab() {
  const worldId = useStore((s) => s.worldId)
  const worldsRev = useStore((s) => s.worldsRev)
  const [turns, setTurns] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setTurns(null)
    setError('')
    fetchJson(`/api/game/${worldId}/history`).then((payload) => {
      if (!cancelled) setTurns(payload.turns || [])
    }).catch((event) => {
      if (!cancelled) setError(event.message || '载入剧情失败')
    })
    return () => { cancelled = true }
  }, [worldId, worldsRev])

  return (
    <section className="view page-view history-page">
      <header className="page-head">
        <h1>剧情记录</h1>
        <div className="page-head-meta"><span className="meta">完整记录</span><span className="meta">{turns ? `${turns.length} 回合` : '读取中'}</span></div>
      </header>
      {error && <div className="error page-error">{error}</div>}
      {turns === null && !error && <div className="meta">载入剧情……</div>}
      {turns?.length === 0 && <div className="meta history-empty">世界刚刚建立，第一幕还在当前场景中展开。</div>}
      <div className="history-list">
        {(turns || []).map((turn, index) => (
          <article className="history-entry" key={`${index}-${turn.time_display || ''}`}>
            <div className="history-meta meta"><span>{turn.time_display || '未知时间'}</span><span className="history-meta-place">{turn.meta?.place || '未知地点'}</span></div>
            <div className="history-body">
              {renderBeats(turn)}
              <div className="history-action-label">你的行动</div>
              <p className="history-action">{turn.player_action || '开局'}</p>
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}
