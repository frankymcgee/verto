import { readonly, ref, watch, type Ref } from 'vue'
import { apiRequest } from './api'

type ThemePreference = 'Light' | 'Dark' | 'Automatic'
type ThemeBoot = { user: string; theme_preference?: string }
const choices: ThemePreference[] = ['Light', 'Dark', 'Automatic']
const preference = ref<ThemePreference>('Light')
const saving = ref(false)
const error = ref('')
let currentUser = ''
let revision = 0
let systemTheme: MediaQueryList | undefined
let refreshing: Promise<void> | null = null

function applyTheme(value: ThemePreference) {
  preference.value = value
  const dark = value === 'Dark' || (value === 'Automatic' && systemTheme?.matches)
  const root = document.documentElement
  root.dataset.theme = dark ? 'dark' : 'light'
  root.dataset.themeMode = value.toLowerCase()
  root.style.colorScheme = dark ? 'dark' : 'light'
  // Native Flow's colour-scheme composable reads this same-origin key on mount.
  try {
    localStorage.setItem('theme', value === 'Automatic' ? 'system' : value.toLowerCase())
    const key = `verto:user-theme:${currentUser}`
    if (currentUser && localStorage.getItem(key) !== value) localStorage.setItem(key, value)
  } catch { /* The server remains the source of the preference if storage is blocked. */ }
}

async function refreshTheme() {
  if (refreshing || !currentUser || saving.value || document.hidden || !navigator.onLine) return
  const user = currentUser
  const before = revision
  refreshing = (async () => {
    try {
      const { message } = await apiRequest<{ message: { user: string; theme: ThemePreference } }>(
        '/api/method/verto.api.mobile.theme.get_user_theme', { cache: 'no-store' }
      )
      if (currentUser === user && message.user === user && revision === before && choices.includes(message.theme)) {
        revision++
        applyTheme(message.theme)
      }
    } catch { /* Keep the last verified theme while offline or signing in. */ }
  })().finally(() => { refreshing = null })
  return refreshing
}

async function setTheme(value: ThemePreference) {
  if (saving.value || value === preference.value) return
  if (!choices.includes(value)) return
  error.value = ''
  if (!currentUser) { error.value = 'Wait for your account settings to load.'; return }
  const user = currentUser
  const change = ++revision
  saving.value = true
  try {
    const body = new FormData()
    body.set('theme', value)
    // Use Desk's native endpoint: it updates only the session user's desk_theme.
    await apiRequest('/api/method/frappe.core.doctype.user.user.switch_theme', { method: 'POST', body })
    if (currentUser !== user || revision !== change) return
    applyTheme(value)
  } catch (err) {
    if (currentUser === user) error.value = err instanceof Error ? err.message : 'Could not save your theme.'
  } finally {
    if (currentUser === user) saving.value = false
  }
}

export function installMobileTheme(boot: Readonly<Ref<ThemeBoot>>) {
  systemTheme = window.matchMedia('(prefers-color-scheme: dark)')
  const stop = watch([() => boot.value.user, () => boot.value.theme_preference] as const, ([user, value]) => {
    revision++
    currentUser = user || ''
    saving.value = false
    error.value = ''
    let choice = choices.includes(value as ThemePreference) ? value as ThemePreference : 'Light'
    // A cached boot may predate a saved theme. Offline, use only this user's cache.
    if (currentUser && !navigator.onLine) {
      try {
        const cached = localStorage.getItem(`verto:user-theme:${currentUser}`) as ThemePreference
        if (choices.includes(cached)) choice = cached
      } catch { /* Use the cached boot preference. */ }
    }
    applyTheme(choice)
  }, { immediate: true })
  const onSystemTheme = () => { if (preference.value === 'Automatic') applyTheme('Automatic') }
  const onResume = () => { void refreshTheme() }
  const onStorage = (event: StorageEvent) => {
    if (currentUser && event.key === `verto:user-theme:${currentUser}` && choices.includes(event.newValue as ThemePreference)) {
      revision++
      applyTheme(event.newValue as ThemePreference)
    }
  }
  systemTheme.addEventListener('change', onSystemTheme)
  window.addEventListener('focus', onResume)
  window.addEventListener('pageshow', onResume)
  document.addEventListener('visibilitychange', onResume)
  window.addEventListener('storage', onStorage)
  return () => {
    stop()
    revision++
    currentUser = ''
    systemTheme?.removeEventListener('change', onSystemTheme)
    window.removeEventListener('focus', onResume)
    window.removeEventListener('pageshow', onResume)
    document.removeEventListener('visibilitychange', onResume)
    window.removeEventListener('storage', onStorage)
  }
}

export function useMobileTheme() {
  return { themePreference: readonly(preference), themeSaving: readonly(saving), themeError: readonly(error), setTheme }
}
