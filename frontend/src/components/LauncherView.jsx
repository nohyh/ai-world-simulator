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

const INITIAL_FORM = {
  world_setting: '',
  current_situation: '',
  protagonist: '',
  player_name: '',
  player_identity: '',
  world_rules: '',
  tone: '',
  start_time: '',
  start_place: '',
  important_people: '',
  custom_notes: '',
  attrs: { 力量: 50, 智力: 50, 魅力: 50, 体质: 50 },
}

export default function LauncherView() {
  const { modal, closeModal, selectWorld, bumpWorlds, worldsRev } = useStore()
  const [worlds, setWorlds] = useState([])
  const [worldName, setWorldName] = useState('')
  const [setup, setSetup] = useState(false)
  const [form, setForm] = useState(INITIAL_FORM)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchJson('/api/worlds').then(setWorlds).catch(() => setWorlds([]))
  }, [worldsRev])

  useEffect(() => {
    if (modal === 'create') {
      setSetup(false)
      setWorldName('')
      setError('')
    }
  }, [modal])

  const set = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }))
  const setAttr = (name) => (event) => setForm((current) => ({
    ...current,
    attrs: { ...current.attrs, [name]: Number(event.target.value) },
  }))

  const beginSetup = (event) => {
    event.preventDefault()
    if (!worldName.trim()) {
      setError('先给这个世界起一个名字')
      return
    }
    setError('')
    setSetup(true)
    closeModal()
  }

  const submit = async (event) => {
    event.preventDefault()
    if (!form.world_setting.trim() || !form.protagonist.trim() || !form.current_situation.trim()) {
      setError('请填写世界设定、主角描述和开局情况')
      return
    }
    setBusy(true)
    setError('')
    try {
      const body = {
        world_setting: form.world_setting.trim(),
        current_situation: form.current_situation.trim(),
        player_background: form.protagonist.trim(),
        title: worldName.trim() || '未命名世界',
        player_name: form.player_name.trim() || '旅人',
        player_identity: form.player_identity.trim(),
        world_rules: form.world_rules.trim(),
        tone: form.tone.trim(),
        start_time: form.start_time.trim(),
        start_place: form.start_place.trim(),
        important_people: form.important_people.trim(),
        custom_notes: form.custom_notes.trim(),
        attrs: form.attrs,
      }
      const { id } = await fetchJson('/api/worlds', { method: 'POST', body: JSON.stringify(body) })
      bumpWorlds()
      closeModal()
      selectWorld(id)
    } catch (event) {
      setError(event.message || '创建世界失败')
      setBusy(false)
    }
  }

  return (
    <section className="view launcher-view">
      <div className="launcher-layout">
        <div className="launcher-copy">
          <div className="launcher-image-frame">
            <img src="/launcher-character.png" alt="故事入口场景" />
          </div>
          <p className="launcher-image-caption">开始你的故事</p>
        </div>

        <div className="launcher-entry">
          {!setup ? (
            <>
              <form className="world-entry-form" onSubmit={beginSetup}>
                <textarea className="textarea" value={worldName} onChange={(event) => setWorldName(event.target.value)} placeholder="例如：黑雨计划" aria-label="世界名称" />
                <button className="world-entry-submit" type="submit" aria-label="开始创建"><Icon name="arrow" size={18} /></button>
              </form>
              <p className="world-entry-caption">给你的新世界起一个独一无二的名字</p>
              <p className="world-entry-feedback">{error}</p>
              <div className="launcher-worlds">
                <div className="launcher-worlds-head"><h2 className="launcher-worlds-title">已有世界</h2><span className="meta">最近打开</span></div>
                {worlds.length === 0 && <p className="meta launcher-empty">还没有世界，从上面开始创建。</p>}
                {worlds.map((world) => (
                  <button className="world-row" type="button" key={world.id} onClick={() => selectWorld(world.id)}>
                    <span className="world-row-name">{world.title}</span>
                    <span className="world-row-time">{fmtTime(world.updated_at)}</span>
                  </button>
                ))}
              </div>
            </>
          ) : (
            <div className="world-setup">
              <div className="world-setup-head">
                <h2 className="world-setup-title">进入一个世界</h2>
                <span className="world-setup-name">{worldName || '新世界'}</span>
              </div>
              <form className="world-setup-form" onSubmit={submit}>
                <div className="world-setup-fields">
                  <div className="world-setup-field is-wide">
                    <label htmlFor="world-lore">世界设定 <span>*</span></label>
                    <textarea id="world-lore" className="world-setup-input" rows="3" value={form.world_setting} onChange={set('world_setting')} placeholder="时代、地点、文明状态，以及正在发生的大事。" />
                  </div>
                  <div className="world-setup-field is-wide">
                    <label htmlFor="world-protagonist">主角描述 <span>*</span></label>
                    <textarea id="world-protagonist" className="world-setup-input" rows="3" value={form.protagonist} onChange={set('protagonist')} placeholder="姓名、身份、性格、背景与能力。" />
                  </div>
                  <div className="world-setup-field is-wide">
                    <label htmlFor="world-situation">开局情况 <span>*</span></label>
                    <textarea id="world-situation" className="world-setup-input" rows="3" value={form.current_situation} onChange={set('current_situation')} placeholder="你此刻在哪里、正在做什么、身边有谁。" />
                  </div>
                  <div className="world-setup-field">
                    <label htmlFor="world-place">开局地点</label>
                    <input id="world-place" className="world-setup-input" value={form.start_place} onChange={set('start_place')} placeholder="例如：北岭避难所" />
                  </div>
                  <div className="world-setup-field">
                    <label htmlFor="world-tone">剧情基调</label>
                    <input id="world-tone" className="world-setup-input" value={form.tone} onChange={set('tone')} placeholder="例如：克制、悬疑" />
                  </div>
                </div>

                <details className="world-setup-advanced">
                  <summary>更多设定（可选）</summary>
                  <div className="world-setup-fields">
                    <div className="world-setup-field"><label htmlFor="player-name">主角姓名</label><input id="player-name" className="world-setup-input" value={form.player_name} onChange={set('player_name')} placeholder="留空则从描述提取" /></div>
                    <div className="world-setup-field"><label htmlFor="player-identity">主角身份</label><input id="player-identity" className="world-setup-input" value={form.player_identity} onChange={set('player_identity')} placeholder="例如：侦察员" /></div>
                    <div className="world-setup-field is-wide"><label htmlFor="world-rules">世界规则</label><textarea id="world-rules" className="world-setup-input" rows="2" value={form.world_rules} onChange={set('world_rules')} placeholder="必须遵守的规则、禁忌或技术边界" /></div>
                    <div className="world-setup-field"><label htmlFor="start-time">开始时间</label><input id="start-time" className="world-setup-input" value={form.start_time} onChange={set('start_time')} placeholder="例如：2041年7月16日 08:00" /></div>
                    <div className="world-setup-field"><label htmlFor="important-people">初始人物</label><input id="important-people" className="world-setup-input" value={form.important_people} onChange={set('important_people')} placeholder="没有也可以留空" /></div>
                    <div className="world-setup-field is-wide"><label htmlFor="custom-notes">补充说明</label><textarea id="custom-notes" className="world-setup-input" rows="2" value={form.custom_notes} onChange={set('custom_notes')} placeholder="希望避免或特别强调的内容" /></div>
                  </div>
                  <div className="attrs-editor launcher-attrs">
                    {Object.entries(form.attrs).map(([name, value]) => <label className="attr-row" key={name}><span>{name}</span><input type="number" min="0" max="100" value={value} onChange={setAttr(name)} /></label>)}
                  </div>
                </details>

                {error && <p className="world-entry-feedback setup-feedback">{error}</p>}
                <div className="world-setup-actions">
                  <button className="world-setup-back" type="button" onClick={() => { setSetup(false); setError('') }}>← 返回世界入口</button>
                  <button className="btn btn-primary" type="submit" disabled={busy}>{busy ? '准备世界……' : '创建并开始 →'}</button>
                </div>
              </form>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
