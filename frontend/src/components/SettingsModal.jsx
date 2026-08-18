import { useEffect, useRef, useState } from 'react'
import { fetchJson } from '../api.js'
import { useStore } from '../store.js'

const EMPTY_FORM = {
  provider: 'openai-compatible',
  base_url: '',
  api_key: '',
  model: '',
  aux_model: '',
  api_mode: 'chat',
}

export default function SettingsModal() {
  const { closeModal, viewStyle, setViewStyle } = useStore()
  const [tab, setTab] = useState('api')
  const [form, setForm] = useState(EMPTY_FORM)
  const [models, setModels] = useState([])
  const [modelsBusy, setModelsBusy] = useState(false)
  const [modelsError, setModelsError] = useState('')
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')
  const lookupRef = useRef('')

  useEffect(() => {
    fetchJson('/api/settings').then((settings) => {
      setForm({ ...EMPTY_FORM, ...settings, api_mode: settings.api_mode || 'chat' })
    }).catch(() => {})
  }, [])

  const set = (key) => (event) => {
    setForm((current) => ({ ...current, [key]: event.target.value }))
    if (key === 'base_url' || key === 'api_key') {
      setModelsError('')
      setError('')
    }
  }

  useEffect(() => {
    if (tab !== 'api' || form.provider === 'mock' || !form.base_url.trim() || !form.api_key.trim()) return undefined
    const url = form.base_url.trim()
    const apiKey = form.api_key.trim()
    const signature = `${url}\n${apiKey}`
    if (lookupRef.current === signature) return undefined
    const timer = window.setTimeout(async () => {
      lookupRef.current = signature
      setModelsBusy(true)
      setModelsError('')
      try {
        const result = await fetchJson('/api/models', {
          method: 'POST',
          body: JSON.stringify({ base_url: url, api_key: apiKey }),
        })
        lookupRef.current = `${result.base_url}\n${apiKey}`
        setModels(result.models || [])
        setForm((current) => {
          const nextModel = result.models?.includes(current.model) ? current.model : (result.models?.[0] || '')
          const nextAux = result.models?.includes(current.aux_model) ? current.aux_model : nextModel
          return { ...current, base_url: result.base_url || current.base_url, api_mode: result.api_mode || current.api_mode, model: nextModel, aux_model: nextAux }
        })
      } catch (event) {
        setModels([])
        setModelsError(event.message || '无法获取模型列表')
      } finally {
        setModelsBusy(false)
      }
    }, 450)
    return () => window.clearTimeout(timer)
  }, [tab, form.provider, form.base_url, form.api_key, form.model, form.aux_model])

  const useDemo = () => {
    setForm({ ...EMPTY_FORM, provider: 'mock' })
    setModels([])
    setModelsError('')
    setError('')
    lookupRef.current = ''
  }

  const save = async (event) => {
    event.preventDefault()
    if (form.provider !== 'mock') {
      if (!form.base_url.trim()) { setError('请填写 API URL'); return }
      if (!form.api_key.trim()) { setError('请填写 API Key'); return }
      if (!form.model.trim()) { setError('请先等待模型列表加载，或确认 API URL 支持 /models'); return }
    }
    setBusy(true)
    setError('')
    try {
      const body = {
        provider: form.provider === 'mock' ? 'mock' : 'openai-compatible',
        base_url: form.base_url.trim(),
        api_key: form.api_key.trim(),
        model: form.model.trim(),
        aux_model: (form.aux_model || form.model).trim(),
        api_mode: form.api_mode || 'chat',
      }
      await fetchJson('/api/settings', { method: 'PUT', body: JSON.stringify(body) })
      useStore.setState({ settingsHint: false })
      setSaved(true)
      window.setTimeout(closeModal, 600)
    } catch (event) {
      setError(event.message || '保存失败')
    } finally { setBusy(false) }
  }

  return (
    <div className="settings-layer" onMouseDown={(event) => { if (event.target === event.currentTarget) closeModal() }}>
      <div className="settings-dialog" role="dialog" aria-modal="true" aria-labelledby="settings-title">
        <aside className="settings-sidebar">
          <div className="settings-dialog-head"><h2 id="settings-title">设置</h2><button className="close-button" type="button" onClick={closeModal} aria-label="关闭设置">×</button></div>
          <button className={`settings-tab ${tab === 'api' ? 'is-active' : ''}`} type="button" onClick={() => setTab('api')}>API 设置</button>
          <button className={`settings-tab ${tab === 'personal' ? 'is-active' : ''}`} type="button" onClick={() => setTab('personal')}>个性化</button>
        </aside>
        <form className="settings-main" onSubmit={save}>
          {tab === 'api' ? (
            <>
              <div className="settings-main-head"><p className="meta">OpenAI 兼容接口</p><h3>连接你的模型</h3><p>只需要填写 API URL 和 API Key，系统会自动读取模型列表。支持 Chat Completions 与传统 Completions 接口。</p></div>
              {form.provider === 'mock' ? (
                <div className="settings-demo"><p className="settings-demo-title">当前为演示模式</p><p>无需网络和 API Key，可以直接跑通世界创建、剧情流和所有界面交互。</p><button className="btn btn-secondary" type="button" onClick={() => setForm((current) => ({ ...current, provider: 'openai-compatible' }))}>改用 API</button></div>
              ) : (
                <div className="settings-form">
                  <label className="settings-field"><span>API URL</span><input className="settings-input" value={form.base_url} onChange={set('base_url')} placeholder="https://api.example.com/v1 或 /v1/completions" autoComplete="url" /></label>
                  <label className="settings-field"><span>API Key</span><input className="settings-input" type="password" value={form.api_key} onChange={set('api_key')} placeholder="sk-…" autoComplete="off" /></label>
                  <label className="settings-field"><span>主模型</span><select className="settings-input" value={form.model} onChange={set('model')} disabled={modelsBusy || (!models.length && !form.model)}><option value="">{modelsBusy ? '正在获取模型列表……' : (modelsError ? '模型列表获取失败' : '等待模型列表')}</option>{form.model && !models.includes(form.model) && <option value={form.model}>{form.model}（当前）</option>}{models.map((model) => <option value={model} key={model}>{model}</option>)}</select></label>
                  <label className="settings-field"><span>辅助模型</span><select className="settings-input" value={form.aux_model || form.model} onChange={set('aux_model')} disabled={!models.length}><option value="">与主模型相同</option>{models.map((model) => <option value={model} key={model}>{model}</option>)}</select></label>
                  {modelsError && <p className="settings-model-error">{modelsError}</p>}
                  {!modelsBusy && form.base_url && form.api_key && !modelsError && models.length > 0 && <p className="settings-model-status">已获取 {models.length} 个模型 · 已自动识别 {form.api_mode === 'completion' ? 'Completions' : 'Chat Completions'} 接口</p>}
                </div>
              )}
              <button className="settings-demo-link" type="button" onClick={useDemo}>没有 API Key？使用演示模式</button>
            </>
          ) : (
            <>
              <div className="settings-main-head"><p className="meta">阅读界面</p><h3>个性化</h3><p>选择一套适合你阅读习惯的故事视图，切换会立即生效并保存在当前浏览器。</p></div>
              <div className="view-style-grid" role="radiogroup" aria-label="选择视图风格">
                {[
                  { key: 'default', name: '雾青', description: '当前的文学玻璃基底，明亮、克制、适合长时间阅读。' },
                  { key: 'night', name: '夜雨', description: '更深的背景与更亮的文字，让场景进入夜间状态。' },
                  { key: 'quiet', name: '灰紫', description: '降低环境色彩，保留对白与人物信息的清晰度。' },
                ].map((style) => (
                  <button className={`view-style-option ${viewStyle === style.key ? 'is-selected' : ''}`} type="button" role="radio" aria-checked={viewStyle === style.key} data-style-key={style.key} key={style.key} onClick={() => setViewStyle(style.key)}>
                    <span className="view-style-swatch" aria-hidden="true" />
                    <span><strong className="view-style-name">{style.name}</strong><small className="view-style-description">{style.description}</small></span>
                    <span className="view-style-check">当前</span>
                  </button>
                ))}
              </div>
            </>
          )}
          {error && <p className="error settings-error">{error}</p>}
          <div className="settings-actions"><span className="meta">{tab === 'personal' ? '✓ 已自动保存' : (saved ? '✓ 已保存' : '对所有世界生效')}</span>{tab === 'personal' ? <button className="btn btn-primary" type="button" onClick={closeModal}>完成</button> : <button className="btn btn-primary" type="submit" disabled={busy || modelsBusy}>{busy ? '保存中……' : '保存设置'}</button>}</div>
        </form>
      </div>
    </div>
  )
}
