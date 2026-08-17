import { useEffect, useState } from 'react'
import { fetchJson } from '../api.js'
import { useStore } from '../store.js'

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
    <div className="history-page page-pad">
      <div className="history-wrap">
        <div className="history-heading">
          <div>
            <div className="history-kicker mono">BACKLOG</div>
            <h1>剧情记录</h1>
          </div>
          <span className="history-count mono">{turns ? `${turns.length} 回合` : '读取中'}</span>
        </div>
        {error && <div className="error">{error}</div>}
        {turns === null && !error && <div className="sidebar-hint">载入剧情……</div>}
        {turns?.length === 0 && <div className="history-empty">世界刚刚建立，第一幕还在当前场景中展开。</div>}
        <div className="history-list">
          {(turns || []).map((turn, index) => (
            <article className="history-turn" key={`${index}-${turn.time_display || ''}`}>
              <div className="history-turn-meta mono">
                <span>{turn.time_display || '未知时间'}</span>
                {turn.meta?.place && <span> · {turn.meta.place}</span>}
              </div>
              {turn.player_action
                ? <div className="history-action"><span>你</span>{turn.player_action}</div>
                : <div className="history-opening mono">· 开局 ·</div>}
              <div className="history-narrative">{turn.narrative || '（没有可显示的叙事）'}</div>
            </article>
          ))}
        </div>
      </div>
    </div>
  )
}
