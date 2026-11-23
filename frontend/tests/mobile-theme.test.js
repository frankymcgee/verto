import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import { flushPromises } from '@vue/test-utils'

const api = vi.hoisted(() => vi.fn())
vi.mock('../src/lib/api', () => ({ apiRequest: api }))
let stop, theme, boot, media
beforeEach(async () => {
  vi.resetModules(); api.mockReset()
  media = new EventTarget()
  media.matches = false
  vi.stubGlobal('matchMedia', () => media)
  localStorage.clear()
  boot = ref({ user: 'worker@example.test', theme_preference: 'Dark' })
  const module = await import('../src/lib/mobileTheme')
  stop = module.installMobileTheme(boot)
  theme = module.useMobileTheme()
  api.mockResolvedValue({ message: { user: boot.value.user, theme: 'Light' } })
})
afterEach(() => {
  stop?.(); vi.unstubAllGlobals()
  document.documentElement.removeAttribute('data-theme')
  document.documentElement.removeAttribute('data-theme-mode')
  document.documentElement.style.removeProperty('color-scheme')
})

describe('Shared user theme', () => {
  it('starts from Desk boot without an extra startup request and saves with the native endpoint', async () => {
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(localStorage.getItem('theme')).toBe('dark')
    expect(api).not.toHaveBeenCalled()
    await theme.setTheme('Light')
    expect(api.mock.calls[0][0]).toBe('/api/method/frappe.core.doctype.user.user.switch_theme')
    const request = api.mock.calls[0][1]
    expect(request.method).toBe('POST')
    expect([...request.body.entries()]).toEqual([['theme', 'Light']])
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(localStorage.getItem('verto:user-theme:worker@example.test')).toBe('Light')
  })

  it('follows system changes only when Automatic is selected', async () => {
    await theme.setTheme('Automatic')
    expect(localStorage.getItem('theme')).toBe('system')
    media.matches = true; media.dispatchEvent(new Event('change'))
    expect(document.documentElement.dataset.theme).toBe('dark')
    await theme.setTheme('Light')
    media.dispatchEvent(new Event('change'))
    expect(document.documentElement.dataset.theme).toBe('light')
  })

  it('retains the current theme and reports failed saves', async () => {
    api.mockRejectedValueOnce(new Error('Connection unavailable'))
    await theme.setTheme('Light')
    expect(theme.themePreference.value).toBe('Dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(theme.themeError.value).toBe('Connection unavailable')
    expect(theme.themeSaving.value).toBe(false)
  })

  it('refreshes a Desk change when returning to Mobile', async () => {
    window.dispatchEvent(new Event('focus')); await flushPromises()
    expect(api.mock.calls[0][0]).toBe('/api/method/verto.api.mobile.theme.get_user_theme')
    expect(theme.themePreference.value).toBe('Light')
  })

  it('ignores another account and synchronises the same account across tabs', () => {
    window.dispatchEvent(new StorageEvent('storage', { key: 'verto:user-theme:someone-else', newValue: 'Light' }))
    expect(theme.themePreference.value).toBe('Dark')
    window.dispatchEvent(new StorageEvent('storage', { key: 'verto:user-theme:worker@example.test', newValue: 'Light' }))
    expect(theme.themePreference.value).toBe('Light')
    expect(api).not.toHaveBeenCalled()
  })

  it('does not let a stale refresh undo a newly saved theme', async () => {
    let resolve
    api.mockImplementationOnce(() => new Promise(r => { resolve = r }))
    window.dispatchEvent(new Event('focus'))
    await theme.setTheme('Automatic')
    resolve({ message: { user: boot.value.user, theme: 'Dark' } })
    await flushPromises()
    expect(theme.themePreference.value).toBe('Automatic')
  })

  it('does not reset a saved theme when unrelated boot settings are refreshed', async () => {
    await theme.setTheme('Light')
    boot.value = { ...boot.value }
    await flushPromises()
    expect(theme.themePreference.value).toBe('Light')
  })

  it('applies a new account preference and ignores old in-flight requests', async () => {
    let resolve
    api.mockImplementationOnce(() => new Promise(r => { resolve = r }))
    window.dispatchEvent(new Event('focus'))
    boot.value = { user: 'other@example.test', theme_preference: 'Light' }
    await flushPromises()
    resolve({ message: { user: 'worker@example.test', theme: 'Dark' } })
    await flushPromises()
    expect(theme.themePreference.value).toBe('Light')
  })

  it('uses only the current account theme cache when starting offline', async () => {
    const descriptor = Object.getOwnPropertyDescriptor(navigator, 'onLine')
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: false })
    try {
      localStorage.setItem('verto:user-theme:worker@example.test', 'Automatic')
      boot.value = { user: 'worker@example.test', theme_preference: 'Light' }
      await flushPromises()
      expect(theme.themePreference.value).toBe('Automatic')
      boot.value = { user: 'new-account@example.test', theme_preference: 'Light' }
      await flushPromises()
      expect(theme.themePreference.value).toBe('Light')
    } finally {
      if (descriptor) Object.defineProperty(navigator, 'onLine', descriptor)
      else delete navigator.onLine
    }
  })

  it('removes resume and system listeners on unmount', async () => {
    stop(); window.dispatchEvent(new Event('focus'))
    media.matches = true; media.dispatchEvent(new Event('change'))
    await flushPromises()
    expect(api).not.toHaveBeenCalled()
  })
})
