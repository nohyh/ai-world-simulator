import { useEffect, useState } from 'react'
import { fetchJson } from '../api.js'
import { useStore } from '../store.js'

const CIRCLED = ['①', '②', '③', '④', '⑤', '⑥']

function ChoiceChip({ taken, children }) {
  return (
    <span
      className={`tchoice ${taken ? 'taken' : 'fog'}`}
      title={taken ? '已探索' : '未探索路线'}
    >
      {taken ? '✓' : '◌'} {taken ? children : '未探索路线'}
    </span>
  )
}

function NodeDetail({ turn, index, onClose }) {
  const snapshot = turn.state_after
  const status = snapshot?.status || {}
  const characters = snapshot?.character?.npcs || []
  const attrs = Object.entries(status.attrs || {})
  const items = status.key_items || []

  return (
    <aside className="node-detail">
      <div className="node-detail-head">
        <div>
          <div className="tree-sec mono">探索节点 {index + 1}</div>
          <div className="node-detail-title">{turn.player_action || '开局'}</div>
        </div>
        <button type="button" className="icon-btn" title="关闭详情" onClick={onClose}>×</button>
      </div>
      <div className="node-detail-story">{turn.narrative}</div>
      <div className="node-detail-grid">
        <div>
          <span className="node-detail-label">时间</span>
          <span>{status.time || turn.time_display}</span>
        </div>
        <div>
          <span className="node-detail-label">地点</span>
          <span>{status.place || '未知地点'}</span>
        </div>
      </div>
      {attrs.length > 0 && (
        <div className="node-detail-section">
          <div className="tree-sec mono">状态</div>
          <div className="node-detail-chips">
            {attrs.map(([name, value]) => <span key={name} className="chip">{name} {value}</span>)}
          </div>
        </div>
      )}
      {items.length > 0 && (
        <div className="node-detail-section">
          <div className="tree-sec mono">关键物品</div>
          <div className="node-detail-chips">
            {items.map((item) => <span key={item} className="chip">{item}</span>)}
          </div>
        </div>
      )}
      {characters.length > 0 && (
        <div className="node-detail-section">
          <div className="tree-sec mono">已见人物</div>
          <div className="node-detail-chips">
            {characters.map((character) => <span key={character.name} className="chip">{character.name}</span>)}
          </div>
        </div>
      )}
      <div className="node-detail-hint">首版只支持查看节点状态，不会从这里创建新的剧情分支。</div>
    </aside>
  )
}

/** 剧情树：展示已探索回合，并把未选择的选项渲染为不可进入的迷雾节点。 */
export default function EventTreeTab() {
  const worldId = useStore((s) => s.worldId)
  const tab = useStore((s) => s.tab)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(null)

  useEffect(() => {
    if (tab !== 'tree') return
    setData(null)
    setError('')
    setSelectedIndex(null)
    fetchJson(`/api/game/${worldId}/history`).then(setData).catch((e) => setError(e.message))
  }, [worldId, tab])

  if (error) return <div className="page-pad"><div className="error">{error}</div></div>
  if (!data) return <div className="page-pad sidebar-hint">载入剧情树……</div>

  const { turns } = data
  const selected = selectedIndex === null ? null : turns[selectedIndex]

  return (
    <div className="page-pad tree">
      {turns.length === 0 && <div className="sidebar-hint">还没有任何事件——先去剧情页开始冒险。</div>}

      {selected && (
        <NodeDetail
          turn={selected}
          index={selectedIndex}
          onClose={() => setSelectedIndex(null)}
        />
      )}

      <div className="timeline">
        {turns.map((turn, index) => {
          const nextAction = turns[index + 1]?.player_action || ''
          const isLatest = index === turns.length - 1
          const isSelected = selectedIndex === index
          const choices = turn.meta?.choices || []
          const hasFreeNextAction = !!nextAction && !choices.includes(nextAction)
          return (
            <div key={index} className={`tnode ${isLatest ? 'latest' : ''} ${isSelected ? 'selected' : ''}`}>
              <div className="tnode-rail"><span className="tnode-dot" /></div>
              <div
                className="tnode-card"
                role="button"
                tabIndex={0}
                onClick={() => setSelectedIndex(index)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') setSelectedIndex(index)
                }}
              >
                <div className="tnode-meta mono">
                  <span>{turn.time_display}</span>
                  {turn.meta?.place && <span className="dim"> · {turn.meta.place}</span>}
                  {turn.meta?.minutes ? <span className="dim"> · +{turn.meta.minutes}min</span> : null}
                  {isLatest && <span className="chip now">现在</span>}
                </div>
                <div className="tnode-action">
                  {turn.player_action
                    ? <><span className="pa-label">你</span>{turn.player_action}</>
                    : <span className="mono dim">开局</span>}
                </div>
                <div className="tnode-summary">{turn.narrative}</div>
                {choices.length > 0 && (
                  <div className="tnode-choices">
                    {choices.map((choice, choiceIndex) => (
                      <ChoiceChip key={choice} taken={choice === nextAction}>
                        {CIRCLED[choiceIndex] || `${choiceIndex + 1}.`} {choice}
                      </ChoiceChip>
                    ))}
                    {hasFreeNextAction && <span className="tchoice free">自由行动</span>}
                  </div>
                )}
                {(Object.keys(turn.attr_changes || {}).length > 0 || turn.item_changes?.add?.length > 0 || turn.item_changes?.remove?.length > 0) && (
                  <div className="tnode-deltas mono">
                    {Object.entries(turn.attr_changes || {}).map(([name, value]) => (
                      <span key={name} className={`delta ${value > 0 ? 'up' : 'down'}`}>{name} {value > 0 ? `+${value}` : value}</span>
                    ))}
                    {(turn.item_changes?.add || []).map((item) => <span key={`add-${item}`} className="delta item">＋{item}</span>)}
                    {(turn.item_changes?.remove || []).map((item) => <span key={`remove-${item}`} className="delta item down">－{item}</span>)}
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
