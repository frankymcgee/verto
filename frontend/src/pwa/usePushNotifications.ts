import { computed, readonly, ref } from 'vue'
import { apiRequest } from '../lib/api'
import { isIosDevice, isStandalonePwa } from './displayMode'


type FrappeResponse<T> = {
  message: T
}

type PushConfig = {
  configured: boolean
  public_key: string
  subscription_count: number
}

const initialised = ref(false)
const loading = ref(false)
const enabling = ref(false)
const disabling = ref(false)
const configured = ref(false)
const subscribed = ref(false)
const error = ref('')
const permission = ref<NotificationPermission>('default')
const dismissedForSession = ref(false)

function supportsWebPush() {
  return (
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window
  )
}

function urlBase64ToUint8Array(base64String: string) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding)
    .replace(/-/g, '+')
    .replace(/_/g, '/')
  const rawData = window.atob(base64)

  return Uint8Array.from(rawData, (character) => character.charCodeAt(0))
}

function getDeviceLabel() {
  const userAgent = navigator.userAgent
  const platform = /Android/i.test(userAgent)
    ? 'Android'
    : /iPad|iPhone|iPod/i.test(userAgent)
      ? 'iOS'
      : /Windows/i.test(userAgent)
        ? 'Windows'
        : /Macintosh|Mac OS X/i.test(userAgent)
          ? 'macOS'
          : 'Browser'

  return `${platform} ${isStandalonePwa() ? 'PWA' : 'browser'}`
}

async function getServiceWorkerRegistration() {
  const existing = await navigator.serviceWorker.getRegistration('/verto-mobile')

  if (existing?.active) {
    return existing
  }

  return Promise.race([
    navigator.serviceWorker.ready,
    new Promise<never>((_, reject) => {
      window.setTimeout(() => {
        reject(new Error('The Verto service worker did not become ready.'))
      }, 10000)
    }),
  ])
}

async function saveSubscription(subscription: PushSubscription) {
  const payload = new FormData()

  payload.append('subscription', JSON.stringify(subscription.toJSON()))
  payload.append('device_label', getDeviceLabel())
  payload.append('user_agent', navigator.userAgent)

  await apiRequest<FrappeResponse<{ name: string; enabled: boolean }>>(
    '/api/method/verto.api.mobile.push_notifications.save_push_subscription',
    {
      method: 'POST',
      body: payload,
    }
  )
}

async function initialisePushNotifications(force = false) {
  if ((initialised.value && !force) || loading.value) {
    return
  }

  initialised.value = true
  error.value = ''

  if (!supportsWebPush()) {
    return
  }

  loading.value = true
  permission.value = Notification.permission

  try {
    const response = await apiRequest<FrappeResponse<PushConfig>>(
      '/api/method/verto.api.mobile.push_notifications.get_push_config'
    )

    configured.value = Boolean(response.message?.configured && response.message?.public_key)

    if (!configured.value) {
      return
    }

    const registration = await getServiceWorkerRegistration()
    const existingSubscription = await registration.pushManager.getSubscription()

    subscribed.value = Boolean(existingSubscription)

    if (existingSubscription) {
      // Refresh the server-side ownership on every authenticated app session. This
      // also handles a shared device that has since been signed in as another user.
      await saveSubscription(existingSubscription)
    }
  } catch (caughtError) {
    error.value = caughtError instanceof Error
      ? caughtError.message
      : 'Could not check notification status.'
  } finally {
    loading.value = false
  }
}

async function enablePushNotifications() {
  if (!supportsWebPush() || !configured.value || enabling.value) {
    return false
  }

  enabling.value = true
  error.value = ''

  try {
    permission.value = await Notification.requestPermission()

    if (permission.value !== 'granted') {
      error.value = permission.value === 'denied'
        ? 'Notifications are blocked. Allow them in this app’s site settings.'
        : 'Notification permission was not granted.'
      return false
    }

    const response = await apiRequest<FrappeResponse<PushConfig>>(
      '/api/method/verto.api.mobile.push_notifications.get_push_config'
    )
    const publicKey = String(response.message?.public_key || '').trim()

    if (!publicKey) {
      throw new Error('Web Push has not been configured for this site.')
    }

    const registration = await getServiceWorkerRegistration()
    let subscription = await registration.pushManager.getSubscription()

    if (!subscription) {
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(publicKey),
      })
    }

    await saveSubscription(subscription)

    subscribed.value = true
    dismissedForSession.value = false

    return true
  } catch (caughtError) {
    error.value = caughtError instanceof Error
      ? caughtError.message
      : 'Could not enable notifications.'
    return false
  } finally {
    enabling.value = false
  }
}

async function disablePushNotifications() {
  if (!supportsWebPush() || disabling.value) {
    return false
  }

  disabling.value = true
  error.value = ''

  try {
    const registration = await getServiceWorkerRegistration()
    const subscription = await registration.pushManager.getSubscription()

    if (!subscription) {
      subscribed.value = false
      permission.value = Notification.permission
      return true
    }

    const payload = new FormData()
    payload.append('endpoint', subscription.endpoint)

    await apiRequest<FrappeResponse<{ disabled: boolean }>>(
      '/api/method/verto.api.mobile.push_notifications.disable_push_subscription',
      {
        method: 'POST',
        body: payload,
      }
    )

    await subscription.unsubscribe()

    subscribed.value = false
    permission.value = Notification.permission

    return true
  } catch (caughtError) {
    error.value = caughtError instanceof Error
      ? caughtError.message
      : 'Could not disable notifications.'
    return false
  } finally {
    disabling.value = false
  }
}

function dismissPushPrompt() {
  dismissedForSession.value = true
}

export function usePushNotifications() {
  const supported = computed(() => supportsWebPush())
  const needsIosInstall = computed(() => isIosDevice() && !isStandalonePwa())
  const shouldPrompt = computed(() => {
    if (
      !initialised.value ||
      subscribed.value ||
      dismissedForSession.value
    ) {
      return false
    }

    if (needsIosInstall.value) {
      return true
    }

    return configured.value && supported.value
  })

  return {
    initialised: readonly(initialised),
    loading: readonly(loading),
    enabling: readonly(enabling),
    disabling: readonly(disabling),
    configured: readonly(configured),
    supported,
    subscribed: readonly(subscribed),
    permission: readonly(permission),
    error: readonly(error),
    needsIosInstall,
    shouldPrompt,
    initialisePushNotifications,
    enablePushNotifications,
    disablePushNotifications,
    dismissPushPrompt,
  }
}
