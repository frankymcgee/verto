import DOMPurify from 'dompurify'

// The returned string belongs in a text node (Vue interpolation), never v-html.
export function htmlToPlainText(value: string): string {
  if (!value || typeof DOMPurify.sanitize !== 'function') return ''

  // Parse/sanitize once. Do not decode the resulting text a second time.
  const content = DOMPurify.sanitize(value, {
    ALLOWED_TAGS: ['p', 'div', 'li', 'br'],
    ALLOWED_ATTR: [],
    RETURN_DOM_FRAGMENT: true,
  })
  const parts: string[] = []
  function visit(node: Node) {
    if (node.nodeType === 3) {
      parts.push(node.textContent || '')
      return
    }
    const tag = node.nodeType === 1 ? (node as Element).tagName.toLowerCase() : ''
    if (tag === 'br') {
      parts.push('\n')
      return
    }
    for (const child of Array.from(node.childNodes)) visit(child)
    if (['p', 'div', 'li'].includes(tag)) parts.push('\n')
  }
  visit(content)
  return parts.join('')
    .replace(/\u00a0/g, ' ')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}
