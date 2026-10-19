export type QrDestination =
  | { kind: 'mobile' | 'file'; url: string }
  | { kind: 'desk'; doctype: string; name: string; revision?: string }

function segment(value: string) {
  const decoded = decodeURIComponent(value)
  if (!decoded || /[\\\u0000-\u001f\u007f]/.test(decoded)) throw new Error('Invalid document link.')
  return decoded
}

/** QR payloads are untrusted. Only document/form routes on this tenant may open. */
export function parseQrLink(value: string, origin = window.location.origin): QrDestination {
  const raw = value.trim()
  if (!raw || raw.length > 8192 || !/^(https?:\/\/|\/)/i.test(raw)) {
    throw new Error('This QR code does not contain a document or form link.')
  }
  const url = new URL(raw, origin)
  if (url.origin !== origin || url.username || url.password) {
    throw new Error('This QR code belongs to another site. Scan a document from this Verto site.')
  }
  const parts = url.pathname.split('/').slice(1).map(part => segment(part))
  if (parts.slice(0, -1).some(part => part.includes('/'))) throw new Error('Invalid document link.')
  if (parts[0] === 'verto-mobile') {
    const path = parts.slice(1)
    const valid = path.length === 1 && path[0] === 'forms'
      || path.length === 2 && path[0] === 'jha'
      || path.length === 2 && path[0] === 'new' && /^[a-z0-9-]+$/.test(path[1])
      || path.length === 3 && path[0] === 'edit' && /^[a-z0-9-]+$/.test(path[1])
    if (valid) return { kind: 'mobile', url: `/${parts.slice(1).map(encodeURIComponent).join('/')}${url.search}` }
  }
  if (parts[0] === 'app' && parts.length === 3) {
    return { kind: 'desk', doctype: parts[1], name: parts[2] }
  }
  if (url.pathname === '/printview') {
    const doctype = url.searchParams.get('doctype'), name = url.searchParams.get('name')
    if (doctype && name) return { kind: 'desk', doctype, name, revision: url.searchParams.get('revision') || undefined }
  }
  if ((parts[0] === 'files' || parts[0] === 'private' && parts[1] === 'files') && /\.pdf$/i.test(url.pathname)) {
    return { kind: 'file', url: `${url.pathname}${url.search}` }
  }
  throw new Error('This QR code is not a supported document or form link.')
}
