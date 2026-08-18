import { useEffect, useRef, useState } from 'react'
import { fetchJson, postSSE } from '../api.js'
import { useStore } from '../store.js'
import BeatPlayer, { getTurnBeats } from './BeatPlayer.jsx'
import ChoicePanel from './ChoicePanel.jsx'

function turnCount(payload) {
  return payload?.turns?.length || 0
}

export default function CurrentScene() {
  const worldId = useStore((s) => s.worldId)
  const enabled = useStore((s) => s.tab === 'current')
  const bumpWorlds = useStore((s) => s.bumpWorlds)
  const [beats, setBeats] = useState([])
  const [pendingMeta, setPendingMeta] = useState(null)
  const [serverDone, setServerDone] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [history, setHistory] = useState(null)
  const [choiceVisible, setChoiceVisible] = useState(false)
  const [roundKey, setRoundKey] = useState(0)
  const [loadingDots, setLoadingDots] = useState(false)
  const [resumeAtEnd, setResumeAtEnd] = useState(false)
  const [recoveryRequest, setRecoveryRequest] = useState(null)
  const abortRef = useRef(null)
  const submittingRef = useRef(false)
  const requestRef = useRef(null)

  const lastTurn = history?.turns?.[history.turns.length - 1]
  const time = lastTurn?.time_display || ''
  const place = pendingMeta?.place || lastTurn?.meta?.place || ''

  const applyHistory = (payload, { readyForChoice = false } = {}) => {
    requestRef.current = null
    setHistory(payload)
    const last = payload?.turns?.[payload.turns.length - 1]
    if (!last) {
      setBeats([])
      setPendingMeta(null)
      setServerDone(false)
      setChoiceVisible(false)
      setResumeAtEnd(false)
      return false
    }
    setBeats(getTurnBeats(last))
    setPendingMeta(last.meta || null)
    setServerDone(true)
    setBusy(false)
    setResumeAtEnd(true)
    setChoiceVisible(readyForChoice)
    setRecoveryRequest(null)
    setRoundKey((key) => key + 1)
    return true
  }

  const reconcileFailure = async (message, request) => {
    try {
      const latest = await fetchJson(`/api/game/${worldId}/history`)
      if (requestRef.current !== request) return
      if (turnCount(latest) > request.historyTurnCount) {
        applyHistory(latest, { readyForChoice: true })
        setError('')
        bumpWorlds()
        return
      }
    } catch {
      // Keep the retry controls visible when the recovery request also fails.
    }
    if (requestRef.current !== request) return
    setError(message)
    setRecoveryRequest(request)
  }

  const runSSE = async (url, body, historyTurnCount = turnCount(history)) => {
    const controller = new AbortController()
    const request = { url, body, historyTurnCount }
    abortRef.current = controller
    requestRef.current = request
    setBusy(true)
    setError('')
    setRecoveryRequest(null)
    setChoiceVisible(false)
    setBeats([])
    setPendingMeta(null)
    setServerDone(false)
    setResumeAtEnd(false)
    setRoundKey((key) => key + 1)
    try {
      await postSSE(url, body, {
        beat: (event) => {
          if (event.beat) setBeats((current) => [...current, event.beat])
        },
        meta: (event) => setPendingMeta(event.meta || null),
        done: (event) => {
          setServerDone(true)
          setBusy(false)
          setLoadingDots(false)
          setRecoveryRequest(null)
          requestRef.current = null
          if (event.history) {
            setHistory(event.history)
            const last = event.history.turns?.[event.history.turns.length - 1]
            if (last) {
              setPendingMeta((current) => current || last.meta || null)
              setBeats((current) => current.length ? current : getTurnBeats(last))
            }
          }
          bumpWorlds()
        },
        error: (event) => {
          setBusy(false)
          setLoadingDots(false)
          setRecoveryRequest(request)
          void reconcileFailure(event.message || '生成失败', request)
        },
      }, controller.signal)
    } catch (event) {
      if (event.name !== 'AbortError') {
        setBusy(false)
        setLoadingDots(false)
        setRecoveryRequest(request)
        void reconcileFailure(event.message || '连接失败', request)
      }
    } finally {
      if (abortRef.current === controller) abortRef.current = null
      submittingRef.current = false
    }
  }

  useEffect(() => {
    if (!busy || beats.length > 0) {
      setLoadingDots(false)
      return undefined
    }
    const timer = window.setTimeout(() => setLoadingDots(true), 900)
    return () => window.clearTimeout(timer)
  }, [busy, beats.length, roundKey])

  useEffect(() => {
    let cancelled = false
    setHistory(null)
    setBeats([])
    setPendingMeta(null)
    setServerDone(false)
    setChoiceVisible(false)
    setRecoveryRequest(null)
    setError('')
    ;(async () => {
      try {
        const payload = await fetchJson(`/api/game/${worldId}/history`)
        if (cancelled) return
        if (!applyHistory(payload, { readyForChoice: turnCount(payload) > 0 })) {
          await runSSE(`/api/game/${worldId}/start`, {}, 0)
        }
      } catch (event) {
        if (!cancelled) {
          setError(event.message || '载入世界失败')
          setRecoveryRequest(null)
        }
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
    await runSSE(`/api/game/${worldId}/action`, { input: action }, turnCount(history))
  }

  const retryRequest = async () => {
    if (submittingRef.current) return
    const request = recoveryRequest || requestRef.current
    if (!request) {
      submittingRef.current = true
      await runSSE(`/api/game/${worldId}/start`, {}, turnCount(history))
      return
    }

    // Invalidate the old failure reconciliation before checking again. If the
    // original request committed just after its first failure, this prevents
    // retrying the same action and creating a duplicate turn.
    requestRef.current = null
    setRecoveryRequest(null)
    setError('')
    submittingRef.current = true
    try {
      const latest = await fetchJson(`/api/game/${worldId}/history`)
      if (turnCount(latest) > request.historyTurnCount) {
        applyHistory(latest, { readyForChoice: true })
        setError('')
        bumpWorlds()
        submittingRef.current = false
        return
      }
    } catch (event) {
      setBusy(false)
      setError(event.message || '无法确认本回合状态')
      setRecoveryRequest(request)
      submittingRef.current = false
      return
    }
    await runSSE(request.url, request.body, request.historyTurnCount)
  }

  const restorePrevious = async () => {
    const request = recoveryRequest || requestRef.current
    requestRef.current = null
    setRecoveryRequest(null)
    try {
      const payload = await fetchJson(`/api/game/${worldId}/history`)
      applyHistory(payload, { readyForChoice: turnCount(payload) > 0 })
      setError('')
    } catch (event) {
      setError(event.message || '无法恢复上一回合')
      if (request) setRecoveryRequest(request)
    }
  }

  const actionRecovery = recoveryRequest?.url.endsWith('/action')

  return (
    <div className="current-view">
      <div className="current-stage">
        <div className="stage-grain" aria-hidden="true" />
        <div className="scene-context" aria-label="当前场景">
          <strong>{time || '故事开始'}</strong>
          <span>{place || '未知地点'}</span>
        </div>
        <div className="scene-void" aria-hidden="true" />
        <div className="current-content">
          <BeatPlayer key={roundKey} beats={beats} serverDone={serverDone}
            pendingMeta={pendingMeta} loadingDots={loadingDots} resumeAtEnd={resumeAtEnd}
            enabled={enabled && !choiceVisible && !error}
            onChoiceReady={() => setChoiceVisible(true)} />
          {choiceVisible && pendingMeta && !error && (
            <ChoicePanel choices={pendingMeta.choices || []} disabled={busy} onSubmit={submitAction} />
          )}
        </div>
        {error && (
          <div className="scene-recovery">
            <div className="error">{error}</div>
            <div className="scene-recovery-actions">
              <button type="button" className="btn btn-primary" onClick={retryRequest}>
                {actionRecovery ? '重试本回合' : '重试开场'}
              </button>
              {actionRecovery && <button type="button" className="btn btn-secondary" onClick={restorePrevious}>返回上一选择</button>}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
