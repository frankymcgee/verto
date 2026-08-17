// VERTO_APP_BROWSER_DRAWER_2026_06_11

export type AppBrowserRequest = {
  url: string
  title?: string
  replace?: boolean
}

export const APP_BROWSER_OPEN_EVENT = 'verto:app-browser-open'

function getUrl(value: string) {
  return new URL(value, window.location.origin)
}

export function isLoginLikeUrl(value: string) {
  try {
    const url = getUrl(value)
    const path = url.pathname.toLowerCase()

    return (
      path === '/login' ||
      path.startsWith('/login/') ||
      path === '/logout' ||
      path.startsWith('/logout/') ||
      url.searchParams.has('redirect-to') && path === '/login'
    )
  } catch {
    return false
  }
}

export function isVertoMobileUrl(value: string) {
  try {
    const url = getUrl(value)

    return (
      url.origin === window.location.origin &&
      (
        url.pathname === '/verto-mobile' ||
        url.pathname.startsWith('/verto-mobile/')
      )
    )
  } catch {
    return false
  }
}

export function shouldOpenInAppBrowser(value: string) {
  const url = String(value || '').trim()

  if (!url || url === '#') {
    return false
  }

  if (url.startsWith('mailto:') || url.startsWith('tel:') || url.startsWith('sms:')) {
    return false
  }

  if (isLoginLikeUrl(url)) {
    return false
  }

  if (isVertoMobileUrl(url)) {
    return false
  }

  return true
}

export function openAppBrowser(request: AppBrowserRequest | string, fallbackTitle = 'Browser') {
  const payload: AppBrowserRequest = typeof request === 'string'
    ? { url: request, title: fallbackTitle }
    : request

  const url = String(payload.url || '').trim()

  if (!url) {
    return
  }

  if (!shouldOpenInAppBrowser(url)) {
    window.location.href = url
    return
  }

  const event = new CustomEvent<AppBrowserRequest>(APP_BROWSER_OPEN_EVENT, {
    detail: {
      url,
      title: payload.title || fallbackTitle,
      replace: payload.replace,
    },
  })

  window.dispatchEvent(event)
}

export function handleAppBrowserLinkClick(event: MouseEvent) {
  if (event.defaultPrevented) {
    return
  }

  if (event.button !== 0) {
    return
  }

  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
    return
  }

  const target = event.target as HTMLElement | null
  const anchor = target?.closest?.('a[href]') as HTMLAnchorElement | null

  if (!anchor) {
    return
  }

  if (anchor.hasAttribute('download')) {
    return
  }

  const rawHref = anchor.getAttribute('href') || ''

  if (!rawHref || rawHref === '#') {
    return
  }

  if (anchor.target && anchor.target !== '_self') {
    if (!shouldOpenInAppBrowser(rawHref)) {
      return
    }
  }

  if (!shouldOpenInAppBrowser(rawHref)) {
    return
  }

  event.preventDefault()
  openAppBrowser({
    url: rawHref,
    title: anchor.getAttribute('aria-label') || anchor.textContent?.trim() || 'Browser',
  })
}
