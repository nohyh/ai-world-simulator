import { useEffect } from 'react'
import { useStore } from './store.js'
import { fetchJson } from './api.js'
import Icon from './components/Icon.jsx'
import Sidebar from './components/Sidebar.jsx'
import TopBar from './components/TopBar.jsx'
import StoryTab from './components/StoryTab.jsx'
import EventTreeTab from './components/EventTreeTab.jsx'
import CharactersTab from './components/CharactersTab.jsx'
import NewWorldModal from './components/NewWorldModal.jsx'
import SettingsModal from './components/SettingsModal.jsx'

function EmptyMain() {
  const openModal = useStore((s) => s.openModal)
  return (
    <div className="empty-main">
      <div className="hero-stack">
        <div className="hero-title">
          <span>探索未至之境</span>
        </div>
        <button className="hero-workspace" onClick={() => openModal('create')}>
          <span className="folder-icon"><Icon name="folder" size={16} /></span> 新建一个世界 <span className="chevron"><Icon name="chevronDown" size={13} /></span>
        </button>
        <button className="hero-composer" onClick={() => openModal('create')}>
          <span className="hero-placeholder">描述你想要探索的世界</span>
          <span className="hero-composer-row">
            <span className="composer-plus"><Icon name="plus" size={16} />
            </span>
            <span>世界设定</span>
            <span className="hero-send"><Icon name="send" size={16} /></span>
          </span>
        </button>
      </div>
    </div>
  )
}

export default function App() {
  const { worldId, tab, modal } = useStore()

  // 拉一次设置，未配置 Key 时提醒（mock 演示模式不打扰）
  useEffect(() => {
    fetchJson('/api/settings').then((s) => {
      if (!s.api_key && s.provider !== 'mock') {
        useStore.setState({ settingsHint: true })
      }
    }).catch(() => {})
  }, [])

  return (
    <div className="shell">
      <Sidebar />
      <main className="main">
        <TopBar />
        {worldId ? (
          <>
            <div className="tab-body">
              {tab === 'story' && <StoryTab key={worldId} />}
              {tab === 'tree' && <EventTreeTab key={worldId} />}
              {tab === 'chars' && <CharactersTab key={worldId} />}
            </div>
          </>
        ) : <div className="tab-body"><EmptyMain /></div>}
      </main>
      {modal === 'create' && <NewWorldModal />}
      {modal === 'settings' && <SettingsModal />}
    </div>
  )
}
