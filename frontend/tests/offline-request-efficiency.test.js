import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
const mocks = vi.hoisted(() => ({ summary: vi.fn(), sync: vi.fn(), prime: vi.fn() }))
vi.mock('../src/pwa/offlineQueue', () => ({ getOfflineQueueSummary: mocks.summary, syncOfflineQueue: mocks.sync }))
vi.mock('../src/pwa/offlineBootstrap', () => ({ primeOfflineData: mocks.prime }))
let wrapper
beforeEach(() => {
  vi.resetModules()
  vi.clearAllMocks()
  vi.useFakeTimers()
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
