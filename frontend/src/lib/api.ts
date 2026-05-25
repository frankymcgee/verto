function getRedirectPath() {
  const path = window.location.pathname + window.location.search + window.location.hash
  return path || '/verto-mobile/'
}

export function redirectToLogin() {
  const redirectTo = getRedirectPath()
  window.location.href = `/login?redirect-to=${encodeURIComponent(redirectTo)}`
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

  const data = await response.json().catch(() => null)

  if (response.status === 401 || response.status === 403) {
    redirectToLogin()
    throw new Error('Login required')
  }

  if (!response.ok) {
    throw new Error(
      data?._server_messages ||
      data?.exception ||
      data?.exc ||
      data?.message ||
      `Request failed with status ${response.status}`
    )
  }

  return data
}