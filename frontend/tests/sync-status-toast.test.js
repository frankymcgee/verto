import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { h, reactive, ref } from 'vue'
import { ToastProvider, toast } from 'frappe-ui'
import OfflineSyncStatus from '../src/components/OfflineSyncStatus.vue'
import { formOpen } from '../src/pwa/formActivity'

const mocks = vi.hoisted(() => ({ state: null, user: null, route: null, push: vi.fn(), prime: vi.fn() }))
vi.mock('../src/pwa/useOfflineSync', () => ({ useOfflineSync: () => mocks.state }))
vi.mock('../src/lib/mobileBoot', () => ({ useMobileBoot: () => ({ user: mocks.user }) }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.push }), useRoute: () => mocks.route }))
let wrapper
let calls
const source = (key, value) => { mocks.state[key].value = value }
const count = (extra = {}) => source('summary', { total: 0, queued: 0, failed: 0, syncing: 0, ...extra })
async function render() {
  wrapper = mount({ render: () => [h(ToastProvider), h(OfflineSyncStatus)] }, { attachTo: document.body })
  await flushPromises()
}
const notices = () => document.querySelectorAll('[data-sonner-toast]:not([data-removed="true"])')
function current() { return document.querySelector('[data-sonner-toast]:not([data-removed="true"])') }
async function settle() { await flushPromises(); await new Promise(requestAnimationFrame); await flushPromises() }
beforeEach(() => {
  vi.clearAllMocks()
  formOpen.value = false
  mocks.user = ref('employee@example.test')
  mocks.route = reactive({ name: 'home' })
  mocks.state = {
    isOnline: ref(true), isSyncing: ref(false), isPriming: ref(false), showReadyConfirmation: ref(false),
    lastOfflineRefreshAt: ref(''), offlineRefreshError: ref(''), lastSyncMessage: ref(''), lastSyncResult: ref(null),
    summary: ref({ total: 0, queued: 0, failed: 0, syncing: 0 }), primeNow: mocks.prime,
  }
  calls = Object.fromEntries(['info', 'warning', 'error', 'success', 'dismiss'].map(kind => [kind, vi.spyOn(toast, kind)]))
})
afterEach(async () => {
  wrapper?.unmount()
  await settle()
  document.body.innerHTML = ''
  formOpen.value = false
  vi.restoreAllMocks()
  vi.useRealTimers()
})

describe('Offline sync toast', () => {
  it('keeps idle polling and empty sync checks quiet, without a layout bar', async () => {
    await render()
    source('isSyncing', true); await settle()
    count(); await settle()
    source('lastSyncResult', { synced: 0, failed: 0, skipped: false })
    source('isSyncing', false); await settle()
    expect(notices()).toHaveLength(0)
    expect(calls.info).not.toHaveBeenCalled()
    expect(wrapper.findComponent(OfflineSyncStatus).find('[role="status"]').exists()).toBe(false)
  })

  it('uses one toast through preparation, queue upload and confirmed completion', async () => {
    source('isPriming', true)
    await render()
    expect(current().textContent).toContain('Preparing offline data')
    const id = calls.info.mock.results[0].value
    source('isPriming', false)
    count({ total: 2, queued: 2 })
    source('isSyncing', true)
    await settle()
    expect(notices()).toHaveLength(1)
    expect(current().textContent).toContain('Syncing saved work')
    expect(calls.info.mock.calls.at(-1)[1].id).toBe(id)
    source('lastSyncResult', { synced: 2, failed: 0, skipped: false })
    source('lastSyncMessage', '2 queued items synced.')
    count()
    source('isSyncing', false)
    await settle()
    expect(notices()).toHaveLength(1)
    expect(current().textContent).toContain('Saved work synced')
    expect(calls.success.mock.calls.at(-1)[1]).toMatchObject({ id, duration: 4000 })
    expect(current().textContent).toContain('2 queued items synced.')
  })

  it('auto-dismisses a success that replaced an indefinite progress notice', async () => {
    source('isPriming', true)
    await render()
    const id = calls.info.mock.results[0].value
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    source('isPriming', false)
    source('lastOfflineRefreshAt', '2026-11-25T02:00:00Z')
    source('showReadyConfirmation', true)
    await flushPromises()
    await vi.advanceTimersByTimeAsync(4100)
    expect(calls.dismiss).toHaveBeenCalledWith(id)
  })

  it('keeps failures persistent and does not repeat identical queue polls', async () => {
    count({ total: 1, failed: 1 })
    await render()
    expect(current().textContent).toContain('1 upload needs attention')
    expect(calls.error.mock.calls[0][1].duration).toBe(Infinity)
    count({ total: 1, failed: 1 }); await settle()
    expect(calls.error).toHaveBeenCalledTimes(1)
    current().querySelector('[data-close-button]').click()
    await settle()
    count({ total: 1, failed: 1 }); await settle()
    expect(calls.error).toHaveBeenCalledTimes(1)
  })

  it('opens Upload queue from the real toast action', async () => {
    count({ total: 1, failed: 1 })
    await render()
    current().querySelector('[data-action]').click()
    await settle()
    expect(mocks.push).toHaveBeenCalledWith({ name: 'failed-uploads' })
  })

  it('keeps navigation and refresh actions off an open form', async () => {
    formOpen.value = true
    count({ total: 1, failed: 1 })
    await render()
    expect(current().querySelector('[data-action]')).toBeNull()
    expect(current().textContent).toContain('Finish this form')
    count()
    source('offlineRefreshError', 'Could not download offline data.')
    await settle()
    expect(current().querySelector('[data-action]')).toBeNull()
    expect(mocks.push).not.toHaveBeenCalled()
    expect(mocks.prime).not.toHaveBeenCalled()
  })

  it('retries cache preparation in place and keeps its progress toast open', async () => {
    source('offlineRefreshError', 'Could not download offline data.')
    mocks.prime.mockImplementation(() => {
      source('offlineRefreshError', '')
      source('isPriming', true)
    })
    await render()
    const id = calls.error.mock.results[0].value
    current().querySelector('[data-action]').click()
    await settle()
    expect(mocks.prime).toHaveBeenCalledOnce()
    expect(notices()).toHaveLength(1)
    expect(current().textContent).toContain('Preparing offline data')
    expect(calls.info.mock.calls.at(-1)[1].id).toBe(id)
  })

  it('shows readiness once and connection recovery without claiming an upload', async () => {
    source('isOnline', false)
    await render()
    expect(current().textContent).toContain('Offline mode')
    source('isOnline', true); await settle()
    expect(current().textContent).toContain('Connection restored')
    source('lastOfflineRefreshAt', '2026-11-25T02:00:00Z')
    source('showReadyConfirmation', true); await settle()
    expect(current().textContent).toContain('Offline data ready')
    count(); await settle()
    expect(calls.success).toHaveBeenCalledTimes(2)
    expect(calls.success.mock.calls.every(([title]) => title !== 'Saved work synced')).toBe(true)
  })

  it('keeps skipped and failed sync attempts out of success notifications', async () => {
    count({ total: 1, queued: 1 })
    source('isSyncing', true)
    await render()
    source('lastSyncResult', { synced: 0, failed: 0, skipped: true })
    source('isSyncing', false); await settle()
    expect(calls.success).not.toHaveBeenCalled()
    source('lastSyncResult', { synced: 0, failed: 0, skipped: false, error: '<img src=x onerror=alert(1)>' })
    await settle()
    expect(current().textContent).toContain('Could not finish syncing')
    expect(current().querySelector('img')).toBeNull()
    expect(current().textContent).toContain('<img src=x onerror=alert(1)>')
  })

  it('cleans up its own notification and uses a new ID after an account change', async () => {
    source('isPriming', true)
    await render()
    const previousId = calls.info.mock.results[0].value
    mocks.user.value = 'another@example.test'
    await settle()
    const nextId = calls.info.mock.results.at(-1).value
    expect(nextId).not.toBe(previousId)
    expect(calls.dismiss).toHaveBeenCalledWith(previousId)
    expect(current().textContent).toContain('Preparing offline data')
    wrapper.unmount(); wrapper = null
    await settle()
    expect(calls.dismiss).toHaveBeenCalledWith(nextId)
    expect(calls.dismiss.mock.calls.every(args => args[0] !== undefined)).toBe(true)
  })

  it('keeps Upload queue controls clear while that page already displays status', async () => {
    count({ total: 1, failed: 1 })
    mocks.route.name = 'failed-uploads'
    await render()
    expect(calls.error).not.toHaveBeenCalled()
    expect(notices()).toHaveLength(0)
    mocks.route.name = 'home'
    await settle()
    expect(current().textContent).toContain('1 upload needs attention')
  })
})
