import { useEffect } from 'react'
import { useStore } from './store.js'
import { fetchJson } from './api.js'
import Sidebar from './components/Sidebar.jsx'
import TopBar from './components/TopBar.jsx'
import CurrentScene from './components/CurrentScene.jsx'
import HistoryTab from './components/HistoryTab.jsx'
import EventTreeTab from './components/EventTreeTab.jsx'
import CharactersTab from './components/CharactersTab.jsx'
import SettingsModal from './components/SettingsModal.jsx'
import LauncherView from './components/LauncherView.jsx'

export default function App() {
  const { worldId, tab, modal, viewStyle } = useStore()

  useEffect(() => {
    document.body.dataset.viewStyle = viewStyle
  }, [viewStyle])

  // 拉一次设置，未配置 Key 时提醒（mock 演示模式不打扰）
  useEffect(() => {
    fetchJson('/api/settings').then((s) => {
      if (!s.api_key && s.provider !== 'mock') {
        useStore.setState({ settingsHint: true })
      }
    }).catch(() => {})
  }, [])

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="app-main">
        <TopBar />
        {worldId ? (
          <div className="tab-body">
            <div className="tab-panel" hidden={tab !== 'current'}><CurrentScene key={worldId} /></div>
            <div className="tab-panel" hidden={tab !== 'story'}><HistoryTab key={worldId} /></div>
            <div className="tab-panel" hidden={tab !== 'tree'}><EventTreeTab key={worldId} /></div>
            <div className="tab-panel" hidden={tab !== 'chars'}><CharactersTab key={worldId} /></div>
          </div>
        ) : <LauncherView />}
      </main>
      {modal === 'settings' && <SettingsModal />}
    </div>
  )
}
