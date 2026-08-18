import { useState } from 'react'
import Icon from './Icon.jsx'

export default function ChoicePanel({ choices = [], onSubmit, disabled = false }) {
  const [input, setInput] = useState('')

  const submit = (value) => {
    const text = String(value || '').trim()
    if (!text || disabled) return
    setInput('')
    onSubmit(text)
  }

  return (
    <section className="choice-panel" data-stop-advance onClick={(event) => event.stopPropagation()}>
      <h2 className="choice-title">你准备怎么做？</h2>
      <div className="choice-list">
        {choices.map((choice, index) => (
          <button className="choice-option" type="button" key={`${choice}-${index}`} disabled={disabled} onClick={() => submit(choice)}>
            <span className="choice-number">{String(index + 1).padStart(2, '0')}</span>
            <span className="choice-copy">{choice}</span>
            <span className="choice-arrow">↗</span>
          </button>
        ))}
      </div>
      <form className="free-action" onSubmit={(event) => { event.preventDefault(); submit(input) }}>
        <input className="input" value={input} disabled={disabled} placeholder="或者，写下你自己的行动……" onChange={(event) => setInput(event.target.value)} />
        <button className="free-submit" type="submit" aria-label="发送行动" disabled={disabled || !input.trim()}><Icon name="arrow" size={17} /></button>
      </form>
      <p className="choice-foot">推荐行动与自由行动处于同一层级</p>
    </section>
  )
}
