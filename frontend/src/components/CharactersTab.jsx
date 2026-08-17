import { useEffect, useState } from 'react'
import { fetchJson } from '../api.js'
import { useStore } from '../store.js'

/** 人物页：玩家卡片 + NPC 卡片（玩家视角——看不到任何人的秘密）。 */
export default function CharactersTab() {
  const worldId = useStore((s) => s.worldId)
  const [state, setState] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchJson(`/api/game/${worldId}/state`).then(setState).catch((e) => setError(e.message))
  }, [worldId])

  if (error) return <div className="page-pad"><div className="error">{error}</div></div>
  if (!state) return <div className="page-pad sidebar-hint">载入人物……</div>

  const p = state.character?.player || {}
  const npcs = state.character?.npcs || []
  const attrs = state.status?.attrs || {}

  return (
    <div className="page-pad chars">
      <div className="player-card">
        <div className="pc-head">
          <div className="pc-avatar">{(p.name || '?').slice(0, 1)}</div>
          <div>
            <div className="pc-name">{p.name}</div>
            <div className="pc-identity">{p.identity}</div>
          </div>
          <div className="pc-loc mono">
            {state.status?.place}{state.status?.place && state.status?.time ? ' · ' : ''}{state.status?.time}
          </div>
        </div>
        {p.background && <p className="pc-bg">{p.background}</p>}
        <div className="pc-attrs">
          {Object.entries(attrs).map(([k, v]) => (
            <div key={k} className="attr-line">
              <span className="attr-k">{k}</span>
              <div className="attr-track"><div className="attr-fill" style={{ width: `${v}%` }} /></div>
              <span className="attr-v mono">{v}</span>
            </div>
          ))}
        </div>
        {state.status?.key_items?.length > 0 && (
          <div className="pc-items">
            <span className="tree-sec mono">关键物品</span>
            <div className="item-chips">
              {state.status.key_items.map((it, i) => <span key={i} className="chip">{it}</span>)}
            </div>
          </div>
        )}
      </div>

      <div className="tree-sec mono sec-gap">人物（{npcs.length}）</div>
      {npcs.length === 0 && <div className="sidebar-hint">这个世界还没有认识的活人。</div>}
      <div className="npc-grid">
        {npcs.map((n) => (
          <div key={n.name} className="npc-card">
            <div className="npc-top">
              <div className="pc-avatar small">{n.name.slice(0, 1)}</div>
              <div>
                <div className="npc-name">{n.name}</div>
                <div className="pc-identity">{n.identity}</div>
              </div>
            </div>
            <div className="npc-tags">
              <span className="chip">{n.relationship}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
