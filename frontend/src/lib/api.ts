function getRedirectPath() {
  const path = window.location.pathname + window.location.search + window.location.hash

  if (!path || path === '/') {
    return '/verto-mobile/'
  }

  return path
}

function isLoginRoute() {
  return window.location.pathname === '/login'
}

function getLoginUrl() {
  const redirectTo = getRedirectPath()

  return `/login?redirect-to=${encodeURIComponent(redirectTo)}`
}

function isHtmlLoginResponse(response: Response, text: string) {
  const contentType = response.headers.get('content-type') || ''

  if (!contentType.includes('text/html')) {
    return false
  }

  const loweredText = text.toLowerCase()

  return (
    loweredText.includes('<html') &&
    (
      loweredText.includes('/login') ||
      loweredText.includes('login') ||
      loweredText.includes('frappe')
    )
  )
}

function extractErrorMessage(data: any, fallback: string) {
  if (!data) {
    return fallback
  }

  if (typeof data === 'string') {
    return data
  }

  return (
    data?._server_messages ||
    data?.exception ||
    data?.exc ||
    data?.message ||
    fallback
  )
}

function parseJsonMaybe(text: string) {
  if (!text) {
    return null
  }

  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

function isAuthFailure(response: Response, data: any, rawText: string) {
  if (response.status === 401) {
    return true
  }

  if (isHtmlLoginResponse(response, rawText)) {
    return true
  }

  const message = String(extractErrorMessage(data, '') || '').toLowerCase()

  return (
    response.status === 403 &&
    (
      message.includes('login required') ||
      message.includes('not permitted in guest mode') ||
      message.includes('session expired') ||
      message.includes('session has expired') ||
      message.includes('not logged in') ||
      message.includes('please login') ||
      message.includes('please log in')
    )
  )
}

export function redirectToLogin() {
  if (isLoginRoute()) {
    return
  }

  window.location.href = getLoginUrl()
}

export async function apiRequest<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, {
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  })

  const rawText = await response.text().catch(() => '')
  const data = parseJsonMaybe(rawText)

  if (isAuthFailure(response, data, rawText)) {
    redirectToLogin()
    throw new Error('Login required')
  }

  if (!response.ok) {
    throw new Error(
      extractErrorMessage(data, `Request failed with status ${response.status}`)
    )
  }

  return (data ?? rawText) as T
}
