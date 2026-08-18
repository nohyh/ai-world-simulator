import { useEffect, useState } from 'react'
import { fetchJson } from '../api.js'
import { useStore } from '../store.js'

function NodeDetail({ turn, index, onClose }) {
  const snapshot = turn.state_after
  const status = snapshot?.status || {}
  const characters = snapshot?.character?.npcs || []
  const attrs = Object.entries(status.attrs || {})
  const items = status.key_items || []
  return (
    <>
      <button className="tree-inspector-backdrop is-open" type="button" aria-label="关闭节点详情" onClick={onClose} />
      <aside className="tree-detail is-open" aria-label="节点详情">
        <div className="tree-detail-head"><div><p className="meta">探索节点 {index + 1}</p><h2>{turn.player_action || '开局'}</h2></div><button className="close-button" type="button" aria-label="关闭详情" onClick={onClose}>×</button></div>
        <p className="tree-detail-summary">{turn.narrative || '（没有可显示的叙事）'}</p>
        <div className="tree-detail-grid">
          <div><p className="tree-detail-label">时间 / 地点</p><p className="tree-detail-value">{status.time || turn.time_display || '未知时间'} · {status.place || turn.meta?.place || '未知地点'}</p></div>
          <div><p className="tree-detail-label">玩家行动</p><p className="tree-detail-value">{turn.player_action || '开局'}</p></div>
        </div>
        {attrs.length > 0 && <div className="tree-detail-section"><p className="tree-detail-label">公开属性</p><div className="tree-detail-chips">{attrs.map(([name, value]) => <span className="chip" key={name}>{name} {value}</span>)}</div></div>}
        {items.length > 0 && <div className="tree-detail-section"><p className="tree-detail-label">关键物品</p><div className="tree-detail-chips">{items.map((item) => <span className="chip" key={item}>{item}</span>)}</div></div>}
        {characters.length > 0 && <div className="tree-detail-section"><p className="tree-detail-label">已见人物</p><div className="tree-detail-chips">{characters.map((character) => <span className="chip" key={character.name}>{character.name}</span>)}</div></div>}
        <p className="tree-detail-note">当前版本支持查看已探索节点。回到节点并从历史继续探索将在分支写入接口稳定后开放。</p>
      </aside>
    </>
  )
}

function UnexploredBranch({ choice, index }) {
  return <span className="tree-branch-fog" title="未探索路线"><span className="tree-branch-index">{String(index + 1).padStart(2, '0')}</span>{choice}</span>
}

export default function EventTreeTab() {
  const worldId = useStore((s) => s.worldId)
  const tab = useStore((s) => s.tab)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(null)

  useEffect(() => {
    if (tab !== 'tree') return
    let cancelled = false
    setData(null)
    setError('')
    setSelectedIndex(null)
    fetchJson(`/api/game/${worldId}/history`).then((payload) => { if (!cancelled) setData(payload) }).catch((event) => { if (!cancelled) setError(event.message || '载入剧情树失败') })
    return () => { cancelled = true }
  }, [worldId, tab])

  if (error) return <section className="view page-view"><div className="error">{error}</div></section>
  if (!data) return <section className="view page-view"><div className="meta">载入世界树……</div></section>

  const turns = data.turns || []
  const selected = selectedIndex === null ? null : turns[selectedIndex]

  return (
    <section className="view page-view tree-page">
      <header className="page-head"><h1>世界树</h1><div className="page-head-meta"><span className="meta">已探索路径</span><span className="meta">{turns.length} 个节点</span></div></header>
      {turns.length === 0 ? <p className="meta">还没有任何事件——先去当前场景开始冒险。</p> : (
        <div className="story-path">
          {turns.map((turn, index) => {
            const nextAction = turns[index + 1]?.player_action || ''
            const choices = turn.meta?.choices || []
            const isLatest = index === turns.length - 1
            const isSelected = selectedIndex === index
            const unexplored = choices.filter((choice) => choice !== nextAction)
            return (
              <div className="path-step" key={`${index}-${turn.time_display || ''}`}>
                <div className="path-time meta">{turn.time_display || '未知时间'}<span>{turn.meta?.place || '未知地点'}</span></div>
                <div className={`path-marker ${isLatest ? 'is-current' : ''}`} />
                <div className="path-content">
                  <button className={`tree-node-main ${isSelected ? 'is-selected' : ''}`} type="button" onClick={() => setSelectedIndex(index)}>
                    <span className="tree-node-title">{turn.player_action || '开局'}</span>
                    <span className="tree-node-state">{isLatest ? '当前节点' : '已探索'}</span>
                    <span className="tree-node-summary">{turn.narrative || '（没有可显示的叙事）'}</span>
                  </button>
                  {(unexplored.length > 0 || (nextAction && !choices.includes(nextAction))) && <div className="branch-cluster">
                    {unexplored.map((choice, choiceIndex) => <UnexploredBranch choice={choice} index={choiceIndex} key={choice} />)}
                    {nextAction && !choices.includes(nextAction) && <span className="tree-branch-taken"><span className="tree-branch-index">自由</span>{nextAction}</span>}
                  </div>}
                </div>
              </div>
            )
          })}
        </div>
      )}
      {selected && <NodeDetail turn={selected} index={selectedIndex} onClose={() => setSelectedIndex(null)} />}
    </section>
  )
}
