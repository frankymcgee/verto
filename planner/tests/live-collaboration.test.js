import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, nextTick } from 'vue'
import { createListResource, setConfig } from 'frappe-ui'
import { createLiveRefreshQueue } from '../src/utils/liveRefreshQueue'
import { coalesceResource } from '../src/utils/coalesceResource'

const transport = vi.hoisted(() => ({ sockets: [], options: [] }))
vi.mock('socket.io-client', () => ({
  Manager: class {
    constructor(origin, options) { transport.options.push({ origin, options }) }
    socket(namespace) {
      const handlers = new Map()
      const socket = {
        namespace, connected: false, ack: null,
        on: vi.fn((name, callback) => { handlers.set(name, callback); return socket }),
        emit: vi.fn((name, callback) => { if (name === 'verto:planner_subscribe') socket.ack = callback }),
        timeout: () => socket,
        connect: vi.fn(() => {}), disconnect: vi.fn(), removeAllListeners: vi.fn(() => handlers.clear()),
        receive(name, payload) { if (name === 'connect') socket.connected = true; if (name === 'disconnect') socket.connected = false; handlers.get(name)?.(payload) },
      }
      transport.sockets.push(socket)
      return socket
    }
  },
}))
import { usePlannerRealtime } from '../src/composables/usePlannerRealtime'

const deferred = () => { let resolve; const promise = new Promise((r) => { resolve = r }); return { promise, resolve } }
let wrappers = []
beforeEach(() => {
  vi.useFakeTimers()
  transport.sockets.length = 0
  transport.options.length = 0
  Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' })
})
afterEach(() => { wrappers.forEach((w) => w.unmount()); wrappers = []; vi.useRealTimers(); document.head.innerHTML = '' })

describe('Coalesced live refreshes', () => {
  it('groups a bulk import into one refresh and retains updates arriving during it', async () => {
    const response = deferred()
    const refresh = vi.fn().mockReturnValueOnce(response.promise).mockResolvedValue(undefined)
    const queue = createLiveRefreshQueue({ refresh, canRun: () => true, delay: 400 })
    for (let i = 0; i < 100; i++) queue.request(['roster', 'projects'])
    await vi.advanceTimersByTimeAsync(400)
    expect(refresh).toHaveBeenCalledTimes(1)
    expect([...refresh.mock.calls[0][0]]).toEqual(['roster', 'projects'])
    queue.request(['employees'])
    queue.request(['projects'])
    await vi.advanceTimersByTimeAsync(5000)
    expect(refresh).toHaveBeenCalledTimes(1)
    response.resolve()
    await flushPromises()
    await vi.advanceTimersByTimeAsync(400)
    expect(refresh).toHaveBeenCalledTimes(2)
    expect([...refresh.mock.calls[1][0]]).toEqual(['employees', 'projects'])
    queue.stop()
  })

  it('holds changes while hidden or dragging and resumes once with the accumulated scopes', async () => {
    let ready = false
    const refresh = vi.fn(async () => {})
    const queue = createLiveRefreshQueue({ refresh, canRun: () => ready, delay: 400 })
    queue.request(['roster'])
    await vi.advanceTimersByTimeAsync(5000)
    expect(refresh).not.toHaveBeenCalled()
    queue.request(['employees'])
    ready = true
    queue.resume()
    await vi.advanceTimersByTimeAsync(400)
    expect(refresh).toHaveBeenCalledOnce()
    expect(refresh.mock.calls[0][0].size).toBe(2)
    queue.stop()
  })

  it('retains failed refreshes for a bounded retry and cancels on unmount', async () => {
    const refresh = vi.fn().mockRejectedValueOnce(new Error('temporary')).mockResolvedValue(undefined)
    const onError = vi.fn()
    const queue = createLiveRefreshQueue({ refresh, onError, canRun: () => true, delay: 400 })
    queue.request(['roster'])
    await vi.advanceTimersByTimeAsync(400)
    expect(onError).toHaveBeenCalledOnce()
    await vi.advanceTimersByTimeAsync(9999)
    expect(refresh).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1)
    expect(refresh).toHaveBeenCalledTimes(2)
    queue.request(['roster'])
    queue.stop()
    await vi.advanceTimersByTimeAsync(5000)
    expect(refresh).toHaveBeenCalledTimes(2)
  })

  it('serializes filter and live requests and finishes with the latest filter', async () => {
    const response = deferred()
    const fetch = vi.fn().mockReturnValueOnce(response.promise).mockImplementation(async (value) => value)
    const resource = coalesceResource({ fetch })
    const first = resource.fetch('January')
    resource.fetch('February')
    const latest = resource.fetch('March')
    expect(fetch).toHaveBeenCalledTimes(1)
    response.resolve('January')
    expect(await first).toBe('March')
    expect(await latest).toBe('March')
    expect(fetch.mock.calls.map(([value]) => value)).toEqual(['January', 'March'])
  })

  it('waits for real Frappe list resources and coalesces their filter changes', async () => {
    const response = deferred()
    const filters = ref({ company: 'First' })
    const requests = []
    const fetcher = vi.fn(({ params }) => {
      requests.push({ ...params.filters })
      return requests.length === 1 ? response.promise : Promise.resolve([{ name: 'latest' }])
    })
    setConfig('resourceFetcher', fetcher)
    try {
      const resource = coalesceResource(createListResource({ doctype: 'Employee', filters, auto: false }))
      const first = resource.fetch()
      expect(resource.list.loading).toBe(true)
      filters.value = { company: 'Middle' }
      resource.fetch()
      filters.value = { company: 'Latest' }
      const latest = resource.fetch()
      expect(fetcher).toHaveBeenCalledOnce()
      response.resolve([{ name: 'old' }])
      await Promise.all([first, latest])
      expect(requests).toEqual([{ company: 'First' }, { company: 'Latest' }])
      expect(resource.data).toEqual([{ name: 'latest' }])
      expect(resource.list.loading).toBe(false)
      resource.disposeRefresh()
    } finally { setConfig('resourceFetcher', undefined) }
  })
})

describe('Planner socket lifecycle', () => {
  function client(refresh, ready = ref(true)) {
    let state
    wrappers.push(mount({ setup() { state = usePlannerRealtime({ refresh, ready: () => ready.value }); return {} }, template: '<div />' }))
    return { state, socket: transport.sockets.at(-1) }
  }
  async function join(socket) { socket.receive('connect'); socket.ack(null, { ok: true }); await vi.advanceTimersByTimeAsync(650) }

  it('refreshes two viewers from the same committed event without sending document data', async () => {
    document.head.innerHTML = '<meta name="frappe-site-name" content="pilot-internal-site">'
    const a = vi.fn(async () => {}), b = vi.fn(async () => {})
    const first = client(a), second = client(b)
    await join(first.socket); await join(second.socket)
    expect(first.socket.namespace).toBe('/pilot-internal-site')
    expect(transport.options[0].origin).toBe(window.location.origin)
    expect(first.state.status.value).toBe('Live')
    a.mockClear(); b.mockClear()
    for (const socket of [first.socket, second.socket]) {
      for (let i = 0; i < 50; i++) socket.receive('verto:planner_changed', { scope: 'roster' })
    }
    await vi.advanceTimersByTimeAsync(650)
    expect(a).toHaveBeenCalledOnce(); expect(b).toHaveBeenCalledOnce()
    expect([...a.mock.calls[0][0]]).toEqual(['roster'])
  })

  it('refreshes after reconnect acknowledgment and ignores a late acknowledgment after disconnect', async () => {
    const refresh = vi.fn(async () => {})
    const { state, socket } = client(refresh)
    await join(socket)
    refresh.mockClear()
    socket.receive('disconnect')
    socket.receive('connect')
    const oldAck = socket.ack
    socket.receive('disconnect')
    oldAck(null, { ok: true })
    expect(state.status.value).toBe('Reconnecting')
    expect(refresh).not.toHaveBeenCalled()
    await join(socket)
    expect(refresh).toHaveBeenCalledOnce()
  })

  it('does not refresh hidden tabs until they become visible and cleans up its socket', async () => {
    const refresh = vi.fn(async () => {})
    const { socket } = client(refresh)
    await join(socket)
    refresh.mockClear()
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' })
    socket.receive('verto:planner_changed', { scope: 'projects' })
    await vi.advanceTimersByTimeAsync(6 * 60_000)
    expect(refresh).not.toHaveBeenCalled()
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' })
    document.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(650)
    expect(refresh).toHaveBeenCalledOnce()
    wrappers.pop().unmount()
    expect(socket.disconnect).toHaveBeenCalledOnce()
    expect(socket.emit).toHaveBeenCalledWith('verto:planner_unsubscribe')
  })
})
