export async function requestJson(baseUrl, path, options = {}) {
  const started = performance.now()
  const response = await fetch(`${baseUrl.replace(/\/+$/, '')}${path}`, options)
  if (!response.ok) {
    const message = await response.text().catch(() => response.statusText)
    throw new Error(`${response.status} ${response.statusText} – ${message}`)
  }
  return { data: await response.json(), latency: Math.round(performance.now() - started) }
}

export const postJson = (baseUrl, path, body) => requestJson(baseUrl, path, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const postForm = (baseUrl, path, body) => requestJson(baseUrl, path, { method: 'POST', body })
