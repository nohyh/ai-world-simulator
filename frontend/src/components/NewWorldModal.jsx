import { useState } from 'react'
import { fetchJson } from '../api.js'
import { useStore } from '../store.js'

export default function NewWorldModal() {
  const { closeModal, selectWorld, bumpWorlds } = useStore()
  const [f, setF] = useState({
    world_setting: '',
    current_situation: '',
    protagonist: '',
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value }))

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
