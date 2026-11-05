const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])

export function getCsrfToken() {
  return String(
    window.frappe?.csrf_token ||
    window.csrf_token ||
    ''
  ).trim()
}

export function withCsrfHeaders(
  headers: HeadersInit | undefined,
  method = 'GET'
) {
  const requestHeaders = new Headers(headers)

  if (!SAFE_METHODS.has(method.toUpperCase())) {
    const csrfToken = getCsrfToken()

    if (csrfToken) {
      requestHeaders.set('X-Frappe-CSRF-Token', csrfToken)
    }
  }

  return requestHeaders
}
