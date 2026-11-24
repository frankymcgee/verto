// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { IDBFactory, IDBKeyRange, IDBObjectStore } from 'fake-indexeddb'
import { Blob, File } from 'node:buffer'

vi.mock('../src/lib/diagnostics', () => ({ reportClientError: vi.fn() }))
vi.mock('../src/lib/csrf', () => ({ withCsrfHeaders: (headers) => new Headers(headers) }))

const actor = 'worker@example.test'
const result = { doctype: 'Daily Timesheet', name: 'TS-1', route: '/shifts' }
const response = (value = { ok: true, result }) => new Response(JSON.stringify({ message: value }))
const attachmentUploads = () => fetch.mock.calls.filter(([url]) =>
  url === '/api/method/upload_file?method=verto.api.mobile.offline.upload_attachment')
const attachmentMetadata = (options) => JSON.parse(decodeURIComponent(options.headers.get('X-Verto-Attachment')))
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
    const automatic = queue.syncOfflineQueue(actor)
    expect(queue.syncOfflineQueue(actor)).toBe(automatic)
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledOnce())
    pending.resolve(response())
    await Promise.all([direct, repeat, automatic])
    expect(fetch).toHaveBeenCalledOnce()
    expect(await queue.getOfflineQueueSummary(actor)).toMatchObject({ total: 0 })
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
    const lock = vi.fn(async (name, _options, run) => run({ name }))
    Object.defineProperty(navigator, 'locks', { configurable: true, value: { request: lock } })
    expect(await queue.getOfflineQueueSummary(actor)).toMatchObject({ queued: 1, syncing: 0 })
    await queue.syncOfflineQueueItem(item.id)
    expect(lock).toHaveBeenCalledWith(`verto:offline-sync:${item.id}`, { ifAvailable: true }, expect.any(Function))
    expect(fetch).toHaveBeenCalledOnce()
  })

  it('syncs the next form when an earlier form is locked by another window', async () => {
    const first = await queue.queueMobileDocumentAction(input())
    await queue.updateOfflineQueueItem({
      ...first, status: 'syncing', sync_owner: 'another-window', sync_expires_at: Date.now() + 120_000,
    })
    const next = await queue.queueMobileDocumentAction(input({ operationId: 'next-form' }))
    const request = vi.fn(async (name, options, run) => {
      expect(options).toEqual({ ifAvailable: true })
      return run(name.endsWith(first.id) ? null : { name })
    })
    Object.defineProperty(navigator, 'locks', { configurable: true, value: { request } })

    expect(await queue.syncOfflineQueue(actor)).toEqual({ synced: 1, failed: 0, skipped: false })
    expect((await queue.getOfflineQueueItem(first.id)).status).toBe('syncing')
    expect((await queue.getOfflineQueueItem(next.id)).status).toBe('synced')
    expect(fetch.mock.calls.map(([, options]) => options.body.get('operation_id'))).toEqual([next.id])
  })

  it('retains a timed-out form and its photos, pauses the batch and backs off before retrying', async () => {
    const attachment = queue.makeOfflineAttachment(new Blob(['photo']), 'photo.jpg')
    const first = await queue.queueMobileDocumentAction(input({ attachments: [attachment] }))
    const next = await queue.queueMobileDocumentAction(input({ operationId: 'next-form' }))
    const started = deferred()
    fetch.mockImplementationOnce((_url, { signal }) => {
      started.resolve(signal)
      return new Promise((_resolve, reject) => {
        signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true })
      })
    })
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    try {
      const sync = queue.syncOfflineQueue(actor)
      const signal = await started.promise
      await vi.advanceTimersByTimeAsync(30_000)
      expect(signal.aborted).toBe(true)
      expect(await sync).toEqual({ synced: 0, failed: 1, skipped: true })
    } finally {
      vi.useRealTimers()
    }

    const failed = await queue.getOfflineQueueItem(first.id)
    expect(failed).toMatchObject({ status: 'queued', last_error_retryable: true, last_error: expect.stringContaining('too long') })
    expect(failed.next_retry_at).toBeGreaterThan(Date.now())
    expect(failed.attachments[0].id).toBe(attachment.id)
    expect((await queue.getOfflineQueueItem(next.id)).status).toBe('queued')
    await queue.syncOfflineQueue(actor)
    expect((await queue.getOfflineQueueItem(first.id)).attempts).toBe(1)
    await queue.syncOfflineQueueItem(first.id, { user: actor })
    const operationIds = fetch.mock.calls.filter(([url]) => url.endsWith('sync_action'))
      .map(([, options]) => options.body.get('operation_id'))
    expect(operationIds).toEqual([first.id, next.id, first.id])
  })

  it('preserves the current attempt when a previous window receives a late response', async () => {
    const item = await queue.queueMobileDocumentAction(input())
    const pending = deferred()
    fetch.mockReturnValueOnce(pending.promise)
    const oldAttempt = queue.syncOfflineQueueItem(item.id)
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledOnce())
    const current = await queue.getOfflineQueueItem(item.id)
    await queue.updateOfflineQueueItem({
      ...current, sync_owner: 'new-window', sync_expires_at: Date.now() + 120_000,
    })
    pending.resolve(response())
    await expect(oldAttempt).rejects.toThrow('already syncing')
    expect(await queue.getOfflineQueueItem(item.id)).toMatchObject({
      status: 'syncing', sync_owner: 'new-window', server_result: null,
    })
  })

  it('shows and syncs work for the signed-in account only', async () => {
    const mine = await queue.queueMobileDocumentAction(input())
    const other = await queue.queueMobileDocumentAction(input({
      operationId: 'other-form', values: { __verto_offline_user: 'other@example.test' },
    }))
    expect(await queue.getOfflineQueueSummary(actor)).toMatchObject({ total: 1, queued: 1 })
    expect((await queue.getPendingOfflineQueueItems(actor)).map(item => item.id)).toEqual([mine.id])
    await expect(queue.syncOfflineQueueItem(other.id, { user: actor })).rejects.toThrow('another signed-in user')
    expect(await queue.syncOfflineQueue(actor)).toMatchObject({ synced: 1, failed: 0 })
    expect((await queue.getOfflineQueueItem(other.id)).status).toBe('queued')
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
    await expect(queue.syncOfflineQueueItem('document-stable', { deleteOnPermanentFailure: true })).rejects.toThrow('Connection unavailable')
    expect((await queue.getOfflineQueueItem('document-stable')).status).toBe('queued')
    await queue.syncOfflineQueueItem('document-stable')
    expect(fetch.mock.calls.map(([, options]) => options.body.get('operation_id'))).toEqual(['document-stable', 'document-stable'])
  })

  it('retains an ambiguous HTTP 200 response for a safe retry', async () => {
    await queue.queueMobileDocumentAction(input())
    fetch.mockResolvedValueOnce(new Response('<html>Proxy error</html>'))
    await expect(queue.syncOfflineQueueItem('document-stable', { deleteOnPermanentFailure: true })).rejects.toThrow('Connection unavailable')
    expect((await queue.getOfflineQueueItem('document-stable')).status).toBe('queued')
  })

  it('sends a restored photo as a Blob with its original name, type and bytes', async () => {
    const photo = new File(['photo evidence'], 'site photo café.jpg', { type: 'image/jpeg' })
    const attachment = queue.makeOfflineAttachment(photo)
    const item = await queue.queueMobileDocumentAction(input({ attachments: [attachment] }))

    await queue.syncOfflineQueueItem(item.id)
    const [[url, options]] = attachmentUploads()
    expect(options.body).toBeInstanceOf(Blob)
    expect(options.body).not.toBeInstanceOf(File)
    expect(options.body.type).toBe(photo.type)
    expect(attachmentMetadata(options)).toEqual({
      operation_id: item.id, attachment_id: attachment.id, target_doctype: result.doctype,
      target_name: result.name, file_name: photo.name,
    })
    const request = new Request(new URL(url, window.location.origin), options)
    expect(request.headers.get('Content-Type')).toBe('application/octet-stream')
    expect(await request.text()).toBe('photo evidence')
    expect(fetch.mock.calls.at(-1)[0]).toContain('queue_submitted_form_review')
  })

  it('reports an oversized photo and retains it after the form has synced', async () => {
    const attachment = queue.makeOfflineAttachment(new Blob(['photo']), 'site photo.jpg')
    const item = await queue.queueMobileDocumentAction(input({ attachments: [attachment] }))
    fetch.mockResolvedValueOnce(response()).mockResolvedValueOnce(new Response('Too large', { status: 413 }))

    await expect(queue.syncOfflineQueueItem(item.id)).rejects.toThrow('site photo.jpg exceeds the server')
    const retained = await queue.getOfflineQueueItem(item.id)
    expect(retained.server_result).toEqual(result)
    expect(retained.attachments[0].id).toBe(attachment.id)
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
    expect(attachmentUploads().map(([, options]) => attachmentMetadata(options).attachment_id))
      .toEqual([attachment.id, attachment.id])
    expect((await queue.getOfflineQueueItem('document-stable')).attachments).toEqual([])
  })

  it('does not re-upload an acknowledged photo when a later photo fails', async () => {
    const attachments = ['one.jpg', 'two.jpg'].map(name => queue.makeOfflineAttachment(new Blob([name]), name))
    const values = { ...input().values, link_task: 'TASK-2', link_project: 'PROJECT-1' }
    await queue.queueMobileDocumentAction(input({ attachments, values }))
    fetch.mockResolvedValueOnce(response()).mockResolvedValueOnce(response())
      .mockRejectedValueOnce(new TypeError('Network failure'))
    await expect(queue.syncOfflineQueueItem('document-stable')).rejects.toThrow('Connection unavailable')
    await queue.syncOfflineQueueItem('document-stable')
    const writes = fetch.mock.calls.filter(([url]) => url.endsWith('sync_action'))
    expect(writes).toHaveLength(1)
    expect(JSON.parse(writes[0][1].body.get('values'))).toMatchObject(values)
    const uploads = attachmentUploads().map(([, options]) => attachmentMetadata(options))
    expect(uploads.map((upload) => upload.target_name)).toEqual([result.name, result.name, result.name])
    expect(uploads.map((upload) => upload.attachment_id)).toEqual([attachments[0].id, attachments[1].id, attachments[1].id])
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
    expect(await queue.getOfflineQueueSummary(actor)).toMatchObject({ queued: 1, failed: 1, total: 2 })
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
    expect(await queue.getPendingOfflineQueueItems('other@example.test')).toEqual([])
    expect(await queue.getPendingOfflineQueueItems('Guest')).toEqual([])
    await expect(queue.discardFailedOfflineQueueItem(item.id, 'other@example.test')).rejects.toThrow('another signed-in user')
    expect(await queue.getPendingOfflineQueueItems(actor)).toHaveLength(1)
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

describe('Durable upload progress and annotated evidence', () => {
  it('persists and uploads photo bytes even when the database rejects native Blob/File values', async () => {
    const put = IDBObjectStore.prototype.put
    const rejectBlobs = vi.spyOn(IDBObjectStore.prototype, 'put').mockImplementation(function (value, ...args) {
      if (value.attachments?.some(attachment => attachment.blob instanceof Blob) || value.attachment?.blob instanceof Blob) {
        throw new DOMException('Error preparing Blob/File data to be stored in object store', 'DataCloneError')
      }
      return put.call(this, value, ...args)
    })
    try {
      const attachment = queue.makeOfflineAttachment(new File(['original bytes'], 'original.jpg', { type: 'image/jpeg' }))
      const item = await queue.queueMobileDocumentAction(input({ attachments: [attachment] }))
      const restored = await queue.getOfflineQueueItem(item.id)
      expect(await restored.attachments[0].blob.text()).toBe('original bytes')
      await queue.syncOfflineQueueItem(item.id)
      expect(await attachmentUploads()[0][1].body.text()).toBe('original bytes')
      expect((await queue.getOfflineQueueItem(item.id)).status).toBe('synced')
    } finally { rejectBlobs.mockRestore() }
  })

  it('still uploads a legacy native-Blob queue record without changing its attachment ID', async () => {
    const item = await queue.queueMobileDocumentAction(input())
    const photo = queue.makeOfflineAttachment(new Blob(['legacy evidence']), 'legacy.jpg')
    await new Promise((resolve, reject) => {
      const open = indexedDB.open('verto-mobile-offline-db', 3)
      open.onerror = () => reject(open.error)
      open.onsuccess = () => {
        const transaction = open.result.transaction('offline_queue', 'readwrite')
        transaction.objectStore('offline_queue').put({ ...item, attachments: [photo] })
        transaction.oncomplete = () => { open.result.close(); resolve() }
        transaction.onerror = () => { open.result.close(); reject(transaction.error) }
      }
    })
    await queue.syncOfflineQueueItem(item.id)
    expect(attachmentMetadata(attachmentUploads()[0][1]).attachment_id).toBe(photo.id)
    expect(await attachmentUploads()[0][1].body.text()).toBe('legacy evidence')
  })

  it('records accepted stages and only confirms after both originals, copies and the review request arrive', async () => {
    const photos = [queue.makeOfflineAttachment(new Blob(['original bytes']), 'original.jpg'),
      queue.makeOfflineAttachment(new Blob(['marked copy']), 'original-annotated.jpg')]
    await queue.queueMobileDocumentAction(input({ attachments: photos }))
    const document = deferred(), first = deferred(), second = deferred(), review = deferred()
    fetch.mockReturnValueOnce(document.promise).mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise).mockReturnValueOnce(review.promise)
    const sync = queue.syncOfflineQueueItem('document-stable', { user: actor })
    await vi.waitFor(async () => expect((await queue.getOfflineQueueItem('document-stable')).sync_stage).toBe('saving_document'))
    document.resolve(response())
    await vi.waitFor(() => expect(attachmentUploads()).toHaveLength(1))
    expect(await queue.getOfflineQueueItem('document-stable')).toMatchObject({
      server_result: result, sync_stage: 'uploading_attachments', attachment_count: 2,
      uploaded_attachment_count: 0, active_attachment_name: 'original.jpg',
    })
    first.resolve(response({ file_url: '/private/files/original.jpg' }))
    await vi.waitFor(() => expect(attachmentUploads()).toHaveLength(2))
    expect(await queue.getOfflineQueueItem('document-stable')).toMatchObject({ uploaded_attachment_count: 1, active_attachment_name: 'original-annotated.jpg' })
    second.resolve(response({ file_url: '/private/files/copy.jpg' }))
    await vi.waitFor(async () => expect((await queue.getOfflineQueueItem('document-stable')).sync_stage).toBe('requesting_review'))
    expect((await queue.getOfflineQueueItem('document-stable')).status).toBe('syncing')
    review.resolve(response({ queued: true })); await sync
    const confirmed = await queue.getOfflineQueueItem('document-stable')
    expect(confirmed).toMatchObject({ status: 'synced', sync_stage: 'confirmed', attachment_count: 2, uploaded_attachment_count: 2, attachments: [] })
    expect(confirmed.confirmed_at).toBeTruthy()
    expect(await queue.getPendingOfflineQueueItems(actor)).toEqual([])
    expect((await queue.getVisibleOfflineQueueItems(actor)).map(item => item.id)).toEqual(['document-stable'])
    expect(await queue.getVisibleOfflineQueueItems('other@example.test')).toEqual([])
    expect(await attachmentUploads()[0][1].body.text()).toBe('original bytes')
    expect(await attachmentUploads()[1][1].body.text()).toBe('marked copy')
  })

  it('retains partial attachment progress across a dropout and resumes without uploading accepted evidence again', async () => {
    const attachments = ['original.jpg', 'annotated.jpg'].map(name => queue.makeOfflineAttachment(new Blob([name]), name))
    await queue.queueMobileDocumentAction(input({ attachments }))
    fetch.mockResolvedValueOnce(response()).mockResolvedValueOnce(response({ file_url: '/private/files/original.jpg' }))
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
    await expect(queue.syncOfflineQueueItem('document-stable')).rejects.toThrow()
    const saved = await queue.getOfflineQueueItem('document-stable')
    expect(saved).toMatchObject({ status: 'queued', sync_stage: 'uploading_attachments', attachment_count: 2, uploaded_attachment_count: 1 })
    expect(saved.attachments).toHaveLength(2)
    await queue.syncOfflineQueueItem('document-stable')
    expect(fetch.mock.calls.filter(([url]) => url.endsWith('sync_action'))).toHaveLength(1)
    expect(attachmentUploads().map(([, options]) => attachmentMetadata(options).file_name)).toEqual(['original.jpg', 'annotated.jpg', 'annotated.jpg'])
  })

  it('bounds recent confirmation history while retaining every pending item', async () => {
    for (let index = 0; index < 25; index++) {
      const item = await queue.queueMobileDocumentAction(input({ operationId: `done-${index}` }))
      await queue.updateOfflineQueueItem({ ...item, status: 'synced', confirmed_at: new Date(Date.now() - index * 1000).toISOString() })
    }
    const old = await queue.queueMobileDocumentAction(input({ operationId: 'old' }))
    await queue.updateOfflineQueueItem({ ...old, status: 'synced', confirmed_at: '2020-01-01T00:00:00Z' })
    await queue.queueMobileDocumentAction(input({ operationId: 'pending' }))
    const visible = await queue.getVisibleOfflineQueueItems(actor)
    expect(visible).toHaveLength(21)
    expect(visible[0].id).toBe('pending')
    expect(visible.some(item => item.id === 'old')).toBe(false)
    expect(await queue.getOfflineQueueSummary(actor)).toMatchObject({ total: 1 })
  })
})
