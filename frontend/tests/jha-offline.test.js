import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
const mocks = vi.hoisted(() => ({ api: vi.fn(), cache: vi.fn(), read: vi.fn(), items: vi.fn(), queue: vi.fn(), sync: vi.fn() }))
vi.mock('../src/lib/api', () => ({ apiRequest: mocks.api }))
vi.mock('../src/pwa/offlineQueue', () => ({ cacheApiResponse: mocks.cache, getCachedApiResponse: mocks.read,
  getOfflineQueueItems: mocks.items, queueJhaObservation: mocks.queue, syncOfflineQueueItem: mocks.sync }))
import { downloadOfflineJha, pendingJhaObservations, readOfflineJha, saveJhaObservation } from '../src/pwa/offlineJha'
const copy = () => ({ user: 'viewer', saved_at: '2026-10-14 10:00', jha: { name: 'JHA-1', revision: 2, status: 'Signed' }, resources: [], photos: {}, review: {} })
const originalOnline = Object.getOwnPropertyDescriptor(navigator, 'onLine')
beforeEach(() => {
  vi.clearAllMocks(); window.localStorage.clear(); window.localStorage.setItem('verto:offline-actor', 'viewer')
  Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
  mocks.api.mockResolvedValue({ message: copy() }); mocks.cache.mockResolvedValue({}); mocks.items.mockResolvedValue([])
  mocks.queue.mockResolvedValue({ id: 'QUEUE-1' }); mocks.sync.mockResolvedValue({ name: 'OBS-1' })
})
afterEach(() => {
  vi.unstubAllGlobals()
  if (originalOnline) Object.defineProperty(navigator, 'onLine', originalOnline)
  else Reflect.deleteProperty(navigator, 'onLine')
})
describe('durable JHA offline copies and observations', () => {
  it('downloads fresh authenticated data into an account-specific cache', async () => {
    await downloadOfflineJha('JHA-1')
    expect(mocks.api.mock.calls[0][1]).toEqual({ cache: 'no-store' })
    expect(mocks.cache.mock.calls[0][0]).toBe('jha-copy:viewer:JHA-1')
    expect(mocks.cache.mock.calls[0][1].jha.revision).toBe(2)
  })
  it('never downloads a new copy offline', async () => {
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: false })
    await expect(downloadOfflineJha('JHA-1')).rejects.toThrow('Connect'); expect(mocks.api).not.toHaveBeenCalled()
  })
  it('rejects a different account before saving a download or showing cached data', async () => {
    mocks.api.mockResolvedValue({ message: { ...copy(), user: 'another' } })
    await expect(downloadOfflineJha('JHA-1')).rejects.toThrow('signed-in session'); expect(mocks.cache).not.toHaveBeenCalled()
    mocks.read.mockResolvedValue({ ...copy(), user: 'another' }); expect(await readOfflineJha('JHA-1')).toBeNull()
  })
  it('retains the signed data and indicates when a photo could not be saved', async () => {
    const saved = copy(); saved.resources = [{ kind: 'Photo', evidence: '/private/files/missing.png' }]
    mocks.api.mockResolvedValue({ message: saved }); vi.stubGlobal('fetch', vi.fn(async () => new Response('', { status: 404 })))
    const result = await downloadOfflineJha('JHA-1'); expect(result.media_missing).toBe(1); expect(result.jha.revision).toBe(2)
  })
  it('does not save a copy if the account changes during a photo download', async () => {
    const saved = copy(); saved.resources = [{ kind: 'Photo', evidence: '/private/files/pump.png' }]; mocks.api.mockResolvedValue({ message: saved })
    vi.stubGlobal('fetch', vi.fn(async () => { window.localStorage.setItem('verto:offline-actor', 'another'); return new Response('', { status: 404 }) }))
    await expect(downloadOfflineJha('JHA-1')).rejects.toThrow('account changed'); expect(mocks.cache).not.toHaveBeenCalled()
  })
  it('queues observations with their exact downloaded revision, actor and stable request ID', async () => {
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: false })
    const result = await saveJhaObservation(copy(), 'Changed restraint', 'STEP-1', true, 'request-1')
    expect(result.queued).toBe(true); expect(mocks.sync).not.toHaveBeenCalled()
    expect(mocks.queue.mock.calls[0][0]).toMatchObject({ jha_name: 'JHA-1', revision: 2, actor: 'viewer', request_id: 'request-1', notes: 'Changed restraint', step_row: 'STEP-1', work_changed: 1 })
  })
  it('keeps the durable item pending when reconnecting sync fails', async () => {
    mocks.sync.mockRejectedValue(Error('Permission changed'))
    expect((await saveJhaObservation(copy(), 'Check restraint', '', false, 'request-1')).queued).toBe(true)
    expect(mocks.queue).toHaveBeenCalledOnce(); expect(mocks.sync).toHaveBeenCalledWith('QUEUE-1')
  })
  it('never queues an observation as another person', async () => {
    await expect(saveJhaObservation({ ...copy(), user: 'another' }, 'Check restraint', '', false, 'request-1')).rejects.toThrow('person who downloaded')
    expect(mocks.queue).not.toHaveBeenCalled()
  })
  it('only displays pending observations for the selected JHA and account', async () => {
    mocks.items.mockResolvedValue([{ id: 'A', kind: 'jha_observation', values: { jha_name: 'JHA-1', actor: 'viewer' } },
      { id: 'B', kind: 'jha_observation', values: { jha_name: 'JHA-1', actor: 'another' } },
      { id: 'C', kind: 'jha_observation', values: { jha_name: 'JHA-2', actor: 'viewer' } }])
    expect((await pendingJhaObservations('JHA-1')).map(row => row.id)).toEqual(['A'])
  })
})
