// VERTO_PWA_REGISTER_RAVEN_STYLE_STAGE_1_2026_06_10
import { registerSW } from 'virtual:pwa-register'

let registered = false

export function registerVertoServiceWorker() {
  if (registered) {
    return
  }

  if (typeof window === 'undefined') {
    return
  }

  if (!('serviceWorker' in navigator)) {
    console.info('[verto pwa] service workers are not supported in this browser')
    return
  }

  registered = true

  const updateSW = registerSW({
    immediate: true,
    onNeedRefresh() {
      console.info('[verto pwa] app update available')
      updateSW(true)
    },
    onOfflineReady() {
      console.info('[verto pwa] app shell is ready for offline use')
    },
    onRegisteredSW(swUrl, registration) {
      console.info('[verto pwa] service worker registered', {
        swUrl,
        scope: registration?.scope,
      })
    },
    onRegisterError(error) {
      console.error('[verto pwa] service worker registration failed', error)
    },
  })
}
