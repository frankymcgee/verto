// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { IDBFactory, IDBKeyRange } from 'fake-indexeddb'
import { Blob, File } from 'node:buffer'

vi.mock('../src/lib/diagnostics', () => ({ reportClientError: vi.fn() }))
vi.mock('../src/lib/csrf', () => ({ withCsrfHeaders: (headers) => new Headers(headers) }))

const actor = 'worker@example.test'
const result = { doctype: 'Daily Timesheet', name: 'TS-1', route: '/shifts' }
const response = (value = { ok: true, result }) => new Response(JSON.stringify({ message: value }))
const deferred = () => {
  let resolve
  const promise = new Promise(done => { resolve = done })
  return { promise, resolve }
}
const input = (overrides = {}) => ({
  operationId: 'document-stable', actionType: 'create', mobileDoctype: 'daily-timesheet',
  values: { date: '2026-11-05', shift_allocation: 'SHIFT-1', __verto_offline_user: actor },
  ...overrides,
})
let queue
beforeEach(async () => {
  vi.resetModules()
  const storage = new Map()
  vi.stubGlobal('window', Object.assign(new EventTarget(), {
    location: new URL('https://example.test/verto-mobile/'),
    localStorage: {
      getItem: key => storage.get(key) || null,
      setItem: (key, value) => storage.set(key, String(value)),
      clear: () => storage.clear(),
    },
  }))
  vi.stubGlobal('indexedDB', new IDBFactory())
  vi.stubGlobal('IDBKeyRange', IDBKeyRange)
  vi.stubGlobal('Blob', Blob)
  vi.stubGlobal('File', File)
  vi.stubGlobal('fetch', vi.fn(async () => response()))
  Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
  Object.defineProperty(navigator, 'locks', { configurable: true, value: undefined })
  window.localStorage.setItem('verto:offline-actor', actor)
  queue = await import('../src/pwa/offlineQueue')
})
afterEach(() => { vi.unstubAllGlobals() })

describe('Durable mobile submission retries', () => {
  it('atomically reuses a form ID and its original attachment IDs', async () => {
    const attachment = queue.makeOfflineAttachment(new Blob(['photo']), 'photo.jpg')
    const [first, second] = await Promise.all([
      queue.queueMobileDocumentAction(input({ attachments: [attachment] })),
      queue.queueMobileDocumentAction(input({ attachments: [queue.makeOfflineAttachment(new Blob(['photo']), 'photo.jpg')] })),
    ])
    expect(first.attachments[0].id).toBe(second.attachments[0].id)
    expect(await queue.getOfflineQueueItems()).toHaveLength(1)
  })

  it('shares one upload between immediate submission, auto-sync and manual sync', async () => {
    await queue.queueMobileDocumentAction(input())
    const pending = deferred()
    fetch.mockReturnValueOnce(pending.promise)
    const direct = queue.syncOfflineQueueItem('document-stable')
    const repeat = queue.syncOfflineQueueItem('document-stable')
    expect(repeat).toBe(direct)
    const automatic = queue.syncOfflineQueue()
    expect(queue.syncOfflineQueue()).toBe(automatic)
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledOnce())
    pending.resolve(response())
    await Promise.all([direct, repeat, automatic])
    expect(fetch).toHaveBeenCalledOnce()
    expect(await queue.getOfflineQueueSummary()).toMatchObject({ total: 0 })
  })

  it('prevents a second window from replaying a live item without Web Locks', async () => {
    await queue.queueMobileDocumentAction(input())
    const pending = deferred()
    fetch.mockReturnValueOnce(pending.promise)
    const first = queue.syncOfflineQueueItem('document-stable')
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledOnce())
    vi.resetModules()
    const otherWindow = await import('../src/pwa/offlineQueue')
    await expect(otherWindow.syncOfflineQueueItem('document-stable')).rejects.toThrow('already syncing')
    expect(fetch).toHaveBeenCalledOnce()
    pending.resolve(response())
    await first
  })

  it('uses a browser lock when available and recovers an expired syncing item', async () => {
    const item = await queue.queueMobileDocumentAction(input())
    await queue.updateOfflineQueueItem({ ...item, status: 'syncing', sync_owner: 'closed-window', sync_expires_at: Date.now() - 1 })
    const lock = vi.fn(async (_name, run) => run())
    Object.defineProperty(navigator, 'locks', { configurable: true, value: { request: lock } })
    await queue.syncOfflineQueueItem(item.id)
    expect(lock).toHaveBeenCalledWith(`verto:offline-sync:${item.id}`, expect.any(Function))
    expect(fetch).toHaveBeenCalledOnce()
  })

  it('returns the completed result when the same form is submitted again', async () => {
    await queue.queueMobileDocumentAction(input())
    await queue.syncOfflineQueueItem('document-stable')
    expect((await queue.queueMobileDocumentAction(input())).status).toBe('synced')
    expect(await queue.syncOfflineQueueItem('document-stable')).toEqual(result)
    expect(fetch).toHaveBeenCalledOnce()
  })

  it('keeps the operation ID after the server accepts a write but its response is lost', async () => {
    await queue.queueMobileDocumentAction(input())
    fetch.mockRejectedValueOnce(new TypeError('Network failure'))
    await expect(queue.syncOfflineQueueItem('document-stable', { deleteOnPermanentFailure: true })).rejects.toThrow('Network')
    expect((await queue.getOfflineQueueItem('document-stable')).status).toBe('failed')
    await queue.syncOfflineQueueItem('document-stable')
    expect(fetch.mock.calls.map(([, options]) => options.body.get('operation_id'))).toEqual(['document-stable', 'document-stable'])
  })

  it('retains an ambiguous HTTP 200 response for a safe retry', async () => {
    await queue.queueMobileDocumentAction(input())
    fetch.mockResolvedValueOnce(new Response('<html>Proxy error</html>'))
    await expect(queue.syncOfflineQueueItem('document-stable', { deleteOnPermanentFailure: true })).rejects.toThrow('could not be confirmed')
    expect((await queue.getOfflineQueueItem('document-stable')).status).toBe('failed')
  })

  it('resumes photos after failure without saving the document again or dropping files', async () => {
    const attachment = queue.makeOfflineAttachment(new Blob(['photo']), 'photo.jpg')
    await queue.queueMobileDocumentAction(input({ attachments: [attachment] }))
    fetch.mockResolvedValueOnce(response()).mockResolvedValueOnce(new Response('Permission denied', { status: 403 }))
    await expect(queue.syncOfflineQueueItem('document-stable', { deleteOnPermanentFailure: true })).rejects.toThrow()
    const retained = await queue.getOfflineQueueItem('document-stable')
    expect(retained.server_result).toEqual(result)
    expect(retained.attachments[0].blob.size).toBe(5)
    await queue.syncOfflineQueueItem('document-stable')
    expect(fetch.mock.calls.filter(([url]) => url.endsWith('sync_action'))).toHaveLength(1)
    const uploads = fetch.mock.calls.filter(([url]) => url.endsWith('upload_attachment'))
    expect(uploads.map(([, options]) => options.body.get('attachment_id'))).toEqual([attachment.id, attachment.id])
    expect((await queue.getOfflineQueueItem('document-stable')).attachments).toEqual([])
  })

  it('does not re-upload an acknowledged photo when a later photo fails', async () => {
    const attachments = ['one.jpg', 'two.jpg'].map(name => queue.makeOfflineAttachment(new Blob([name]), name))
    await queue.queueMobileDocumentAction(input({ attachments }))
    fetch.mockResolvedValueOnce(response()).mockResolvedValueOnce(response())
      .mockRejectedValueOnce(new TypeError('Network failure'))
    await expect(queue.syncOfflineQueueItem('document-stable')).rejects.toThrow('Network')
    await queue.syncOfflineQueueItem('document-stable')
    const uploads = fetch.mock.calls.filter(([url]) => url.endsWith('upload_attachment'))
    expect(uploads.map(([, options]) => options.body.get('attachment_id')))
      .toEqual([attachments[0].id, attachments[1].id, attachments[1].id])
  })

  it('does not reuse a submission for a different person or silently discard changed hours', async () => {
    await queue.queueMobileDocumentAction(input())
    await expect(queue.queueMobileDocumentAction(input({ values: { __verto_offline_user: 'other' } }))).rejects.toThrow('another document or signed-in user')
    await expect(queue.queueMobileDocumentAction(input({ values: { ...input().values, duration: 3600 } }))).rejects.toThrow('make changes')
  })

  it('keeps permanent pre-save validation errors out of the retry queue', async () => {
    await queue.queueMobileDocumentAction(input())
    fetch.mockResolvedValueOnce(new Response(JSON.stringify({ exception: 'Duplicate timesheet' }), { status: 417 }))
    await expect(queue.syncOfflineQueueItem('document-stable', { deleteOnPermanentFailure: true })).rejects.toThrow('Duplicate timesheet')
    expect(await queue.getOfflineQueueItem('document-stable')).toBeUndefined()
  })

  it('allows corrected values after a background attempt failed validation before saving', async () => {
    await queue.queueMobileDocumentAction(input())
    fetch.mockResolvedValueOnce(new Response(JSON.stringify({ exception: 'Invalid hours' }), { status: 417 }))
    await expect(queue.syncOfflineQueueItem('document-stable')).rejects.toThrow('Invalid hours')
    const corrected = await queue.queueMobileDocumentAction(input({ values: { ...input().values, duration: 3600 } }))
    expect(corrected.values.duration).toBe(3600)
    expect(corrected.status).toBe('queued')
    expect(corrected.id).toBe('document-stable')
  })
})

describe('Discarding failed uploads', () => {
  it('removes only the selected failed upload and its photos, preserving cached data and other work', async () => {
    const attachment = queue.makeOfflineAttachment(new Blob(['evidence']), 'photo.jpg')
    const failed = await queue.queueMobileDocumentAction(input({ attachments: [attachment] }))
    await queue.updateOfflineQueueItem({ ...failed, status: 'failed', server_result: result })
    await queue.queueMobileDocumentAction(input({ operationId: 'keep-queued' }))
    await queue.updateOfflineQueueItem({ ...failed, id: 'keep-failed', status: 'failed' })
    await queue.updateOfflineQueueItem({ ...failed, id: 'keep-synced', status: 'synced', attachments: [] })
    await queue.cacheApiResponse('offline-test', { ready: true })
    const updated = vi.fn()
    window.addEventListener('verto:offline-queue-updated', updated)

    await queue.discardFailedOfflineQueueItem(failed.id, actor)

    expect(await queue.getOfflineQueueItem(failed.id)).toBeUndefined()
    expect((await queue.getOfflineQueueItems()).map(item => item.id).sort()).toEqual(['keep-failed', 'keep-queued', 'keep-synced'])
    expect(await queue.getCachedApiResponse('offline-test')).toEqual({ ready: true })
    expect(await queue.getOfflineQueueSummary()).toMatchObject({ queued: 1, failed: 1, total: 2 })
    expect(updated).toHaveBeenCalledOnce()
    expect(fetch).not.toHaveBeenCalled()
  })

  it.each(['queued', 'syncing', 'synced'])('preserves an upload that changed to %s before confirmation', async status => {
    const item = await queue.queueMobileDocumentAction(input())
    await queue.updateOfflineQueueItem({ ...item, status })
    await expect(queue.discardFailedOfflineQueueItem(item.id, actor)).rejects.toThrow('no longer failed')
    expect((await queue.getOfflineQueueItem(item.id)).status).toBe(status)
  })

  it('does not remove or resurrect an upload during an active retry in another window', async () => {
    const item = await queue.queueMobileDocumentAction(input())
    await queue.updateOfflineQueueItem({ ...item, status: 'failed' })
    const pending = deferred()
    fetch.mockReturnValueOnce(pending.promise)
    const uploading = queue.syncOfflineQueueItem(item.id)
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledOnce())
    vi.resetModules()
    const otherWindow = await import('../src/pwa/offlineQueue')
    await expect(otherWindow.discardFailedOfflineQueueItem(item.id, actor)).rejects.toThrow('syncing')
    pending.resolve(response())
    await uploading
    expect((await queue.getOfflineQueueItem(item.id)).status).toBe('synced')
  })

  it('prevents a previously listed item from uploading after it was discarded', async () => {
    const item = await queue.queueMobileDocumentAction(input())
    await queue.updateOfflineQueueItem({ ...item, status: 'failed' })
    await queue.discardFailedOfflineQueueItem(item.id, actor)
    await expect(queue.syncOfflineQueueItem(item.id)).rejects.toThrow('could not be found')
    expect(fetch).not.toHaveBeenCalled()
    expect(await queue.getOfflineQueueItem(item.id)).toBeUndefined()
  })

  it('protects an unexpired upload lease even if a stale record still says failed', async () => {
    const item = await queue.queueMobileDocumentAction(input())
    await queue.updateOfflineQueueItem({ ...item, status: 'failed', sync_owner: 'other-window', sync_expires_at: Date.now() + 120000 })
    await expect(queue.discardFailedOfflineQueueItem(item.id, actor)).rejects.toThrow('syncing')
    expect(await queue.getOfflineQueueItem(item.id)).toBeDefined()
  })

  it('allows old unidentified failures to be removed without requiring a working server connection', async () => {
    const item = await queue.addOfflineQueueItem({ type: 'old form', url: '/api/method/old', body: {} })
    await queue.updateOfflineQueueItem({ ...item, status: 'failed' })
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: false })
    await queue.discardFailedOfflineQueueItem(item.id, actor)
    expect(await queue.getOfflineQueueItem(item.id)).toBeUndefined()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('hides another account’s failures and refuses to discard them', async () => {
    const item = await queue.queueMobileDocumentAction(input())
    await queue.updateOfflineQueueItem({ ...item, status: 'failed' })
    expect(await queue.getFailedOfflineQueueItems('other@example.test')).toEqual([])
    expect(await queue.getFailedOfflineQueueItems('Guest')).toEqual([])
    await expect(queue.discardFailedOfflineQueueItem(item.id, 'other@example.test')).rejects.toThrow('another signed-in user')
    expect(await queue.getFailedOfflineQueueItems(actor)).toHaveLength(1)
    expect((await queue.getOfflineQueueItem(item.id)).status).toBe('failed')
  })
})

describe('Form and photo queue handoff', () => {
  it.each(['create', 'update'])('persists all photos before exposing an offline %s action', async action => {
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: false })
    const payload = new FormData()
    payload.append('mobile_doctype', 'daily-timesheet')
    payload.append('operation_id', 'form-operation')
    payload.append('values', JSON.stringify({ date: '2026-11-05' }))
    if (action === 'update') payload.append('docname', 'TS-1')
    payload.append('attachments', new File(['evidence'], 'photo.jpg', { type: 'image/jpeg' }))
    const { apiRequest } = await import('../src/lib/api')
    const saved = await apiRequest(`/api/method/verto.api.mobile.documents.${action}_mobile_doc`, { method: 'POST', body: payload })
    const item = await queue.getOfflineQueueItem('form-operation')
    expect(saved.message.offline_operation_id).toBe('form-operation')
    expect(item.attachments).toHaveLength(1)
    expect(await item.attachments[0].blob.text()).toBe('evidence')
    expect(item.values.__verto_offline_user).toBe(actor)
    expect(fetch).not.toHaveBeenCalled()
  })

  it('returns a pending upload once the document saved, even if a photo is rejected', async () => {
    const payload = new FormData()
    payload.append('mobile_doctype', 'daily-timesheet')
    payload.append('operation_id', 'form-operation')
    payload.append('values', JSON.stringify({ date: '2026-11-05' }))
    payload.append('attachments', new File(['evidence'], 'photo.jpg'))
    fetch.mockResolvedValueOnce(response(actor)).mockResolvedValueOnce(response())
      .mockResolvedValueOnce(new Response('Rejected upload', { status: 403 }))
    const { apiRequest } = await import('../src/lib/api')
    const saved = await apiRequest('/api/method/verto.api.mobile.documents.create_mobile_doc', { method: 'POST', body: payload })
    expect(saved.message).toMatchObject({ offline_queued: true, offline_operation_id: 'form-operation' })
    expect((await queue.getOfflineQueueItem('form-operation')).server_result).toEqual(result)
  })
})

describe('Timesheet visibility while a connection returns', () => {
  it('merges pending hours into the online calendar and hides other accounts', async () => {
    await queue.queueMobileDocumentAction(input())
    await queue.queueMobileDocumentAction(input({ operationId: 'other-account', values: { ...input().values, __verto_offline_user: 'other' } }))
    fetch.mockResolvedValueOnce(response({ user: actor, timesheets: [], shifts: [] }))
    const { apiRequest } = await import('../src/lib/api')
    const calendar = await apiRequest('/api/method/verto.api.mobile.shifts.get_shift_calendar?start_date=2026-11-01&end_date=2026-11-30')
    expect(calendar.message.timesheets).toHaveLength(1)
    expect(calendar.message.timesheets[0]).toMatchObject({ name: 'document-stable', offline_queued: true })
  })

  it('uses the real name once the document saved and its photos are pending', async () => {
    const item = await queue.queueMobileDocumentAction(input())
    await queue.updateOfflineQueueItem({ ...item, status: 'failed', server_result: result })
    const rows = await queue.mergePendingTimesheets([{ name: 'TS-1', duration: 3600 }], '2026-11-01', '2026-11-30', actor)
    expect(rows).toHaveLength(1)
    expect(rows[0]).toMatchObject({ name: 'TS-1', offline_queued: true })
  })
})
