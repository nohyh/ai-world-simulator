import { useEffect, useState } from 'react'
import { fetchJson } from '../api.js'
import { useStore } from '../store.js'
import Icon from './Icon.jsx'

function fmtTime(ts) {
  const d = new Date(ts * 1000)
  const now = new Date()
  if (d.toDateString() === now.toDateString()) {
    const mins = Math.round((now - d) / 60000)
    if (mins < 1) return '刚刚'
    if (mins < 60) return `${mins}分钟前`
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  }
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

export default function Sidebar() {
  const { worldId, sidebarCollapsed, selectWorld, toggleSidebar, openModal, worldsRev, bumpWorlds, settingsHint } = useStore()
  const [worlds, setWorlds] = useState(null)
  const immersive = Boolean(worldId)

  useEffect(() => {
    fetchJson('/api/worlds').then(setWorlds).catch(() => setWorlds([]))
  }, [worldsRev])

  const remove = async (e, id, title) => {
    e.stopPropagation()
    if (!window.confirm(`确定删除世界「${title}」？不可恢复。`)) return
    await fetchJson(`/api/worlds/${id}`, { method: 'DELETE' })
    if (id === worldId) selectWorld(null)
    bumpWorlds()
  }

  return (
    <>
      {immersive && !sidebarCollapsed && (
        <button className="drawer-scrim" type="button" aria-label="关闭世界抽屉" onClick={toggleSidebar} />
      )}
      <aside className={`sidebar ${sidebarCollapsed ? 'collapsed' : ''} ${immersive ? 'world-drawer' : ''}`}>
      <div className="sidebar-head">
        {sidebarCollapsed ? (
          <button className="icon-btn collapsed-toggle" title="展开" onClick={toggleSidebar}>
            <Icon name="panel" size={18} />
          </button>
        ) : (
          <>
            <div className="brand">
              <span className="brand-title">{immersive ? '世界' : '世界模拟器'}</span>
            </div>
            <button className="icon-btn" title="收起" onClick={toggleSidebar}>
              <Icon name="panel" size={16} />
            </button>
          </>
        )}
      </div>

      <button className="new-world-btn" title={sidebarCollapsed ? '新建世界' : undefined} onClick={() => openModal('create')}>
        <span className="plus"><Icon name="plus" size={16} /></span>{!sidebarCollapsed && <span>新建世界</span>}
      </button>

      {!sidebarCollapsed && (
        <div className="workspace-head">
          <span>工作区</span>
          <span className="workspace-actions">
            <button type="button" title="搜索世界"><Icon name="search" size={15} /></button>
            <button type="button" title="视图选项"><Icon name="sliders" size={15} /></button>
            <button type="button" title="添加世界" onClick={() => openModal('create')}><Icon name="plus" size={16} /></button>
          </span>
        </div>
      )}

      <div className="sidebar-list">
        {worlds === null && <div className="sidebar-hint">加载中……</div>}
        {worlds?.length === 0 && (
          <div className="sidebar-hint">{sidebarCollapsed ? '' : '还没有世界'}</div>
        )}
        {(worlds || []).map((w) => (
          <div key={w.id}
            className={`world-item ${w.id === worldId ? 'active' : ''}`}
            onClick={() => selectWorld(w.id)}
            title={w.title}>
            {sidebarCollapsed
              ? <span className="world-dot">{w.title.slice(0, 1)}</span>
              : <>
                  <div className="workspace-icon"><Icon name="folder" size={17} /></div>
                  <div className="world-item-copy">
                    <div className="world-item-title">{w.title}</div>
                    <div className="world-item-sub">{fmtTime(w.updated_at)}</div>
                  </div>
                </>}
            {!sidebarCollapsed && (
              <button className="world-del" title="删除"
                onClick={(e) => remove(e, w.id, w.title)}>✕</button>
            )}
          </div>
        ))}
      </div>

      <div className="sidebar-foot">
        <button className="settings-btn" title={sidebarCollapsed ? '设置' : undefined} onClick={() => openModal('settings')}>
          <span className="gear"><Icon name="settings" size={17} /></span>{!sidebarCollapsed && <span>设置{settingsHint ? ' · 未配置' : ''}</span>}
        </button>
      </div>
      </aside>
    </>
  )
}
