import { mount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { describe, it, expect, vi, afterEach } from 'vitest'
import AppHeader from '../src/components/AppHeader.vue'
import { Switch } from 'frappe-ui'
const calls = vi.hoisted(() => ({
  init: vi.fn(),
  enable: vi.fn(),
  disable: vi.fn(),
  prime: vi.fn(),
  sync: vi.fn(),
  browser: vi.fn(),
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ path: '/', fullPath: '/', meta: {} }),
}))
vi.mock('../src/lib/mobileBoot', () => ({
  useMobileBoot: () => ({
    appName: ref('Verto'),
    appIconUrl: ref(''),
    user: ref('user@example.test'),
    userFullname: ref('Test User'),
    userImageUrl: ref(''),
    reloadMobileBoot: vi.fn(),
  }),
}))
vi.mock('../src/pwa/usePushNotifications', () => ({
  usePushNotifications: () => ({
    loading: ref(false),
    enabling: ref(false),
    disabling: ref(false),
    configured: ref(true),
    supported: ref(true),
    subscribed: ref(false),
    permission: ref('default'),
    error: ref(''),
    needsIosInstall: ref(false),
    initialisePushNotifications: calls.init,
    enablePushNotifications: calls.enable,
    disablePushNotifications: calls.disable,
  }),
}))
vi.mock('../src/pwa/useOfflineSync', () => ({
  useOfflineSync: () => ({
    isOnline: ref(true),
    isSyncing: ref(false),
    isPriming: ref(false),
    lastOfflineRefreshAt: ref(''),
    offlineRefreshError: ref(''),
    summary: ref({ total: 0, failed: 0 }),
    primeNow: calls.prime,
    syncNow: calls.sync,
  }),
}))
vi.mock('../src/lib/appBrowser', () => ({ openAppBrowser: calls.browser }))
let w
const click = async (text) => {
  const el = [...document.querySelectorAll('button')].find(
    (el) => el.textContent.trim() === text
  )
  expect(el).toBeTruthy()
  el.click()
  await flushPromises()
}
afterEach(() => {
  w?.unmount()
  document.body.innerHTML = ''
  vi.clearAllMocks()
})
describe('Profile menu', () => {
  it('opens from the avatar and runs offline refresh from a real button', async () => {
    w = mount(AppHeader, {
      attachTo: document.body,
      global: { stubs: { AboutAppToast: true } },
    })
    await w.find('[aria-label="Open profile menu"]').trigger('click')
    await flushPromises()
    expect(calls.init).toHaveBeenCalledWith(true)
    await click('Refresh')
    expect(calls.prime).toHaveBeenCalledOnce()
  })
  it('runs notification permission workflow through the switch', async () => {
    w = mount(AppHeader, {
      attachTo: document.body,
      global: { stubs: { AboutAppToast: true } },
    })
    await w.find('[aria-label="Open profile menu"]').trigger('click')
    await flushPromises()
    w.findComponent(Switch).vm.$emit('update:modelValue', true)
    await flushPromises()
    expect(calls.enable).toHaveBeenCalledOnce()
  })
  it('opens About from the menu after pointer activation', async () => {
    w = mount(AppHeader, {
      attachTo: document.body,
      global: { stubs: { AboutAppToast: true } },
    })
    await w.find('[aria-label="Open profile menu"]').trigger('click')
    await flushPromises()
    await click('About')
    expect(w.findComponent({ name: 'AboutAppToast' }).props('open')).toBe(true)
  })
})
