import { useEffect, useMemo, useState } from 'react'
import { fetchJson } from '../api.js'
import { useStore } from '../store.js'

function avatar(name) {
  return (name || '?').slice(0, 1)
}

export default function CharactersTab() {
  const worldId = useStore((s) => s.worldId)
  const tab = useStore((s) => s.tab)
  const [state, setState] = useState(null)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    if (tab !== 'chars') return
    setState(null)
    setSelected(null)
    setError('')
    fetchJson(`/api/game/${worldId}/state`).then(setState).catch((event) => setError(event.message || '载入人物失败'))
  }, [worldId, tab])

  const characters = useMemo(() => {
    if (!state) return []
    const player = state.character?.player || {}
    const npcs = state.character?.npcs || []
    return [
      { id: 'player', name: player.name || '旅人', role: player.identity || '主角', state: '玩家视角', description: player.background || '这是你的角色。', player: true },
      ...npcs.map((npc) => ({
        id: npc.name, name: npc.name, role: npc.identity || '已知人物',
        state: npc.status || '处境未知', age: npc.age,
        description: (npc.age ? `${npc.age} 岁 · ` : '') + `你已经在故事中见过${npc.name}。`, npc,
      })),
    ]
  }, [state])

  if (error) return <section className="view page-view"><div className="error">{error}</div></section>
  if (!state) return <section className="view page-view"><div className="meta">载入人物……</div></section>

  const selectedCharacter = characters.find((character) => character.id === selected)
  const attrs = state.status?.attrs || {}

  return (
    <section className="view page-view characters-page">
      {!selectedCharacter ? (
        <>
          <header className="page-head">
            <h1>人物图谱</h1>
            <div className="page-head-meta"><span className="meta">已见人物</span><span className="meta">{characters.length} 张卡片</span></div>
          </header>
          <div className="character-index-view">
            <div className="character-grid">
              {characters.map((character) => (
                <button className="character-card" type="button" key={character.id} onClick={() => setSelected(character.id)}>
                  <span className="character-card-avatar"><strong>{avatar(character.name)}</strong><small>头像预留</small></span>
                  <span className="character-card-copy"><span className="character-card-name">{character.name}</span><span className="character-card-role">{character.role}</span><span className="character-card-state">{character.state}</span></span>
                </button>
              ))}
            </div>
            {characters.length === 1 && <p className="meta character-empty">随着你探索世界，见过的人会出现在这里。</p>}
          </div>
        </>
      ) : (
        <div className="character-detail-view">
          <button className="character-back" type="button" onClick={() => setSelected(null)}>← 人物图谱</button>
          <div className="character-hero">
            <div className="portrait-reserve"><span>{avatar(selectedCharacter.name)}</span><small>头像预留</small></div>
            <div><h2>{selectedCharacter.name}</h2><p className="character-role">{selectedCharacter.role}</p><p className="character-description">{selectedCharacter.description}</p></div>
          </div>
          <dl className="character-basic">
            <div className="character-basic-item"><dt>身份</dt><dd>{selectedCharacter.role}</dd></div>
            <div className="character-basic-item"><dt>当前状态</dt><dd>{selectedCharacter.state}</dd></div>
            <div className="character-basic-item"><dt>所在地点</dt><dd>{state.status?.place || '未知地点'}</dd></div>
            <div className="character-basic-item"><dt>当前时间</dt><dd>{state.status?.time || '未知时间'}</dd></div>
          </dl>
          {selectedCharacter.player && (
            <div className="character-detail-section">
              <p className="meta">玩家状态</p>
              <div className="character-attrs">
                {Object.entries(attrs).map(([name, value]) => <div className="character-attr" key={name}><span>{name}</span><span className="character-attr-track"><i style={{ width: `${Math.max(0, Math.min(100, Number(value) || 0))}%` }} /></span><strong>{value}</strong></div>)}
              </div>
              {state.status?.key_items?.length > 0 && <div className="character-items"><p className="meta">公开持有物</p><div className="item-chips">{state.status.key_items.map((item) => <span className="chip" key={item}>{item}</span>)}</div></div>}
            </div>
          )}
        </div>
      )}
    </section>
  )
}
