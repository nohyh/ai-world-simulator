import { useState } from 'react'
import { fetchJson } from '../api.js'
import { useStore } from '../store.js'

export default function NewWorldModal() {
  const { closeModal, selectWorld, bumpWorlds } = useStore()
  const [f, setF] = useState({
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
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value }))
  const setAttr = (name) => (e) => setF((s) => ({
    ...s,
    attrs: { ...s.attrs, [name]: Number(e.target.value) },
  }))

  const submit = async (e) => {
    e.preventDefault()
    if (!f.world_setting.trim() || !f.protagonist.trim() || !f.current_situation.trim()) {
      setError('请完整填写世界设定、主角描述和开局情况')
      return
    }
    setBusy(true)
    setError('')
    try {
      const body = {
        world_setting: f.world_setting.trim(),
        current_situation: f.current_situation.trim(),
        player_background: f.protagonist.trim(),
        player_name: f.player_name.trim() || '旅人',
        player_identity: f.player_identity.trim(),
        world_rules: f.world_rules.trim(),
        tone: f.tone.trim(),
        start_time: f.start_time.trim(),
        start_place: f.start_place.trim(),
        important_people: f.important_people.trim(),
        custom_notes: f.custom_notes.trim(),
        attrs: f.attrs,
      }
      const { id } = await fetchJson('/api/worlds', { method: 'POST', body: JSON.stringify(body) })
      bumpWorlds()
      selectWorld(id)
      closeModal()
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <div className="modal-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) closeModal() }}>
      <form className="modal" onSubmit={submit}>
        <div className="modal-head">
          <h2>新建世界</h2>
          <button type="button" className="icon-btn" onClick={closeModal}>✕</button>
        </div>

        <div className="modal-body">
          <label>世界观设定 *</label>
          <textarea rows={5} value={f.world_setting} onChange={set('world_setting')}
            placeholder={'这个世界是什么样的？时代、地点、文明状态、正在发生的大事……\n例如：2041年，大崩坏后的第十年。文明退回到据点时代，你的避难所靠一台老旧的水净化器维生，北方的武装集团正在南下。'} />

          <label>主角描述 *</label>
          <textarea rows={4} value={f.protagonist} onChange={set('protagonist')}
            placeholder={'自由描述主角的姓名、身份、性格、背景和能力。\n例如：林默，避难所的年轻侦察员，擅长追踪，表面冷静但一直在寻找失踪的姐姐。'} />

          <label>开局情况 *</label>
          <textarea rows={3} value={f.current_situation} onChange={set('current_situation')}
            placeholder={'你此刻在哪、正在做什么、身边有谁。例如：清晨的医务室，陈医生刚把你叫醒——昨晚巡逻队失去了联络。'} />

          <details className="modal-advanced">
            <summary>更多设定（可选）</summary>
            <div className="modal-advanced-body">
              <div className="modal-grid">
                <div>
                  <label>主角姓名</label>
                  <input value={f.player_name} onChange={set('player_name')} placeholder="留空则从主角描述提取" />
                </div>
                <div>
                  <label>主角身份</label>
                  <input value={f.player_identity} onChange={set('player_identity')} placeholder="例如：侦察员" />
                </div>
              </div>

              <label>世界规则</label>
              <textarea rows={2} value={f.world_rules} onChange={set('world_rules')} placeholder="这个世界必须遵守的规则、禁忌或技术边界" />

              <div className="modal-grid">
                <div>
                  <label>剧情基调</label>
                  <input value={f.tone} onChange={set('tone')} placeholder="例如：克制、悬疑、有张力" />
                </div>
                <div>
                  <label>开局地点</label>
                  <input value={f.start_place} onChange={set('start_place')} placeholder="例如：北岭避难所" />
                </div>
              </div>

              <label>开始时间</label>
              <input value={f.start_time} onChange={set('start_time')} placeholder="例如：2041年7月16日 08:00" />

              <label>初始人物</label>
              <textarea rows={3} value={f.important_people} onChange={set('important_people')} placeholder="描述重要人物或初始关系；没有也可以留空，系统会按世界设定生成。" />

              <label>补充说明</label>
              <textarea rows={2} value={f.custom_notes} onChange={set('custom_notes')} placeholder="希望避免或特别强调的内容" />

              <label>主角属性</label>
              <div className="attrs-editor">
                {Object.entries(f.attrs).map(([name, value]) => (
                  <div key={name} className="attr-row">
                    <input value={name} readOnly aria-label={`${name}属性`} />
                    <input type="number" min="0" max="100" value={value} onChange={setAttr(name)} aria-label={`${name}数值`} />
                  </div>
                ))}
              </div>
            </div>
          </details>
        </div>

        {error && <div className="error">{error}</div>}
        <div className="modal-foot">
          <span className="modal-hint">创建后将自动生成开场剧情</span>
          <button className="btn primary" disabled={busy}>{busy ? '准备世界……' : '创建并开始'}</button>
        </div>
      </form>
    </div>
  )
}
