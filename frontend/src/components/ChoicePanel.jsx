import { useState } from 'react'
import Icon from './Icon.jsx'

const CIRCLED = ['①', '②', '③', '④']

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
      <div className="choice-panel-title">你准备怎么做？</div>
      <div className="choice-panel-options">
        {choices.map((choice, index) => (
          <button type="button" className="vn-choice" key={`${choice}-${index}`}
            disabled={disabled} onClick={() => submit(choice)}>
            <span className="vn-choice-index">{CIRCLED[index] || `${index + 1}.`}</span>
            <span>{choice}</span>
          </button>
        ))}
      </div>
      <div className="choice-free-input">
        <textarea rows={2} value={input} disabled={disabled}
          placeholder="或输入自己的行动……"
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              submit(input)
            }
          }} />
        <button type="button" className="choice-send" aria-label="发送" disabled={disabled || !input.trim()}
          onClick={() => submit(input)}>
          <Icon name="arrow" size={16} />
        </button>
      </div>
    </section>
  )
}
