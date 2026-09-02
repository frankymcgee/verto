import { computed, readonly, ref } from 'vue'
import { apiRequest } from './api'

export type MobileBoot = {
  site_name: string
  base_url: string
  csrf_token: string

  app_name: string
  app_icon: string
  app_icon_url: string
  app_logo: string
  app_logo_url: string
  favicon: string
  favicon_url: string

  app_route_base: string
  fallback_home_route: string

  default_workspace: string
  default_chat_channel: string
  peri_bot_name: string
  peri_bot_user: string
  peri_bot_image: string
  peri_bot_image_url: string

  api_method_base: string
  api_resource_base: string

  user: string
  user_fullname: string
  user_image: string
  user_image_url: string
}

type FrappeResponse<T> = {
  message: T
}

const defaultBoot: MobileBoot = {
  site_name: '',
  base_url: window.location.origin,
  csrf_token: '',

  app_name: 'Verto Mobile',
  app_icon: '/assets/verto/images/verto-icon.png',
  app_icon_url: `${window.location.origin}/assets/verto/images/verto-icon.png`,
  app_logo: '',
  app_logo_url: '',
  favicon: '',
  favicon_url: '',

  app_route_base: '/verto-mobile',
  fallback_home_route: '/',

  default_workspace: '',
  default_chat_channel: 'general',
  peri_bot_name: 'P.E.R.I.',
  peri_bot_user: '',
  peri_bot_image: '',
  peri_bot_image_url: '',

  api_method_base: '/api/method',
  api_resource_base: '/api/resource',

  user: '',
  user_fullname: '',
  user_image: '',
  user_image_url: '',
}

const boot = ref<MobileBoot>({ ...defaultBoot })
const loading = ref(false)
const loaded = ref(false)
const error = ref('')

let loadingPromise: Promise<MobileBoot> | null = null

function mergeBoot(payload?: Partial<MobileBoot>) {
  boot.value = {
    ...defaultBoot,
    ...(payload || {}),
  }

  return boot.value
}

async function loadMobileBoot(force = false) {
  if (loaded.value && !force) {
    return boot.value
  }

  if (loadingPromise && !force) {
    return loadingPromise
  }

  loading.value = true
  error.value = ''

  loadingPromise = apiRequest<FrappeResponse<MobileBoot>>(
    '/api/method/verto.api.mobile.boot.get_mobile_boot'
  )
    .then((response) => {
      const merged = mergeBoot(response.message)

      if (merged.csrf_token) {
        window.csrf_token = merged.csrf_token

        if (window.frappe) {
          window.frappe.csrf_token = merged.csrf_token
        }
      }

      loaded.value = true

      return merged
    })
    .catch((err) => {
      if (err instanceof Error && err.message === 'Login required') {
        throw err
      }

      error.value = err instanceof Error
        ? err.message
        : 'Could not load mobile app settings.'

      return boot.value
    })
    .finally(() => {
      loading.value = false
      loadingPromise = null
    })

  return loadingPromise
}

function reloadMobileBoot() {
  loaded.value = false
  return loadMobileBoot(true)
}

function normalisePath(path?: string) {
  if (!path) {
    return ''
  }

  const value = String(path).trim()

  if (!value) {
    return ''
  }

  if (
    value.startsWith('http://') ||
    value.startsWith('https://') ||
    value.startsWith('data:')
  ) {
    return value
  }

  return value.startsWith('/') ? value : `/${value}`
}

function getAbsoluteUrl(path?: string) {
  const value = normalisePath(path)

  if (!value) {
    return ''
  }

  if (value.startsWith('data:')) {
    return value
  }

  if (value.startsWith('http://') || value.startsWith('https://')) {
    try {
      const parsed = new URL(value)

      // Repair legacy boot/settings values that contain the public hostname
      // with an internal Bench port such as :8000.
      if (parsed.hostname === window.location.hostname) {
        return `${window.location.origin}${parsed.pathname}${parsed.search}${parsed.hash}`
      }
    } catch {
      return value
    }

    return value
  }

  return `${window.location.origin}${value}`
}

function getApiMethodUrl(method: string) {
  const cleanMethod = String(method || '').replace(/^\/+/, '')

  return `${boot.value.api_method_base}/${cleanMethod}`
}

function getAppRoute(route?: string) {
  const fallback = boot.value.fallback_home_route || '/'
  const value = normalisePath(route || fallback)

  if (!value) {
    return '/'
  }

  if (value.startsWith('/verto-mobile/')) {
    return value.replace('/verto-mobile', '') || '/'
  }

  return value
}

export function useMobileBoot() {
  return {
    boot: readonly(boot),
    loading: readonly(loading),
    loaded: readonly(loaded),
    error: readonly(error),

    appName: computed(() => boot.value.app_name || defaultBoot.app_name),
    appIcon: computed(() => boot.value.app_icon || defaultBoot.app_icon),
    appIconUrl: computed(() => getAbsoluteUrl(boot.value.app_icon_url || boot.value.app_icon)),
    appLogo: computed(() => boot.value.app_logo),
    appLogoUrl: computed(() => getAbsoluteUrl(boot.value.app_logo_url || boot.value.app_logo)),
    favicon: computed(() => boot.value.favicon || ''),
    faviconUrl: computed(() => getAbsoluteUrl(boot.value.favicon_url || boot.value.favicon)),

    user: computed(() => boot.value.user),
    userFullname: computed(() => boot.value.user_fullname || boot.value.user),
    userImage: computed(() => boot.value.user_image || ''),
    userImageUrl: computed(() => getAbsoluteUrl(boot.value.user_image_url || boot.value.user_image)),

    defaultWorkspace: computed(() => boot.value.default_workspace),
    defaultChatChannel: computed(() => boot.value.default_chat_channel || 'general'),
    periBotName: computed(() => boot.value.peri_bot_name || 'P.E.R.I.'),
    periBotUser: computed(() => boot.value.peri_bot_user),
    periBotImage: computed(() => boot.value.peri_bot_image || ''),
    periBotImageUrl: computed(() => getAbsoluteUrl(boot.value.peri_bot_image_url || boot.value.peri_bot_image)),

    loadMobileBoot,
    reloadMobileBoot,
    getAbsoluteUrl,
    getApiMethodUrl,
    getAppRoute,
  }
}
