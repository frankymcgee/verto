import DOMPurify from 'dompurify'
import { decodeHTML, escapeUTF8 } from 'entities'

// Legacy Raven bodies may contain several encoded layers. Decode strings only;
// callers must sanitize the final formatted HTML before putting it in the DOM.
export function decodeHtmlDeep(value: string) {
  let current = String(value || '')

  for (let index = 0; index < 3; index += 1) {
    const decoded = decodeHTML(current)

    if (decoded === current) {
      break
    }

    current = decoded
  }

  return current
}

export function escapeHtml(value: string) {
  return escapeUTF8(String(value ?? ''))
}

export function isSafeUrl(value?: string) {
  const url = String(value || '').trim()

  return Boolean(
    url &&
      (
        url.startsWith('/') ||
        url.startsWith('#') ||
        /^https?:\/\//i.test(url) ||
        /^mailto:/i.test(url) ||
        /^tel:/i.test(url) ||
        /^data:image\/(png|jpeg|jpg|gif|webp|svg\+xml);base64,/i.test(url)
      )
  )
}

export function sanitiseMessageHtml(value: string) {
  const content = DOMPurify.sanitize(value, {
    ALLOWED_TAGS: [
      'a', 'b', 'blockquote', 'br', 'code', 'del', 'div', 'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'hr', 'i', 'img', 'li', 'ol', 'p', 'pre', 's', 'span', 'strong', 'table', 'tbody', 'td', 'th',
      'thead', 'tr', 'u', 'ul',
    ],
    ALLOWED_ATTR: ['href', 'src', 'alt', 'title', 'width', 'height', 'colspan', 'rowspan', 'start'],
    ALLOW_ARIA_ATTR: false,
    ALLOW_DATA_ATTR: false,
    RETURN_DOM_FRAGMENT: true,
  })

  for (const link of content.querySelectorAll('a')) {
    if (!isSafeUrl(link.getAttribute('href') || undefined)) link.removeAttribute('href')
    link.setAttribute('target', '_blank')
    link.setAttribute('rel', 'noopener noreferrer')
  }

  for (const image of content.querySelectorAll('img')) {
    if (!isSafeUrl(image.getAttribute('src') || undefined)) image.removeAttribute('src')
    image.setAttribute('loading', 'lazy')
  }

  const template = document.createElement('template')
  template.content.append(content)
  return template.innerHTML.trim()
}

