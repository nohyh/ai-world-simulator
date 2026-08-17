import { useEffect, useState } from 'react'
import { fetchJson } from '../api.js'
import { useStore } from '../store.js'
import Icon from './Icon.jsx'

const TABS = [
  { key: 'current', label: '当前' },
  { key: 'story', label: '剧情记录' },
  { key: 'tree', label: '世界树' },
  { key: 'chars', label: '人物图谱' },
]

export default function TopBar() {
  const { worldId, tab, setTab, toggleSidebar, selectWorld } = useStore()
  const [title, setTitle] = useState('开始你的故事')

  useEffect(() => {
    if (!worldId) {
      setTitle('开始你的故事')
      return
    }
    fetchJson(`/api/worlds/${worldId}`).then((world) => setTitle(world.title)).catch(() => {})
  }, [worldId])

  return (
    <header className="app-topbar">
      <div className="app-bar-inner">
        <button className="menu-button" type="button" title="打开世界" aria-label="打开世界" onClick={toggleSidebar}>
          <Icon name="menu" size={18} />
        </button>
        <button className="brand-button" type="button" title={worldId ? '返回世界入口' : title} onClick={() => { if (worldId) selectWorld(null) }}>
          {title}
        </button>
        {worldId ? (
          <nav className="app-nav" aria-label="世界视图">
            {TABS.map((item) => (
              <button key={item.key} className={`nav-button ${tab === item.key ? 'is-active' : ''}`} type="button" onClick={() => setTab(item.key)}>
                {item.label}
              </button>
            ))}
          </nav>
        ) : <span className="nav-space" />}
        <span className="nav-space" />
      </div>
    </header>
  )
}
