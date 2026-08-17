export async function fetchJson(url, opts = {}) {
  const resp = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!resp.ok) {
    let msg = `${resp.status}`
    try { msg = (await resp.json()).detail || msg } catch { /* ignore */ }
    throw new Error(msg)
  }
  return resp.json()
}

/**
 * POST 一个 SSE 端点，按事件类型分发回调。
 * on: { delta, meta, done, error }；signal 用于中断流。
 */
export async function postSSE(url, body, on, signal) {
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  if (!resp.ok) {
    let msg = `${resp.status}`
    try { msg = (await resp.json()).detail || msg } catch { /* ignore */ }
    throw new Error(msg)
  }
  const reader = resp.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    let idx
    while ((idx = buf.indexOf('\n\n')) >= 0) {
      const raw = buf.slice(0, idx)
      buf = buf.slice(idx + 2)
      let evType = null
      let data = ''
      for (const line of raw.split('\n')) {
        if (line.startsWith('event: ')) evType = line.slice(7).trim()
        else if (line.startsWith('data: ')) data += line.slice(6)
      }
      if (!evType) continue
      let obj
      try { obj = JSON.parse(data) } catch { continue }
      if (on[evType]) on[evType](obj)
      if (evType === 'done' || evType === 'error') return
    }
  }
}
