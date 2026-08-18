import { useEffect, useMemo, useState } from 'react'

export function getTurnBeats(turn) {
  if (turn?.beats?.length) return turn.beats
  return [{ type: 'narration', speaker: null, text: turn?.narrative || '' }]
}

function normalizeBeat(beat) {
  return {
    type: beat?.type === 'dialogue' ? 'dialogue' : 'narration',
    speaker: beat?.speaker || null,
    text: String(beat?.text || ''),
  }
}

function beatLabel(beat) {
  if (!beat) return '读取中'
  if (beat.type === 'dialogue') return '对白'
  if (beat.speaker === '你') return '行动'
  return '叙事'
}

export default function BeatPlayer({
  beats,
  serverDone,
  pendingMeta,
  loadingDots,
  resumeAtEnd = false,
  enabled = true,
  onChoiceReady,
}) {
  const [activeIndex, setActiveIndex] = useState(-1)
  const [visibleCount, setVisibleCount] = useState(0)
  const [advanceRequested, setAdvanceRequested] = useState(false)

  const activeBeat = activeIndex >= 0 ? normalizeBeat(beats[activeIndex]) : null
  const characters = useMemo(() => Array.from(activeBeat?.text || ''), [activeBeat?.text])
  const revealed = !activeBeat || visibleCount >= characters.length
  const waitingForNext = advanceRequested && activeIndex >= 0 && activeIndex + 1 >= beats.length

  useEffect(() => {
    if (!beats.length) {
      setActiveIndex(-1)
      setVisibleCount(0)
      setAdvanceRequested(false)
      return
    }
    if (resumeAtEnd) {
      const lastBeat = normalizeBeat(beats[beats.length - 1])
      setActiveIndex(beats.length - 1)
      setVisibleCount(Array.from(lastBeat.text).length)
      setAdvanceRequested(false)
      return
    }
    setActiveIndex((current) => (current < 0 ? 0 : current))
  }, [beats, resumeAtEnd])

  useEffect(() => {
    if (!advanceRequested || activeIndex < 0) return
    if (activeIndex + 1 < beats.length) {
      setActiveIndex((current) => current + 1)
      setVisibleCount(0)
      setAdvanceRequested(false)
      return
    }
    if (serverDone && pendingMeta) {
      setAdvanceRequested(false)
      onChoiceReady(pendingMeta)
    }
  }, [advanceRequested, activeIndex, beats.length, serverDone, pendingMeta, onChoiceReady])

  useEffect(() => {
    if (!activeBeat || visibleCount >= characters.length) return undefined
    const timer = window.setInterval(() => setVisibleCount((count) => Math.min(count + 1, characters.length)), 24)
    return () => window.clearInterval(timer)
  }, [activeBeat, characters.length, visibleCount])

  const requestAdvance = () => {
    if (!activeBeat) return
    if (!revealed) {
      setVisibleCount(characters.length)
      return
    }
    if (activeIndex + 1 < beats.length) {
      setActiveIndex((current) => current + 1)
      setVisibleCount(0)
      return
    }
    if (!serverDone || !pendingMeta) {
      setAdvanceRequested(true)
      return
    }
    setAdvanceRequested(false)
    onChoiceReady(pendingMeta)
  }

  useEffect(() => {
    if (!enabled) return undefined
    const handleKeyDown = (event) => {
      if (event.target.closest('button, textarea, input, select, a, [data-stop-advance]')) return
      if (event.key !== 'Enter' && event.key !== ' ') return
      if (event.repeat) return
      event.preventDefault()
      requestAdvance()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  })

  if (!activeBeat) {
    return <div className="reading-stack reading-stack-empty">{loadingDots && <div className="vn-loading-dots">· · ·</div>}</div>
  }

  return (
    <div className="reading-stack">
      <p className="beat-kicker">{beatLabel(activeBeat)}</p>
      <p className="beat-speaker" hidden={!activeBeat.speaker}>{activeBeat.speaker}</p>
      <button className="dialogue-surface" type="button" onClick={requestAdvance} aria-label="继续阅读">
        <span className={`beat-text ${activeBeat.type === 'narration' ? 'is-narration' : ''} ${activeBeat.speaker === '你' ? 'is-player' : ''}`}>
          {characters.slice(0, visibleCount).join('')}
          {!revealed && <span className="vn-caret">▍</span>}
        </span>
        {revealed && <span className="beat-mark" aria-hidden="true" />}
      </button>
      <div className="reading-footer">
        <span className="num">{String(Math.max(activeIndex + 1, 1)).padStart(2, '0')} / {String(beats.length).padStart(2, '0')}</span>
        <span className="reading-hint">{activeIndex === beats.length - 1 ? (serverDone && pendingMeta ? '进入选择' : '等待后续') : '继续阅读'}</span>
      </div>
      {loadingDots && <div className="vn-loading-dots">· · ·</div>}
      {waitingForNext && <div className="vn-loading-dots vn-loading-dots-waiting">· · ·</div>}
    </div>
  )
}
