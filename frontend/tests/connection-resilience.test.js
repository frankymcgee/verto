// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { IDBFactory, IDBKeyRange } from 'fake-indexeddb'
import { Blob, File } from 'node:buffer'

vi.mock('../src/lib/diagnostics', () => ({ reportClientError: vi.fn() }))
vi.mock('../src/lib/csrf', () => ({ withCsrfHeaders: headers => new Headers(headers) }))
const actor = 'worker@example.test'
const json = message => new Response(JSON.stringify({ message }))
let connection, queue, apiRequest

beforeEach(async () => {
  vi.resetModules()
  const storage = new Map([['verto:offline-actor', actor]])
  vi.stubGlobal('window', Object.assign(new EventTarget(), {
    location: { origin: 'https://example.test', href: 'https://example.test/verto-mobile/new/field-interaction',
      pathname: '/verto-mobile/new/field-interaction', search: '', hash: '' },
    localStorage: { getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value) },
  }))
  vi.stubGlobal('indexedDB', new IDBFactory())
  vi.stubGlobal('IDBKeyRange', IDBKeyRange)
  vi.stubGlobal('Blob', Blob)
  vi.stubGlobal('File', File)
  vi.stubGlobal('fetch', vi.fn())
  Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
  connection = await import('../src/lib/connection')
  queue = await import('../src/pwa/offlineQueue')
  ;({ apiRequest } = await import('../src/lib/api'))
})
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })

describe('Weak signals and captive Wi-Fi', () => {
  it('keeps live safety checks unavailable when a portal blocks the server', async () => {
    fetch.mockResolvedValueOnce(new Response('<html>Wi-Fi login</html>', { headers: { 'Content-Type': 'text/html' } }))
    await expect(apiRequest('/api/method/verto.api.mobile.voice_jha_workpack.check_jha_revision', { cache: 'no-store' }))
      .rejects.toThrow('current status could not be checked')
  })

  it.each([200, 401, 403, 502])('preserves cached forms when a Wi-Fi login page replaces an API response (HTTP %s)', async status => {
    const url = '/api/method/verto.api.mobile.documents.get_form_schema?mobile_doctype=field-interaction'
    const schema = { message: { title: 'Field interaction', fields: [{ fieldname: 'notes', fieldtype: 'Data' }] } }
    await queue.cacheApiResponse(`request:GET:${url}:`, schema, 'form-schema')
    fetch.mockResolvedValueOnce(new Response('<html>Wi-Fi login: complete your connection</html>', {
      status, headers: { 'Content-Type': 'text/html' },
    }))
    expect(await apiRequest(url)).toEqual(schema)
    expect(connection.serverReachable.value).toBe(false)
    expect(window.location.href).toContain('/verto-mobile/new/')
    expect(await queue.getCachedApiResponse(`request:GET:${url}:`)).toEqual(schema)
    // Further cached reads remain instant while the portal is still blocking access.
    expect(await apiRequest(url)).toEqual(schema)
    expect(fetch).toHaveBeenCalledOnce()
  })

  it('rejects a portal redirect without following it or replacing the current form', async () => {
    fetch.mockResolvedValueOnce(new Response('', { status: 302, headers: { Location: 'https://wifi.example.test/login' } }))
    await expect(apiRequest('/api/method/verto.api.mobile.documents.get_prefill_values?project=PROJECT-1'))
      .resolves.toMatchObject({ message: { values: { project: 'PROJECT-1' }, offline_cached: true } })
    expect(fetch.mock.calls[0][1].redirect).toBe('manual')
    expect(window.location.href).toContain('/verto-mobile/new/')
  })

  it('saves a form and its photos locally when actor verification meets a captive portal, then syncs the same operation', async () => {
    const payload = new FormData()
    payload.append('mobile_doctype', 'field-interaction')
    payload.append('operation_id', 'stable-operation')
    payload.append('values', JSON.stringify({ notes: 'Keep these notes' }))
    payload.append('attachments', new File(['photo evidence'], 'site.jpg'))
    fetch.mockResolvedValueOnce(new Response('<html>Wi-Fi login</html>', { headers: { 'Content-Type': 'text/html' } }))
    const saved = await apiRequest('/api/method/verto.api.mobile.documents.create_mobile_doc', { method: 'POST', body: payload })
    expect(saved.message.offline_operation_id).toBe('stable-operation')
    const queued = await queue.getOfflineQueueItem('stable-operation')
    expect(queued).toMatchObject({ status: 'queued', values: { notes: 'Keep these notes', __verto_offline_user: actor } })
    expect(await queued.attachments[0].blob.text()).toBe('photo evidence')
    expect(fetch).toHaveBeenCalledOnce()
    fetch.mockImplementation(async url => url.endsWith('frappe.ping') ? json('pong')
      : json({ ok: true, result: { doctype: 'Field Interaction', name: 'FORM-1' } }))
    expect(await connection.checkServerConnection(true)).toBe(true)
    await queue.syncOfflineQueue(actor)
    expect((await queue.getOfflineQueueItem('stable-operation')).status).toBe('synced')
    const writes = fetch.mock.calls.filter(([url]) => url.endsWith('sync_action'))
    expect(writes).toHaveLength(1)
    expect(writes[0][1].body.get('operation_id')).toBe('stable-operation')
  })

  it('bounds stalled response bodies and coalesces probes while backing off between failed checks', async () => {
    vi.useFakeTimers()
    fetch.mockImplementationOnce((_url, { signal }) => Promise.resolve({
      status: 200, ok: true,
      text: () => new Promise((_resolve, reject) => {
        signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
      }),
    }))
    const first = connection.checkServerConnection()
    expect(connection.checkServerConnection()).toBe(first)
    await vi.advanceTimersByTimeAsync(8000)
    expect(await first).toBe(false)
    expect(await connection.checkServerConnection()).toBe(false)
    expect(fetch).toHaveBeenCalledOnce()
    await vi.advanceTimersByTimeAsync(5000)
    fetch.mockResolvedValueOnce(json('pong'))
    expect(await connection.checkServerConnection()).toBe(true)
    expect(connection.serverReachable.value).toBe(true)
  })

  it('aborts an active upload as soon as the radio disconnects and retains its payload and photos', async () => {
    const item = await queue.queueMobileDocumentAction({ operationId: 'radio-drop', actionType: 'create',
      mobileDoctype: 'field-interaction', values: { notes: 'Keep me', __verto_offline_user: actor },
      attachments: [queue.makeOfflineAttachment(new Blob(['evidence']), 'photo.jpg')],
    })
    let started
    const ready = new Promise(resolve => { started = resolve })
    fetch.mockImplementationOnce((_url, { signal }) => {
      started()
      return new Promise((_resolve, reject) => signal.addEventListener('abort', () => reject(new DOMException('Offline', 'AbortError'))))
    })
    const upload = queue.syncOfflineQueueItem(item.id)
    const rejected = expect(upload).rejects.toThrow('Connection interrupted')
    await ready
    window.dispatchEvent(new Event('offline'))
    await rejected
    expect(await queue.getOfflineQueueItem(item.id)).toMatchObject({ status: 'queued', values: { notes: 'Keep me' }, attachments: [{ id: item.attachments[0].id }] })
  })
})
