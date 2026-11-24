import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
const mocks = vi.hoisted(() => ({ summary: vi.fn(), sync: vi.fn(), prime: vi.fn() }))
vi.mock('../src/pwa/offlineQueue', () => ({ getOfflineQueueSummary: mocks.summary, syncOfflineQueue: mocks.sync }))
vi.mock('../src/pwa/offlineBootstrap', () => ({ primeOfflineData: mocks.prime }))
vi.mock('../src/lib/mobileBoot', () => ({ useMobileBoot: () => ({ user: mocks.user }) }))
vi.mock('../src/lib/connection', () => ({
  serverReachable: mocks.reachable,
  connectionLost: () => { mocks.reachable.value = false },
  checkServerConnection: (...args) => mocks.check(...args),
}))
let wrapper
beforeEach(() => {
  vi.resetModules()
  vi.clearAllMocks()
  vi.useFakeTimers()
  mocks.user = ref('employee@example.test')
  mocks.reachable ??= ref(true)
  mocks.reachable.value = true
  mocks.available = true
  mocks.check = vi.fn(async () => { mocks.reachable.value = mocks.available; return mocks.available })
  Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' })
  mocks.summary.mockResolvedValue({ total: 1, queued: 1, failed: 0, syncing: 0 })
  mocks.sync.mockResolvedValue({ synced: 1, failed: 0, skipped: false })
  mocks.prime.mockResolvedValue({ user: 'employee@example.test' })
})
afterEach(() => { wrapper?.unmount(); vi.useRealTimers() })

describe('Offline refresh requests', () => {
  it('syncs before one startup download, debounces reconnects and keeps recent offline data', async () => {
    const order = []
    mocks.sync.mockImplementation(async () => { order.push('sync'); return { synced: 1, failed: 0 } })
    mocks.prime.mockImplementation(async () => { order.push('prime'); return { user: 'employee@example.test' } })
    const { useOfflineSync } = await import('../src/pwa/useOfflineSync')
    wrapper = mount({ setup: useOfflineSync, template: '<div />' })
    await flushPromises()
    expect(order).toEqual(['sync', 'prime'])
    window.dispatchEvent(new Event('online'))
    await flushPromises()
    expect(order).toEqual(['sync', 'prime'])
    await vi.advanceTimersByTimeAsync(5000)
    expect(order).toEqual(['sync', 'prime', 'sync'])
  })

  it('waits for the account on startup and resumes waiting work when the app is visible again', async () => {
    mocks.user.value = ''
    mocks.summary.mockImplementation(async user =>
      user ? { total: 1, queued: 1, failed: 0, syncing: 0 } : { total: 0, queued: 0, failed: 0, syncing: 0 })
    const { useOfflineSync } = await import('../src/pwa/useOfflineSync')
    wrapper = mount({ setup: useOfflineSync, template: '<div />' })
    await flushPromises()
    expect(mocks.sync).not.toHaveBeenCalled()
    expect(mocks.prime).not.toHaveBeenCalled()

    mocks.user.value = 'employee@example.test'
    await flushPromises()
    expect(mocks.sync).toHaveBeenCalledWith('employee@example.test')
    expect(mocks.prime).toHaveBeenCalledOnce()

    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' })
    document.dispatchEvent(new Event('visibilitychange'))
    await flushPromises()
    expect(mocks.sync).toHaveBeenCalledOnce()
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' })
    document.dispatchEvent(new Event('visibilitychange'))
    await flushPromises()
    expect(mocks.sync).toHaveBeenCalledTimes(2)
    expect(mocks.prime).toHaveBeenCalledOnce()
  })

  it('skips large periodic refreshes while hidden and lets manual refresh work', async () => {
    mocks.summary.mockResolvedValue({ total: 0, queued: 0, failed: 0, syncing: 0 })
    const { useOfflineSync } = await import('../src/pwa/useOfflineSync')
    let state
    wrapper = mount({ setup() { state = useOfflineSync(); return {} }, template: '<div />' })
    await flushPromises()
    expect(mocks.prime).toHaveBeenCalledOnce()
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' })
    await vi.advanceTimersByTimeAsync(15 * 60_000)
    expect(mocks.prime).toHaveBeenCalledOnce()
    await state.primeNow()
    expect(mocks.prime).toHaveBeenCalledTimes(2)
  })

  it('keeps queued work and cached data when Wi-Fi is connected but Verto cannot be reached', async () => {
    mocks.reachable.value = false
    mocks.available = false
    const { useOfflineSync } = await import('../src/pwa/useOfflineSync')
    let state
    wrapper = mount({ setup() { state = useOfflineSync(); return {} }, template: '<div />' })
    await flushPromises()
    expect(state.isOnline.value).toBe(false)
    expect(mocks.sync).not.toHaveBeenCalled()
    expect(mocks.prime).not.toHaveBeenCalled()
    await state.primeNow()
    expect(mocks.prime).not.toHaveBeenCalled()
    mocks.reachable.value = true
    mocks.available = true
    window.dispatchEvent(new Event('online'))
    await vi.advanceTimersByTimeAsync(5000)
    expect(mocks.sync).toHaveBeenCalledOnce()
    expect(mocks.prime).toHaveBeenCalledOnce()
  })

  it('waits for a stable connection through repeated radio dropouts', async () => {
    const { useOfflineSync } = await import('../src/pwa/useOfflineSync')
    wrapper = mount({ setup: useOfflineSync, template: '<div />' })
    await flushPromises()
    mocks.check.mockImplementation(async () => { mocks.reachable.value = navigator.onLine; return navigator.onLine })
    for (let i = 0; i < 3; i++) {
      window.dispatchEvent(new Event('offline'))
      window.dispatchEvent(new Event('online'))
      await vi.advanceTimersByTimeAsync(3000)
    }
    expect(mocks.sync).toHaveBeenCalledOnce()
    await vi.advanceTimersByTimeAsync(2000)
    expect(mocks.sync).toHaveBeenCalledTimes(2)
  })

  it.each(['/new/field-interaction', '/edit/daily-timesheet/TS-1', '/voice-jha/WORK-1'])(
    'defers automatic and manual offline refreshes throughout an open form: %s', async path => {
      const { setFormPath } = await import('../src/pwa/formActivity')
      setFormPath(path)
      const { useOfflineSync } = await import('../src/pwa/useOfflineSync')
      let state
      wrapper = mount({ setup() { state = useOfflineSync(); return {} }, template: '<div />' })
      await flushPromises()
      expect(mocks.sync).toHaveBeenCalledOnce()
      expect(await state.primeNow()).toBe(false)
      await vi.advanceTimersByTimeAsync(15 * 60_000)
      expect(mocks.prime).not.toHaveBeenCalled()
      setFormPath('/forms')
      await flushPromises()
      expect(mocks.prime).toHaveBeenCalledOnce()
    },
  )
})
