import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
const mocks = vi.hoisted(() => ({ summary: vi.fn(), sync: vi.fn(), prime: vi.fn() }))
vi.mock('../src/pwa/offlineQueue', () => ({ getOfflineQueueSummary: mocks.summary, syncOfflineQueue: mocks.sync }))
vi.mock('../src/pwa/offlineBootstrap', () => ({ primeOfflineData: mocks.prime }))
vi.mock('../src/lib/mobileBoot', () => ({ useMobileBoot: () => ({ user: mocks.user }) }))
let wrapper
beforeEach(() => {
  vi.resetModules()
  vi.clearAllMocks()
  vi.useFakeTimers()
  mocks.user = ref('employee@example.test')
  Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' })
  mocks.summary.mockResolvedValue({ total: 1, queued: 1, failed: 0, syncing: 0 })
  mocks.sync.mockResolvedValue({ synced: 1, failed: 0, skipped: false })
  mocks.prime.mockResolvedValue({ user: 'employee@example.test' })
})
afterEach(() => { wrapper?.unmount(); vi.useRealTimers() })

describe('Offline refresh requests', () => {
  it('syncs queued work before downloading exactly one fresh dataset on startup and reconnect', async () => {
    const order = []
    mocks.sync.mockImplementation(async () => { order.push('sync'); return { synced: 1, failed: 0 } })
    mocks.prime.mockImplementation(async () => { order.push('prime'); return { user: 'employee@example.test' } })
    const { useOfflineSync } = await import('../src/pwa/useOfflineSync')
    wrapper = mount({ setup: useOfflineSync, template: '<div />' })
    await flushPromises()
    expect(order).toEqual(['sync', 'prime'])
    window.dispatchEvent(new Event('online'))
    await flushPromises()
    expect(order).toEqual(['sync', 'prime', 'sync', 'prime'])
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
})
