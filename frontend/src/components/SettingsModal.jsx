import { useEffect, useState } from 'react'
import { fetchJson } from '../api.js'
import { useStore } from '../store.js'

const PROVIDERS = [
  { value: 'deepseek', label: 'DeepSeek', url: 'https://api.deepseek.com/v1' },
  { value: 'openai-compatible', label: 'OpenAI 兼容（GLM / Qwen / Kimi / OpenAI…）', url: '' },
  { value: 'mock', label: '演示模式（无需 Key，假模型跑通全流程）', url: '' },
]

export default function SettingsModal() {
  const { closeModal } = useStore()
  const [f, setF] = useState({ provider: 'deepseek', base_url: '', api_key: '', model: '', aux_model: '' })
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchJson('/api/settings').then(setF).catch(() => {})
  }, [])

  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value }))

  const save = async (e) => {
    e.preventDefault()
    if (f.provider !== 'mock' && !f.api_key.trim()) { setError('填写 API Key，或选择演示模式'); return }
    setBusy(true)
    setError('')
    try {
      const body = { ...f, base_url: PROVIDERS.find((p) => p.value === f.provider)?.url || f.base_url }
      await fetchJson('/api/settings', { method: 'PUT', body: JSON.stringify(body) })
      useStore.setState({ settingsHint: false })
      setSaved(true)
      setTimeout(closeModal, 600)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) closeModal() }}>
      <form className="modal narrow" onSubmit={save}>
        <div className="modal-head">
          <h2>设置</h2>
          <button type="button" className="icon-btn" onClick={closeModal}>✕</button>
        </div>
        <div className="modal-body">
          <label>Provider</label>
          <select value={f.provider} onChange={(e) => setF((s) => ({ ...s, provider: e.target.value }))}>
            {PROVIDERS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
          {f.provider === 'openai-compatible' && (
            <>
              <label>Base URL</label>
              <input value={f.base_url} onChange={set('base_url')} placeholder="https://open.bigmodel.cn/api/paas/v4" />
            </>
          )}
          {f.provider !== 'mock' && (
            <>
              <label>API Key</label>
              <input type="password" value={f.api_key} onChange={set('api_key')} placeholder="sk-…" />
              <label>主模型（叙事）</label>
              <input value={f.model} onChange={set('model')} placeholder="deepseek-chat" />
              <label>辅助模型（记忆 / 状态更新，可用更便宜的）</label>
              <input value={f.aux_model} onChange={set('aux_model')} placeholder="留空则与主模型相同" />
            </>
          )}
        </div>
        {error && <div className="error">{error}</div>}
        <div className="modal-foot">
          <span className="modal-hint">{saved ? '✓ 已保存' : '对所有世界生效'}</span>
          <button className="btn primary" disabled={busy}>{busy ? '保存中……' : '保存'}</button>
        </div>
      </form>
    </div>
  )
}
