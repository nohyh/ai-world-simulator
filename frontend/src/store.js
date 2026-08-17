import { create } from 'zustand'

export const useStore = create((set) => ({
  worldId: null,
  tab: 'current',          // 'current' | 'story' | 'tree' | 'chars'
  sidebarCollapsed: false,
  modal: null,             // null | 'create' | 'settings'
  worldsRev: 0,            // 世界列表变化计数（Sidebar 监听刷新）
  selectWorld: (id) => set({ worldId: id, tab: 'current', sidebarCollapsed: Boolean(id) }),
  setTab: (tab) => set({ tab }),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  openModal: (modal) => set({ modal }),
  closeModal: () => set({ modal: null }),
  bumpWorlds: () => set((s) => ({ worldsRev: s.worldsRev + 1 })),
}))
