// VERTO_PWA_AUTO_UPDATE_AND_PUSH_2026_08_09

const SERVICE_WORKER_URL = '/verto-mobile-sw.js'
const SERVICE_WORKER_SCOPE = '/verto-mobile/'
const UPDATE_CHECK_INTERVAL_MS = 15 * 60 * 1000
const FOREGROUND_UPDATE_THROTTLE_MS = 60 * 1000

let registration: ServiceWorkerRegistration | null = null
let registrationPromise: Promise<ServiceWorkerRegistration | null> | null = null
let updateInterval: number | undefined
let lastUpdateCheck = 0
let reloadStarted = false

function isLocalhost() {
  return ['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname)
}

function canUseServiceWorker() {
  return (
    'serviceWorker' in navigator &&
    (window.location.protocol === 'https:' || isLocalhost())
  )
}

function reloadOnceForNewController() {
  if (reloadStarted) {
    return
  }

  reloadStarted = true
  window.location.reload()
}

async function removeLegacyAssetScopedWorkers() {
  const registrations = await navigator.serviceWorker.getRegistrations()

  await Promise.all(
    registrations
      .filter((item) => {
        return (
          item.scope.includes('/assets/verto/verto-mobile/') &&
          item.scope !== new URL(SERVICE_WORKER_SCOPE, window.location.origin).href
        )
      })
      .map((item) => item.unregister())
  )
}

async function checkForUpdate(force = false) {
  if (!registration) {
    return
  }

  const now = Date.now()

  if (!force && now - lastUpdateCheck < FOREGROUND_UPDATE_THROTTLE_MS) {
    return
  }

  lastUpdateCheck = now

  try {
    await registration.update()
  } catch (error) {
    console.warn('[verto pwa] update check failed', error)
  }
}

function installUpdateChecks() {
  if (updateInterval) {
    window.clearInterval(updateInterval)
  }

  updateInterval = window.setInterval(() => {
    void checkForUpdate(true)
  }, UPDATE_CHECK_INTERVAL_MS)

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      void checkForUpdate()
    }
  })

  window.addEventListener('focus', () => {
    void checkForUpdate()
  })

  window.addEventListener('online', () => {
    void checkForUpdate(true)
  })
}

export function registerVertoServiceWorker() {
  if (registrationPromise) {
    return registrationPromise
  }

  if (!canUseServiceWorker()) {
    console.info('[verto pwa] Service workers are not supported in this context.')
    return Promise.resolve(null)
  }

  const hadControllerAtStartup = Boolean(navigator.serviceWorker.controller)

  navigator.serviceWorker.addEventListener('controllerchange', () => {
    console.info('[verto pwa] service worker controller changed')

    if (hadControllerAtStartup) {
      reloadOnceForNewController()
    }
  })

  registrationPromise = (async () => {
    try {
      await removeLegacyAssetScopedWorkers()

      registration = await navigator.serviceWorker.register(SERVICE_WORKER_URL, {
        scope: SERVICE_WORKER_SCOPE,
        updateViaCache: 'none',
      })

      console.info('[verto pwa] service worker registered', {
        scope: registration.scope,
        script: SERVICE_WORKER_URL,
      })

      registration.addEventListener('updatefound', () => {
        const installingWorker = registration?.installing

        if (!installingWorker) {
          return
        }

        window.dispatchEvent(new CustomEvent('verto:pwa-update-available'))

        installingWorker.addEventListener('statechange', () => {
          console.info('[verto pwa] service worker state', installingWorker.state)
        })
      })

      installUpdateChecks()
      window.setTimeout(() => {
        void checkForUpdate(true)
      }, 1500)

      window.dispatchEvent(new CustomEvent('verto:pwa-registered', {
        detail: {
          swUrl: SERVICE_WORKER_URL,
          scope: registration.scope,
        },
      }))

      return registration
    } catch (error) {
      console.error('[verto pwa] service worker registration failed', error)
      return null
    }
  })()

  return registrationPromise
}

function activateWaitingWorker(currentRegistration: ServiceWorkerRegistration) {
  const waitingWorker = currentRegistration.waiting

  if (!waitingWorker) {
    return false
  }

  waitingWorker.postMessage({ type: 'SKIP_WAITING' })
  return true
}

export async function updateVertoServiceWorkerAndReload() {
  const currentRegistration = registration || await registerVertoServiceWorker()

  if (!currentRegistration) {
    window.location.reload()
    return
  }

  if (activateWaitingWorker(currentRegistration)) {
    return
  }

  await checkForUpdate(true)
  activateWaitingWorker(currentRegistration)
}
