import { useEffect, useRef, useState } from 'react'
import { fetchJson, postSSE } from '../api.js'
import { useStore } from '../store.js'
import BeatPlayer, { getTurnBeats } from './BeatPlayer.jsx'
import ChoicePanel from './ChoicePanel.jsx'

export default function CurrentScene() {
  const worldId = useStore((s) => s.worldId)
  const bumpWorlds = useStore((s) => s.bumpWorlds)
  const [beats, setBeats] = useState([])
  const [pendingMeta, setPendingMeta] = useState(null)
  const [serverDone, setServerDone] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [history, setHistory] = useState(null)
  const [choiceVisible, setChoiceVisible] = useState(false)
  const [roundKey, setRoundKey] = useState(0)
  const [initialLoading, setInitialLoading] = useState(false)
  const abortRef = useRef(null)
  const submittingRef = useRef(false)

  const lastTurn = history?.turns?.[history.turns.length - 1]
  const time = lastTurn?.time_display || ''
  const place = pendingMeta?.place || lastTurn?.meta?.place || ''

  const applyHistory = (payload) => {
    setHistory(payload)
    const last = payload?.turns?.[payload.turns.length - 1]
    if (!last) return false
    setBeats(getTurnBeats(last))
    setPendingMeta(last.meta || null)
    setServerDone(true)
    setBusy(false)
    setRoundKey((key) => key + 1)
    return true
  }

  const runSSE = async (url, body) => {
    const controller = new AbortController()
    abortRef.current = controller
    setBusy(true)
    setInitialLoading(true)
    setError('')
    setChoiceVisible(false)
    setBeats([])
    setPendingMeta(null)
    setServerDone(false)
    setRoundKey((key) => key + 1)
    try {
      await postSSE(url, body, {
        beat: (event) => {
          if (event.beat) setBeats((current) => [...current, event.beat])
          setInitialLoading(false)
        },
        meta: (event) => {
          setPendingMeta(event.meta || null)
          setInitialLoading(false)
        },
        done: (event) => {
          setServerDone(true)
          setBusy(false)
          setInitialLoading(false)
          if (event.history) {
            setHistory(event.history)
            const last = event.history.turns?.[event.history.turns.length - 1]
            if (last) setPendingMeta((current) => current || last.meta || null)
          }
          bumpWorlds()
        },
        error: (event) => {
          setError(event.message || '生成失败')
          setBusy(false)
          setInitialLoading(false)
        },
      }, controller.signal)
    } catch (event) {
      if (event.name !== 'AbortError') {
        setError(event.message || '连接失败')
        setBusy(false)
        setInitialLoading(false)
      }
    } finally {
      if (abortRef.current === controller) abortRef.current = null
      submittingRef.current = false
    }
  }

  useEffect(() => {
    let cancelled = false
    setHistory(null)
    setBeats([])
    setPendingMeta(null)
    setServerDone(false)
    setChoiceVisible(false)
    setError('')
    ;(async () => {
      try {
        const payload = await fetchJson(`/api/game/${worldId}/history`)
        if (cancelled) return
        if (!applyHistory(payload)) {
          await runSSE(`/api/game/${worldId}/start`, {})
        }
      } catch (event) {
        if (!cancelled) setError(event.message || '载入世界失败')
      }
    })()
    return () => {
      cancelled = true
      abortRef.current?.abort()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [worldId])

  const submitAction = async (value) => {
    const action = String(value || '').trim()
    if (!action || busy || submittingRef.current) return
    submittingRef.current = true
    await runSSE(`/api/game/${worldId}/action`, { input: action })
  }

  const retry = () => runSSE(`/api/game/${worldId}/start`, {})

  return (
    <div className="current-scene">
      <div className="current-scene-head">
        {time && <span className="mono chip">{time}</span>}
        {place && <span className="chip dim">{place}</span>}
      </div>
      <div className="current-scene-body">
        {error && !beats.length ? (
          <div className="scene-retry">
            <div className="error">{error}</div>
            <button type="button" className="btn primary" onClick={retry}>重试开场</button>
          </div>
        ) : (
          <>
            <BeatPlayer key={roundKey} beats={beats} serverDone={serverDone}
              pendingMeta={pendingMeta} busy={busy} initialLoading={initialLoading}
              onChoiceReady={() => setChoiceVisible(true)} />
            {choiceVisible && pendingMeta && (
              <div className="choice-layer">
                <ChoicePanel choices={pendingMeta.choices || []} disabled={busy} onSubmit={submitAction} />
              </div>
            )}
          </>
        )}
      </div>
      {error && beats.length > 0 && <div className="scene-inline-error error">{error}</div>}
    </div>
  )
}
