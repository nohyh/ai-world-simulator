import { useEffect, useState } from 'react'
import { fetchJson } from '../api.js'
import { useStore } from '../store.js'
import Icon from './Icon.jsx'

const TABS = [
  { key: 'current', label: '当前' },
  { key: 'story', label: '剧情' },
  { key: 'chars', label: '人物' },
  { key: 'tree', label: '剧情树' },
]

export default function TopBar() {
  const { worldId, tab, setTab, toggleSidebar } = useStore()
  const [title, setTitle] = useState('选择一个世界开始')

  useEffect(() => {
    if (!worldId) {
      setTitle('选择一个世界开始')
      return
    }
    fetchJson(`/api/worlds/${worldId}`).then((w) => setTitle(w.title)).catch(() => {})
  }, [worldId])

  return (
    <header className={`topbar ${worldId ? '' : 'topbar-library'}`}>
      {worldId && (
        <>
          <div className="topbar-leading">
            <button className="topbar-menu" type="button" title="打开世界" aria-label="打开世界" onClick={toggleSidebar}>
              <Icon name="menu" size={18} />
            </button>
            <div className="topbar-title" title={title}>{title}</div>
          </div>
          <nav className="tabs" aria-label="世界视图">
            {TABS.map((t) => (
              <button key={t.key}
                className={`tab ${tab === t.key ? 'active' : ''}`}
                onClick={() => setTab(t.key)}>{t.label}</button>
            ))}
          </nav>
        </>
      )}
    </header>
  )
}
