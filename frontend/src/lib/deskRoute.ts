/** Resolve links stored by earlier Verto versions to the current site's Desk. */
export function toDeskUrl(value: string, origin = window.location.origin) {
  const raw = String(value || '').trim()
  try {
    const url = new URL(raw, origin)
    if (url.origin !== new URL(origin).origin || !/^\/app(?:\/|$)/.test(url.pathname)) return raw
    url.pathname = url.pathname.replace(/^\/app(?=\/|$)/, '/desk')
    if (raw.startsWith('/app')) return `${url.pathname}${url.search}${url.hash}`
    if (raw.startsWith('//')) return `//${url.host}${url.pathname}${url.search}${url.hash}`
    return url.href
  } catch {
    return raw
  }
}
