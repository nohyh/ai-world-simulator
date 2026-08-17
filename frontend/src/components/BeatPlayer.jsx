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

export default function BeatPlayer({
  beats,
  serverDone,
  pendingMeta,
  busy,
  initialLoading,
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
    setActiveIndex((current) => (current < 0 ? 0 : current))
  }, [beats.length])

  useEffect(() => {
    if (!advanceRequested || activeIndex < 0 || activeIndex + 1 >= beats.length) return
    setActiveIndex((current) => current + 1)
    setVisibleCount(0)
    setAdvanceRequested(false)
  }, [advanceRequested, activeIndex, beats.length])

  useEffect(() => {
    if (!activeBeat || visibleCount >= characters.length) return undefined
    const timer = window.setInterval(() => {
      setVisibleCount((count) => Math.min(count + 1, characters.length))
    }, 24)
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
      event.preventDefault()
      requestAdvance()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  })

  const handleStageClick = (event) => {
    if (event.target.closest('button, textarea, input, select, a, [data-stop-advance]')) return
    requestAdvance()
  }

  return (
    <div className="vn-stage" onClick={handleStageClick} role="button" tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          requestAdvance()
        }
      }}>
      <div className="vn-stage-spacer" />
      <div className={`vn-beat-frame ${activeBeat?.type === 'dialogue' ? 'dialogue' : 'narration'}`}>
        {activeBeat?.speaker && <div className="vn-speaker">{activeBeat.speaker}</div>}
        {activeBeat && (
          <div className="vn-text">
            {characters.slice(0, visibleCount).join('')}
            {!revealed && <span className="vn-caret">▍</span>}
          </div>
        )}
        {revealed && activeBeat && <div className="vn-advance-mark">▼</div>}
      </div>
      {(initialLoading || (busy && !activeBeat)) && <div className="vn-loading-dots">· · ·</div>}
      {waitingForNext && <div className="vn-loading-dots vn-loading-dots-waiting">· · ·</div>}
    </div>
  )
}
