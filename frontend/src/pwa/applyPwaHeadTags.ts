// VERTO_PWA_SETTINGS_METADATA_HEAD_TAGS_2026_06_11

import type { Router } from 'vue-router'

type FrappeResponse<T> = {
  message: T
}

type PwaMetadata = {
  app_name?: string
  short_name?: string
  description?: string
  manifest_url?: string
  apple_touch_icon?: string
  icon?: string
  theme_color?: string
  background_color?: string
}

const FALLBACK_TITLE = 'Verto'
const FALLBACK_DESCRIPTION = 'Mobile companion app for Verto'
const FALLBACK_MANIFEST_HREF = '/assets/verto/verto-mobile/manifest.webmanifest'
const FALLBACK_APPLE_TOUCH_ICON = '/assets/verto/manifest/apple-touch-icon.png'
const FALLBACK_ICON = '/assets/verto/manifest/mss-pwa-192.png'
const FALLBACK_MASK_ICON = '/assets/verto/manifest/mss-pwa-maskable-512.png'

let titleObserver: MutationObserver | null = null
let routerHookInstalled = false
let currentMetadata: Required<PwaMetadata> = {
  app_name: FALLBACK_TITLE,
  short_name: FALLBACK_TITLE,
  description: FALLBACK_DESCRIPTION,
  manifest_url: FALLBACK_MANIFEST_HREF,
  apple_touch_icon: FALLBACK_APPLE_TOUCH_ICON,
  icon: FALLBACK_ICON,
  theme_color: '#171717',
  background_color: '#171717',
}

function normalisePathOrUrl(value: string | undefined, fallback: string) {
  const cleaned = String(value || '').trim()

  if (!cleaned) {
    return fallback
  }

  if (cleaned.startsWith('http://') || cleaned.startsWith('https://') || cleaned.startsWith('/')) {
    return cleaned
  }

  return `/${cleaned}`
}

function getPwaTitle() {
  return String(currentMetadata.short_name || currentMetadata.app_name || FALLBACK_TITLE).trim() || FALLBACK_TITLE
}

function upsertMeta(name: string, content: string) {
  let element = document.head.querySelector<HTMLMetaElement>(`meta[name="${name}"]`)

  if (!element) {
    element = document.createElement('meta')
    element.setAttribute('name', name)
    document.head.appendChild(element)
  }

  element.setAttribute('content', content)

  return element
}

function removeLinks(selector: string) {
  document.head
    .querySelectorAll<HTMLLinkElement>(selector)
    .forEach((element) => element.remove())
}

function addLink(rel: string, href: string, attributes: Record<string, string> = {}) {
  const element = document.createElement('link')

  element.setAttribute('rel', rel)
  element.setAttribute('href', href)

  for (const [key, value] of Object.entries(attributes)) {
    element.setAttribute(key, value)
  }

  document.head.appendChild(element)

  return element
}

function replacePwaLinks() {
  const manifestUrl = normalisePathOrUrl(currentMetadata.manifest_url, FALLBACK_MANIFEST_HREF)
  const appleIcon = normalisePathOrUrl(currentMetadata.apple_touch_icon, FALLBACK_APPLE_TOUCH_ICON)
  const icon = normalisePathOrUrl(currentMetadata.icon, FALLBACK_ICON)

  removeLinks('link[rel="manifest"]')
  removeLinks('link[rel="apple-touch-icon"]')
  removeLinks('link[rel="apple-touch-icon-precomposed"]')
  removeLinks('link[rel="icon"]')
  removeLinks('link[rel="shortcut icon"]')
  removeLinks('link[rel="mask-icon"]')

  addLink('manifest', manifestUrl)
  addLink('apple-touch-icon', appleIcon, {
    sizes: '180x180',
    type: 'image/png',
  })
  addLink('apple-touch-icon', icon, {
    sizes: '192x192',
    type: 'image/png',
  })
  addLink('icon', icon, {
    sizes: '192x192',
    type: 'image/png',
  })
  addLink('mask-icon', FALLBACK_MASK_ICON, {
    color: currentMetadata.theme_color || '#171717',
  })
}

function applyStaticPwaTags() {
  const title = getPwaTitle()

  upsertMeta('description', currentMetadata.description || FALLBACK_DESCRIPTION)
  upsertMeta('theme-color', currentMetadata.theme_color || '#171717')
  upsertMeta('background-color', currentMetadata.background_color || '#171717')
  upsertMeta('apple-mobile-web-app-capable', 'yes')
  upsertMeta('mobile-web-app-capable', 'yes')
  upsertMeta('apple-mobile-web-app-title', title)
  upsertMeta('apple-mobile-web-app-status-bar-style', 'black-translucent')
  upsertMeta('apple-touch-fullscreen', 'yes')

  replacePwaLinks()
}

function forcePwaTitle() {
  const title = getPwaTitle()

  if (document.title !== title) {
    document.title = title
  }

  const titleElement = document.head.querySelector('title')

  if (titleElement && titleElement.textContent !== title) {
    titleElement.textContent = title
  }
}

function installTitleObserver() {
  if (titleObserver) {
    return
  }

  let titleElement = document.head.querySelector('title')

  if (!titleElement) {
    titleElement = document.createElement('title')
    document.head.appendChild(titleElement)
  }

  titleObserver = new MutationObserver(() => {
    forcePwaTitle()
  })

  titleObserver.observe(titleElement, {
    childList: true,
    characterData: true,
    subtree: true,
  })
}

function installRouterTitleEnforcer(router?: Router) {
  if (!router || routerHookInstalled) {
    return
  }

  routerHookInstalled = true

  router.afterEach(() => {
    window.requestAnimationFrame(() => {
      applyStaticPwaTags()
      forcePwaTitle()
    })
  })
}

async function loadPwaMetadataFromSettings() {
  try {
    const response = await fetch('/api/method/verto.api.mobile.pwa_manifest.get_pwa_metadata', {
      credentials: 'include',
      headers: {
        Accept: 'application/json',
      },
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const data = await response.json() as FrappeResponse<PwaMetadata>
    const message = data.message || {}

    currentMetadata = {
      app_name: String(message.app_name || FALLBACK_TITLE),
      short_name: String(message.short_name || message.app_name || FALLBACK_TITLE),
      description: String(message.description || FALLBACK_DESCRIPTION),
      manifest_url: normalisePathOrUrl(message.manifest_url, FALLBACK_MANIFEST_HREF),
      apple_touch_icon: normalisePathOrUrl(message.apple_touch_icon, FALLBACK_APPLE_TOUCH_ICON),
      icon: normalisePathOrUrl(message.icon, FALLBACK_ICON),
      theme_color: String(message.theme_color || '#171717'),
      background_color: String(message.background_color || '#171717'),
    }

    applyStaticPwaTags()
    forcePwaTitle()
  } catch (error) {
    console.warn('[verto pwa] could not load PWA metadata from settings', error)
  }
}

export function applyVertoPwaHeadTags(router?: Router) {
  applyStaticPwaTags()
  forcePwaTitle()
  installTitleObserver()
  installRouterTitleEnforcer(router)
  loadPwaMetadataFromSettings()

  window.setTimeout(() => {
    applyStaticPwaTags()
    forcePwaTitle()
  }, 0)

  window.setTimeout(() => {
    applyStaticPwaTags()
    forcePwaTitle()
  }, 250)

  window.setTimeout(() => {
    applyStaticPwaTags()
    forcePwaTitle()
    loadPwaMetadataFromSettings()
  }, 1000)

  window.setTimeout(() => {
    applyStaticPwaTags()
    forcePwaTitle()
  }, 3000)

  console.info('[verto pwa] settings-driven PWA head tags applied', {
    title: document.title,
    manifest: document.querySelector<HTMLLinkElement>('link[rel="manifest"]')?.href,
    appleTouchIcons: Array.from(
      document.querySelectorAll<HTMLLinkElement>('link[rel="apple-touch-icon"]')
    ).map((element) => element.href),
    appleMobileTitle: document.querySelector<HTMLMetaElement>('meta[name="apple-mobile-web-app-title"]')?.content,
  })
}

export function stopVertoPwaTitleObserver() {
  titleObserver?.disconnect()
  titleObserver = null
}
