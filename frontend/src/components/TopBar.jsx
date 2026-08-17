import { useEffect, useState } from 'react'
import { fetchJson } from '../api.js'
import { useStore } from '../store.js'

const TABS = [
  { key: 'story', label: '剧情' },
  { key: 'tree', label: '世界树' },
  { key: 'chars', label: '人物图谱' },
]

export default function TopBar() {
  const { worldId, tab, setTab } = useStore()
  const [title, setTitle] = useState('选择一个世界开始')
  const [model, setModel] = useState('')

  useEffect(() => {
    if (!worldId) {
      setTitle('选择一个世界开始')
      setModel('')
      return
    }
    fetchJson(`/api/worlds/${worldId}`).then((w) => setTitle(w.title)).catch(() => {})
    fetchJson('/api/settings').then((s) => setModel(s.model || '')).catch(() => {})
  }, [worldId])

  return (
    <header className="topbar">
      <div className="topbar-leading">
        <div className="topbar-kicker">当前世界</div>
        <div className="topbar-title" title={title}>{title}</div>
      </div>
      <nav className="tabs">
        {TABS.map((t) => (
          <button key={t.key}
            className={`tab ${tab === t.key ? 'active' : ''}`}
            onClick={() => setTab(t.key)}>{t.label}</button>
        ))}
      </nav>
      <div className="topbar-model mono" title="当前主模型（在设置中修改）">{model}</div>
    </header>
  )
}
