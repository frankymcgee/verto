import { describe, it, expect, vi } from 'vitest'
import { createReadCoordinator } from '../../shared/requestCoordinator'
import { coordinateApiRead } from '../src/lib/requestCoordinator'
import { shouldRefreshChat, CHAT_POLL_INTERVAL_MS } from '../src/lib/chatRefreshPolicy'
import { createSaveQueue, sceneKey } from '../../verto/public/js/whiteboard/saveQueue'

const deferred = () => {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
const tick = async () => { for (let i = 0; i < 12; i++) await Promise.resolve() }

describe('API request coordination', () => {
  it('combines 20 identical pending reads and gives callers independent data', async () => {
    const reads = createReadCoordinator()
    const response = deferred()
    const fetch = vi.fn(() => response.promise)
    const requests = Array.from({ length: 20 }, () => reads.run('same', fetch))
    await tick()
    expect(fetch).toHaveBeenCalledTimes(1)
    response.resolve({ rows: [{ name: 'original' }] })
    const results = await Promise.all(requests)
    results[0].rows[0].name = 'edited'
    expect(results[1].rows[0].name).toBe('original')
    await reads.run('same', fetch)
    expect(fetch).toHaveBeenCalledTimes(2) // Completed reads are never cached online.
  })

  it('runs at most four reads and releases slots after failures', async () => {
    const reads = createReadCoordinator()
    const responses = Array.from({ length: 8 }, deferred)
    const calls = responses.map((response) => vi.fn(() => response.promise))
    const requests = calls.map((call, i) => reads.run(String(i), call).catch(() => 'failed'))
    await tick()
    expect(calls.filter((call) => call.mock.calls.length)).toHaveLength(4)
    responses[0].reject(new Error('server unavailable'))
    await tick()
    expect(calls[4]).toHaveBeenCalledOnce()
    for (const response of responses) response.resolve('ok')
    expect((await Promise.all(requests))[0]).toBe('failed')
  })

  it('does not reuse failed reads or join reads across a mutation boundary', async () => {
    const reads = createReadCoordinator()
    await expect(reads.run('same', () => Promise.reject(new Error('failure')))).rejects.toThrow('failure')
    const old = deferred()
    const oldRead = reads.run('same', () => old.promise)
    reads.invalidate()
    expect(await reads.run('same', async () => 'fresh')).toBe('fresh')
    old.resolve('old')
    expect(await oldRead).toBe('old')
  })

  it('coalesces equivalent POST reads without coalescing writes or get-or-create calls', async () => {
    const pending = deferred()
    const read = vi.fn(() => pending.promise)
    const firstBody = new FormData()
    firstBody.set('channel_id', 'a')
    firstBody.set('from_message', 'one')
    const secondBody = new FormData()
    secondBody.set('from_message', 'one')
    secondBody.set('channel_id', 'a')
    const url = '/api/method/raven.api.chat_stream.get_newer_messages'
    const a = coordinateApiRead(url, { method: 'POST', body: firstBody }, read)
    const b = coordinateApiRead(url, { method: 'POST', body: secondBody }, read)
    await tick()
    expect(read).toHaveBeenCalledOnce()
    const write = vi.fn(async () => 'saved')
    await Promise.all(Array.from({ length: 2 }, () => coordinateApiRead(
      '/api/method/verto.api.mobile.documents.create_mobile_doc', { method: 'POST' }, write
    )))
    expect(write).toHaveBeenCalledTimes(2)
    await Promise.all(Array.from({ length: 2 }, () => coordinateApiRead(
      '/api/method/verto.api.mobile.raven.get_or_create_peri_channel', {}, write
    )))
    expect(write).toHaveBeenCalledTimes(4)
    pending.resolve({ message: [] })
    await Promise.all([a, b])
  })

  it('keeps distinct filters separate and never fetches an already aborted request', async () => {
    const call = vi.fn(async () => ({ message: [] }))
    await Promise.all(['one', 'two'].map((txt) => coordinateApiRead(
      `/api/method/verto.api.mobile.documents.search_link?txt=${txt}`, {}, call
    )))
    expect(call).toHaveBeenCalledTimes(2)
    const controller = new AbortController()
    controller.abort()
    await expect(coordinateApiRead('/api/method/verto.api.mobile.home.get_home_summary',
      { signal: controller.signal }, call)).rejects.toThrow()
    expect(call).toHaveBeenCalledTimes(2)
  })

  it('does not make offline cache reads wait for slow online requests', async () => {
    const pending = deferred()
    const online = Array.from({ length: 4 }, (_, i) => coordinateApiRead(
      `/api/method/verto.api.mobile.documents.search_link?txt=slow${i}`, {}, () => pending.promise
    ))
    await tick()
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: false })
    try {
      const cached = vi.fn(async () => ({ message: 'cached form' }))
      const result = await coordinateApiRead('/api/method/verto.api.mobile.documents.get_form_schema', {}, cached)
      expect(result.message).toBe('cached form')
      expect(cached).toHaveBeenCalledOnce()
    } finally {
      Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
      pending.resolve({ message: [] })
      await Promise.all(online)
    }
  })
})

describe('Chat recovery traffic', () => {
  it('uses 12 connected recovery checks per hour and keeps 60 disconnected checks', () => {
    for (const [connected, expected] of [[true, 12], [false, 60]]) {
      let lastRefresh = 0, requests = 0
      for (let now = CHAT_POLL_INTERVAL_MS; now <= 3_600_000; now += CHAT_POLL_INTERVAL_MS) {
        if (shouldRefreshChat(connected, lastRefresh, now)) {
          lastRefresh = now
          requests++
        }
      }
      expect(requests).toBe(expected)
    }
  })
})

describe('Whiteboard autosave', () => {
  const elements = [{ id: 'shape', version: 1, versionNonce: 10 }]
  it('ignores selection, pan and zoom but notices edits, deletion, files and background', () => {
    const base = sceneKey(elements, { viewBackgroundColor: '#fff' }, {})
    expect(sceneKey(elements, { viewBackgroundColor: '#fff', scrollX: 50, zoom: { value: 2 }, selectedElementIds: { shape: true } }, {})).toBe(base)
    expect(sceneKey([{ ...elements[0], version: 2 }], { viewBackgroundColor: '#fff' }, {})).not.toBe(base)
    expect(sceneKey([{ ...elements[0], isDeleted: true }], { viewBackgroundColor: '#fff' }, {})).not.toBe(base)
    expect(sceneKey(elements, { viewBackgroundColor: '#fff' }, { image: {} })).not.toBe(base)
    expect(sceneKey(elements, { viewBackgroundColor: '#000' }, {})).not.toBe(base)
  })

  it('saves one request at a time and sends only the newest queued scene', async () => {
    const pending = deferred()
    const save = vi.fn().mockReturnValueOnce(pending.promise).mockResolvedValue({ saved: true })
    const queue = createSaveQueue(save, vi.fn())
    queue.baseline('empty')
    queue.update('one', { content: 1 })
    const saving = queue.flush()
    queue.update('two', { content: 2 })
    queue.update('three', { content: 3 })
    void queue.flush() // pagehide/unmount must not start a duplicate request.
    expect(save).toHaveBeenCalledTimes(1)
    pending.resolve()
    await saving
    expect(save.mock.calls.map(([state]) => state.content)).toEqual([1, 3])
    await queue.flush()
    expect(save).toHaveBeenCalledTimes(2)
  })

  it('retains failed edits for retry and persists undo back to the original scene', async () => {
    const save = vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue({ saved: true })
    const onError = vi.fn()
    const queue = createSaveQueue(save, onError)
    queue.baseline('original')
    queue.update('changed', { text: 'changed' })
    await queue.flush()
    expect(onError).toHaveBeenCalledOnce()
    await queue.flush()
    queue.update('original', { text: 'original' })
    await queue.flush()
    expect(save).toHaveBeenCalledTimes(3)
    expect(save.mock.calls.at(-1)[0].text).toBe('original')
  })
})
