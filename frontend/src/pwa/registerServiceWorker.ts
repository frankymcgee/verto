// VERTO_PWA_STAGE2_REGISTER_SERVICE_WORKER_2026_06_10

import { registerSW } from 'virtual:pwa-register'

let updateServiceWorker: ((reloadPage?: boolean) => Promise<void>) | undefined

export function registerVertoServiceWorker() {
  if (!('serviceWorker' in navigator)) {
    console.info('[verto pwa] Service workers are not supported in this browser.')
    return
  }

  updateServiceWorker = registerSW({
    immediate: true,
    onNeedRefresh() {
      console.info('[verto pwa] New app version available.')
      window.dispatchEvent(new CustomEvent('verto:pwa-update-available'))
    },
    onOfflineReady() {
      console.info('[verto pwa] App shell is ready for offline use.')
      window.dispatchEvent(new CustomEvent('verto:pwa-offline-ready'))
    },
    onRegisteredSW(swUrl, registration) {
      console.info('[verto pwa] Service worker registered:', swUrl)

      if (registration) {
        window.dispatchEvent(new CustomEvent('verto:pwa-registered', {
          detail: {
            swUrl,
          },
        }))
      }
    },
    onRegisterError(error) {
      console.error('[verto pwa] Service worker registration failed:', error)
    },
  })
}

export async function updateVertoServiceWorkerAndReload() {
  if (!updateServiceWorker) {
    window.location.reload()
    return
  }

  await updateServiceWorker(true)
}
