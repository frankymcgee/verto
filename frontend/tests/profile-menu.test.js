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
  navigate: vi.fn(),
  setTheme: vi.fn(),
  employeeId: 'HR-EMP-001',
  queued: 0,
  canReview: false,
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ path: '/', fullPath: '/', meta: {} }),
  useRouter: () => ({ push: calls.navigate }),
}))
vi.mock('../src/lib/mobileBoot', () => ({
  useMobileBoot: () => ({
    appName: ref('Verto'),
    appIconUrl: ref(''),
    user: ref('user@example.test'),
    userFullname: ref('Test User'),
    employeeId: ref(calls.employeeId),
    canReviewTimesheets: ref(calls.canReview),
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
    summary: ref({ total: calls.queued, queued: calls.queued, failed: 0 }),
    primeNow: calls.prime,
    syncNow: calls.sync,
  }),
}))
vi.mock('../src/lib/appBrowser', () => ({ openAppBrowser: calls.browser }))
vi.mock('../src/lib/mobileTheme', () => ({ useMobileTheme: () => ({
  themePreference: ref('Light'), themeSaving: ref(false), themeError: ref(''), setTheme: calls.setTheme,
}) }))
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
  calls.employeeId = 'HR-EMP-001'
  calls.queued = 0
  calls.canReview = false
})
describe('Profile menu', () => {
  it.each([false, true])('expands theme choices only on request (compact=%s)', async compact => {
    w = mount(AppHeader, { props: { compact }, attachTo: document.body, global: { stubs: { AboutAppToast: true } } })
    const id = compact ? 'desktop-user-theme' : 'mobile-user-theme'
    expect(document.querySelector(`#${id}`)).toBeNull()
    await w.find('[aria-label="Open profile menu"]').trigger('click'); await flushPromises()
    expect(document.querySelector(`#${id}`)).toBeNull()
    const trigger = document.querySelector(`button[aria-controls="${id}"]`)
    expect(trigger.textContent).toContain('Light')
    expect(trigger.getAttribute('aria-expanded')).toBe('false')
    trigger.click(); await flushPromises()
    const choices = [...document.querySelectorAll(`#${id} button`)]
    expect(choices.map(choice => choice.textContent.replace('✓', '').trim())).toEqual(['Light', 'Dark', 'Automatic'])
    choices[1].click(); await flushPromises()
    expect(calls.setTheme).toHaveBeenCalledWith('Dark')
    expect(document.querySelector(`#${id}`)).toBeNull()
  })
  it('collapses the theme choices when the profile menu is closed and reopened', async () => {
    w = mount(AppHeader, { attachTo: document.body, global: { stubs: { AboutAppToast: true } } })
    const avatar = w.find('[aria-label="Open profile menu"]')
    await avatar.trigger('click'); await flushPromises()
    document.querySelector('button[aria-controls="mobile-user-theme"]').click(); await flushPromises()
    expect(document.querySelector('#mobile-user-theme')).not.toBeNull()
    await avatar.trigger('click'); await flushPromises()
    await avatar.trigger('click'); await flushPromises()
    expect(document.querySelector('#mobile-user-theme')).toBeNull()
  })
  it('shows the waiting count and opens the upload queue from the offline section', async () => {
    calls.queued = 2
    w = mount(AppHeader, {
      attachTo: document.body,
      global: { stubs: { AboutAppToast: true } },
    })
    await w.find('[aria-label="Open profile menu"]').trigger('click')
    await flushPromises()
    await click('Upload queue (2)')
    expect(calls.navigate).toHaveBeenCalledWith({ name: 'failed-uploads' })
  })

  it('shows the employee ID beneath the name and opens the native profile page', async () => {
    w = mount(AppHeader, {
      attachTo: document.body,
      global: { stubs: { AboutAppToast: true } },
    })
    await w.find('[aria-label="Open profile menu"]').trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('HR-EMP-001')
    expect(document.body.textContent).not.toContain('user@example.test')
    await click('My profile')
    expect(calls.navigate).toHaveBeenCalledWith({ name: 'my-profile' })
    expect(calls.browser).not.toHaveBeenCalled()
  })

  it('keeps My profile available without showing an email when no employee is linked', async () => {
    calls.employeeId = ''
    w = mount(AppHeader, {
      attachTo: document.body,
      global: { stubs: { AboutAppToast: true } },
    })
    await w.find('[aria-label="Open profile menu"]').trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('Test User')
    expect(document.body.textContent).not.toContain('user@example.test')
    await click('My profile')
    expect(calls.navigate).toHaveBeenCalledOnce()
  })

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


it('offers the exceptions queue only to timesheet reviewers', async () => {
  calls.canReview = true
  w = mount(AppHeader, { attachTo: document.body })
  await w.find('[aria-label="Open profile menu"]').trigger('click')
  await click('Timesheet exceptions')
  expect(calls.navigate).toHaveBeenCalledWith({ name: 'timesheet-exceptions' })
})
