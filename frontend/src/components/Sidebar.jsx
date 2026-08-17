import { useEffect, useState } from 'react'
import { fetchJson } from '../api.js'
import { useStore } from '../store.js'
import Icon from './Icon.jsx'

function fmtTime(ts) {
  const date = new Date(ts * 1000)
  const now = new Date()
  if (date.toDateString() === now.toDateString()) {
    const minutes = Math.round((now - date) / 60000)
    if (minutes < 1) return '刚刚'
    if (minutes < 60) return `${minutes}分钟前`
    return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
  }
  return `${date.getMonth() + 1}月${date.getDate()}日`
}

export default function Sidebar() {
  const { worldId, sidebarCollapsed, selectWorld, toggleSidebar, openModal, worldsRev, bumpWorlds, settingsHint } = useStore()
  const [worlds, setWorlds] = useState(null)

  useEffect(() => {
    fetchJson('/api/worlds').then(setWorlds).catch(() => setWorlds([]))
  }, [worldsRev])

  const createWorld = () => {
    selectWorld(null)
    openModal('create')
  }

  const remove = async (event, id, title) => {
    event.stopPropagation()
    if (!window.confirm(`确定删除世界「${title}」？不可恢复。`)) return
    try {
      await fetchJson(`/api/worlds/${id}`, { method: 'DELETE' })
      if (id === worldId) selectWorld(null)
      bumpWorlds()
    } catch (error) {
      window.alert(error.message || '删除失败')
    }
  }

  return (
    <>
      <button className={`drawer-backdrop ${sidebarCollapsed ? '' : 'is-open'}`} type="button" aria-label="关闭世界抽屉" onClick={toggleSidebar} />
      <aside className={`world-drawer ${sidebarCollapsed ? '' : 'is-open'}`} aria-hidden={sidebarCollapsed}>
        <div className="drawer-head">
          <h2 className="drawer-title">世界</h2>
          <button className="close-button" type="button" aria-label="关闭世界抽屉" onClick={toggleSidebar}>×</button>
        </div>

        <button className="new-world-button" type="button" onClick={createWorld}><span>＋</span>新建世界</button>
        <div className="drawer-section-label">最近打开</div>
        <div className="drawer-world-list">
          {worlds === null && <p className="meta drawer-hint">读取中……</p>}
          {worlds?.length === 0 && <p className="meta drawer-hint">还没有世界</p>}
          {(worlds || []).map((world) => (
            <div className={`drawer-world ${world.id === worldId ? 'is-current' : ''}`} key={world.id}>
              <button type="button" className="drawer-world-main" onClick={() => selectWorld(world.id)}>
                <span className="drawer-world-name">{world.title}</span>
                <span className="drawer-world-time">{fmtTime(world.updated_at)}</span>
              </button>
              <button type="button" className="drawer-world-delete" title="删除世界" aria-label={`删除${world.title}`} onClick={(event) => remove(event, world.id, world.title)}>×</button>
            </div>
          ))}
        </div>
        <button className="drawer-settings" type="button" onClick={() => openModal('settings')}>
          <Icon name="settings" size={15} /> 设置 {settingsHint ? '· 未配置' : ''}
        </button>
      </aside>
    </>
  )
}
