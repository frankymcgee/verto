// VERTO_PWA_ICON_HEAD_OVERRIDE_FIX_2026_06_11

import type { Router } from 'vue-router'

const PWA_TITLE = 'MSS'
const PWA_DESCRIPTION = 'PWA Companion app for Mine Site Support'

const MANIFEST_HREF = '/assets/verto/verto-mobile/manifest.webmanifest'
const APPLE_TOUCH_ICON_180 = '/assets/verto/manifest/apple-touch-icon.png'
const PWA_ICON_192 = '/assets/verto/manifest/mss-pwa-192.png'
const PWA_ICON_512 = '/assets/verto/manifest/mss-pwa-512.png'
const PWA_MASKABLE_ICON_512 = '/assets/verto/manifest/mss-pwa-maskable-512.png'

let titleObserver: MutationObserver | null = null
let routerHookInstalled = false

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

function addLink(
  rel: string,
  href: string,
  attributes: Record<string, string> = {}
) {
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
  // Frappe/ERPNext may inject favicon and apple-touch-icon tags before the Verto app starts.
  // iOS will often use the first apple-touch-icon it finds, so remove old ones before adding ours.
  removeLinks('link[rel="manifest"]')
  removeLinks('link[rel="apple-touch-icon"]')
  removeLinks('link[rel="apple-touch-icon-precomposed"]')
  removeLinks('link[rel="icon"]')
  removeLinks('link[rel="shortcut icon"]')
  removeLinks('link[rel="mask-icon"]')

  addLink('manifest', MANIFEST_HREF)

  // iOS Add to Home Screen icons. Put these before normal favicon links.
  addLink('apple-touch-icon', APPLE_TOUCH_ICON_180, {
    sizes: '180x180',
    type: 'image/png',
  })

  addLink('apple-touch-icon', PWA_ICON_192, {
    sizes: '192x192',
    type: 'image/png',
  })

  addLink('apple-touch-icon', PWA_ICON_512, {
    sizes: '512x512',
    type: 'image/png',
  })

  // Normal browser icons. Keep these aligned with the PWA icon so the UI does not fall back to Frappe's favicon.
  addLink('icon', PWA_ICON_192, {
    sizes: '192x192',
    type: 'image/png',
  })

  addLink('icon', PWA_ICON_512, {
    sizes: '512x512',
    type: 'image/png',
  })

  addLink('mask-icon', PWA_MASKABLE_ICON_512, {
    color: '#171717',
  })
}

function applyStaticPwaTags() {
  upsertMeta('description', PWA_DESCRIPTION)
  upsertMeta('theme-color', '#171717')
  upsertMeta('background-color', '#171717')

  // iOS Add to Home Screen metadata.
  upsertMeta('apple-mobile-web-app-capable', 'yes')
  upsertMeta('mobile-web-app-capable', 'yes')
  upsertMeta('apple-mobile-web-app-title', PWA_TITLE)
  upsertMeta('apple-mobile-web-app-status-bar-style', 'black-translucent')
  upsertMeta('apple-touch-fullscreen', 'yes')

  replacePwaLinks()
}

function forcePwaTitle() {
  if (document.title !== PWA_TITLE) {
    document.title = PWA_TITLE
  }

  const titleElement = document.head.querySelector('title')

  if (titleElement && titleElement.textContent !== PWA_TITLE) {
    titleElement.textContent = PWA_TITLE
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
      forcePwaTitle()
      applyStaticPwaTags()
    })
  })
}

export function applyVertoPwaHeadTags(router?: Router) {
  applyStaticPwaTags()
  forcePwaTitle()
  installTitleObserver()
  installRouterTitleEnforcer(router)

  // Frappe/Vue title/icon utilities may run after mount or after route-ready.
  // Re-apply a few times so the final metadata iOS sees is the MSS PWA metadata.
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
  }, 1000)

  window.setTimeout(() => {
    applyStaticPwaTags()
    forcePwaTitle()
  }, 3000)

  console.info('[verto pwa] head tags/icon/title overridden', {
    title: document.title,
    manifest: document.querySelector<HTMLLinkElement>('link[rel="manifest"]')?.href,
    appleTouchIcons: Array.from(
      document.querySelectorAll<HTMLLinkElement>('link[rel="apple-touch-icon"]')
    ).map((element) => element.href),
    favicons: Array.from(
      document.querySelectorAll<HTMLLinkElement>('link[rel="icon"], link[rel="shortcut icon"]')
    ).map((element) => element.href),
    appleMobileTitle: document.querySelector<HTMLMetaElement>('meta[name="apple-mobile-web-app-title"]')?.content,
  })
}

export function stopVertoPwaTitleObserver() {
  titleObserver?.disconnect()
  titleObserver = null
}
