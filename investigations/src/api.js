function serverError(data, fallback) {
  try {
    const messages = JSON.parse(data._server_messages || '[]').map((item) => {
      const parsed = typeof item === 'string' ? JSON.parse(item) : item
      return parsed.message || ''
    })
    if (messages.length) return messages.join('\n').replace(/<[^>]*>/g, ' ')
  } catch {
    /* The response need not contain Frappe messages. */
  }
  return fallback
}

export async function call(method, params = {}, signal) {
  const response = await fetch(`/api/method/verto.api.investigations.${method}`, {
    method: 'POST',
    credentials: 'same-origin',
    cache: 'no-store',
    signal,
    headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': window.csrf_token || '' },
    body: JSON.stringify(params),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok || data.exc)
    throw new Error(
      serverError(
        data,
        response.status === 403
          ? 'Your session or permissions do not allow this action. Sign in again if your session expired.'
          : 'The request could not be completed. Please try again.',
      ),
    )
  return data.message
}

export async function uploadFile(file, investigation) {
  const form = new FormData()
  form.append('file', file)
  form.append('is_private', '1')
  form.append('doctype', 'Verto Investigation')
  form.append('docname', investigation)
  const response = await fetch('/api/method/upload_file', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'X-Frappe-CSRF-Token': window.csrf_token || '' },
    body: form,
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok || !data.message?.file_url)
    throw new Error(serverError(data, 'The evidence file could not be uploaded.'))
  return data.message.file_url
}
