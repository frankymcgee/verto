// VERTO_PWA_INSTALL_PROMPT_SETTINGS_FIX_2026_06_11

import { computed, onMounted, onUnmounted, ref } from 'vue'

type BeforeInstallPromptEvent = Event & {
  readonly platforms?: string[]
  readonly userChoice: Promise<{
    outcome: 'accepted' | 'dismissed'
    platform: string
  }>
  prompt: () => Promise<void>
}

const dismissedStorageKey = 'verto_pwa_install_prompt_dismissed_at'
const installedStorageKey = 'verto_pwa_installed_at'
const dismissCooldownMs = 1000 * 60 * 60 * 24 * 7

function getNow() {
  return Date.now()
}

function getStoredNumber(key: string) {
  const value = window.localStorage.getItem(key)
  const numberValue = Number(value)

  return Number.isFinite(numberValue) ? numberValue : 0
}

function isRecentlyDismissed() {
  const dismissedAt = getStoredNumber(dismissedStorageKey)

  if (!dismissedAt) {
    return false
  }

  return getNow() - dismissedAt < dismissCooldownMs
}

function isRunningStandalone() {
  return window.matchMedia('(display-mode: standalone)').matches ||
    (window.navigator as any).standalone === true
}

function isIOSDevice() {
  return /iPad|iPhone|iPod/i.test(window.navigator.userAgent) ||
    (
      window.navigator.platform === 'MacIntel' &&
      Number((window.navigator as any).maxTouchPoints || 0) > 1
    )
}

function isAndroidDevice() {
  return /Android/i.test(window.navigator.userAgent)
}

function isMobileOrTabletDevice() {
  return isIOSDevice() ||
    isAndroidDevice() ||
    /Mobile|Tablet/i.test(window.navigator.userAgent) ||
    window.matchMedia('(pointer: coarse)').matches
}

export function usePwaInstallPrompt() {
  const deferredPrompt = ref<BeforeInstallPromptEvent | null>(null)
  const installPromptAvailable = ref(false)
  const installing = ref(false)
  const installed = ref(false)
  const dismissed = ref(false)
  const error = ref('')

  const isStandalone = computed(() => isRunningStandalone())
  const isIOS = computed(() => isIOSDevice())
  const isAndroid = computed(() => isAndroidDevice())
  const isMobileOrTablet = computed(() => isMobileOrTabletDevice())

  const canShowPrompt = computed(() => {
    if (!isMobileOrTablet.value) {
      return false
    }

    if (installed.value || isStandalone.value) {
      return false
    }

    if (dismissed.value || isRecentlyDismissed()) {
      return false
    }

    return installPromptAvailable.value || isIOS.value
  })

  function dismissPrompt() {
    dismissed.value = true
    window.localStorage.setItem(dismissedStorageKey, String(getNow()))
  }

  async function install() {
    error.value = ''

    if (isIOS.value && !deferredPrompt.value) {
      return
    }

    if (!deferredPrompt.value) {
      error.value = 'The install prompt is not available yet.'
      return
    }

    try {
      installing.value = true

      await deferredPrompt.value.prompt()

      const choice = await deferredPrompt.value.userChoice

      if (choice.outcome === 'accepted') {
        installed.value = true
        window.localStorage.setItem(installedStorageKey, String(getNow()))
      } else {
        dismissPrompt()
      }

      deferredPrompt.value = null
      installPromptAvailable.value = false
    } catch (err) {
      error.value = err instanceof Error
        ? err.message
        : 'Could not open the install prompt.'
    } finally {
      installing.value = false
    }
  }

  function handleBeforeInstallPrompt(event: Event) {
    event.preventDefault()

    deferredPrompt.value = event as BeforeInstallPromptEvent
    installPromptAvailable.value = true

    console.info('[verto pwa install] beforeinstallprompt captured')
  }

  function handleAppInstalled() {
    installed.value = true
    installPromptAvailable.value = false
    deferredPrompt.value = null

    window.localStorage.setItem(installedStorageKey, String(getNow()))

    console.info('[verto pwa install] app installed')
  }

  onMounted(() => {
    installed.value = Boolean(getStoredNumber(installedStorageKey)) || isRunningStandalone()
    dismissed.value = isRecentlyDismissed()

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
    window.addEventListener('appinstalled', handleAppInstalled)
  })

  onUnmounted(() => {
    window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
    window.removeEventListener('appinstalled', handleAppInstalled)
  })

  return {
    canShowPrompt,
    installPromptAvailable,
    installing,
    installed,
    dismissed,
    error,
    isStandalone,
    isIOS,
    isAndroid,
    isMobileOrTablet,
    install,
    dismissPrompt,
  }
}
