import { afterEach, beforeEach, describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'

const mocks = vi.hoisted(() => ({ api: vi.fn(), subscription: vi.fn() }))
vi.mock('../src/lib/api', () => ({ apiRequest: mocks.api }))
let wrapper, metadata, serviceWorkerDescriptor
const bootData = () => ({
  user: 'viewer@example.test', user_fullname: 'Viewer', favicon: '',
  navigation_access: { has_employee_profile: true },
  pwa_metadata: { app_name: 'MSS Mobile', short_name: 'MSS', icon: '/icon.png', apple_touch_icon: '/apple.png' },
  push_config: { configured: true, public_key: 'PUBLIC' },
})

beforeEach(() => {
  serviceWorkerDescriptor = Object.getOwnPropertyDescriptor(navigator, 'serviceWorker')
  vi.resetModules(); vi.useFakeTimers(); vi.clearAllMocks()
  document.head.innerHTML = ''
  mocks.api.mockImplementation(async url => {
    if (url.endsWith('get_mobile_boot')) return { message: bootData() }
    if (url.endsWith('save_push_subscription')) return { message: { enabled: true } }
    throw new Error(`Unexpected API: ${url}`)
  })
  vi.stubGlobal('Notification', class { static permission = 'granted' })
  vi.stubGlobal('PushManager', class {})
  mocks.subscription.mockResolvedValue(null)
  Object.defineProperty(navigator, 'serviceWorker', { configurable: true, value: {
    getRegistration: async () => ({ active: {}, pushManager: { getSubscription: mocks.subscription } }),
  } })
})
afterEach(() => {
  wrapper?.unmount(); metadata?.stopVertoPwaTitleObserver()
  if (serviceWorkerDescriptor) Object.defineProperty(navigator, 'serviceWorker', serviceWorkerDescriptor)
  else delete navigator.serviceWorker
  vi.clearAllTimers(); vi.useRealTimers(); vi.unstubAllGlobals()
  document.head.innerHTML = ''; document.body.innerHTML = ''
})

async function startup() {
  const App = (await import('../src/App.vue')).default
  const { useMobileBoot } = await import('../src/lib/mobileBoot')
  const { usePushNotifications } = await import('../src/pwa/usePushNotifications')
  metadata = await import('../src/pwa/applyPwaHeadTags')
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: { template: '<div>Home</div>' } }] })
  await router.push('/'); await router.isReady()
  wrapper = mount(App, { global: { plugins: [router] } })
  metadata.applyVertoPwaHeadTags(router)
  await Promise.all([useMobileBoot().loadMobileBoot(), usePushNotifications().initialisePushNotifications()])
  await flushPromises(); await vi.advanceTimersByTimeAsync(3100); await flushPromises()
  return { useMobileBoot, usePushNotifications }
}

describe('Mobile startup request budget', () => {
  it('uses one configuration request for boot, navigation, PWA metadata and push setup', async () => {
    await startup()
    expect(mocks.api.mock.calls.map(([url]) => url)).toEqual(['/api/method/verto.api.mobile.boot.get_mobile_boot'])
    expect(wrapper.find('.verto-no-employee-profile').exists()).toBe(false)
    expect(document.querySelector('meta[name="application-name"]').content).toBe('MSS Mobile')
    const icon = document.querySelector('link[rel="icon"]')
    const manifest = document.querySelector('link[rel="manifest"]')
    await vi.advanceTimersByTimeAsync(3000)
    expect(document.querySelector('link[rel="icon"]')).toBe(icon)
    expect(document.querySelector('link[rel="manifest"]')).toBe(manifest)
    expect(mocks.api).toHaveBeenCalledOnce()
  })

  it('still registers an existing push subscription for the signed-in session', async () => {
    mocks.subscription.mockResolvedValue({ toJSON: () => ({ endpoint: 'https://push.example.test/device', keys: { auth: 'test' } }) })
    await startup()
    expect(mocks.api.mock.calls.map(([url]) => url)).toEqual([
      '/api/method/verto.api.mobile.boot.get_mobile_boot',
      '/api/method/verto.api.mobile.push_notifications.save_push_subscription',
    ])
    expect(mocks.api.mock.calls[1][1].method).toBe('POST')
  })

  it('keeps employee-only navigation hidden for viewers without a profile', async () => {
    mocks.api.mockResolvedValue({ message: { ...bootData(), navigation_access: { has_employee_profile: false } } })
    await startup()
    expect(wrapper.find('.verto-no-employee-profile').exists()).toBe(true)
    expect(mocks.api).toHaveBeenCalledOnce()
  })

  it('uses the existing endpoints when an older boot response lacks the new sections', async () => {
    mocks.api.mockImplementation(async url => {
      if (url.endsWith('get_mobile_boot')) return { message: { user: 'viewer' } }
      if (url.endsWith('get_navigation_access')) return { message: { has_employee_profile: false } }
      if (url.endsWith('get_push_config')) return { message: { configured: false } }
      throw new Error(url)
    })
    const fetch = vi.fn(async () => new Response(JSON.stringify({ message: bootData().pwa_metadata })))
    vi.stubGlobal('fetch', fetch)
    await startup()
    expect(mocks.api).toHaveBeenCalledTimes(3)
    expect(fetch).toHaveBeenCalledOnce()
    expect(wrapper.find('.verto-no-employee-profile').exists()).toBe(true)
  })

  it('does not start another boot request when reload is clicked during startup', async () => {
    let resolve
    mocks.api.mockReturnValue(new Promise(r => { resolve = r }))
    const { useMobileBoot } = await import('../src/lib/mobileBoot')
    const state = useMobileBoot()
    const first = state.loadMobileBoot()
    const reload = state.reloadMobileBoot()
    expect(mocks.api).toHaveBeenCalledOnce()
    resolve({ message: bootData() })
    await Promise.all([first, reload])
    expect(state.loaded.value).toBe(true)
  })
})
