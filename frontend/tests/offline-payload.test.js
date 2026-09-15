import { beforeEach, describe, it, expect, vi, afterEach } from 'vitest'
const mocks = vi.hoisted(() => ({ api: vi.fn(), cache: vi.fn(), clear: vi.fn() }))
vi.mock('../src/lib/api', () => ({ apiRequest: mocks.api }))
vi.mock('../src/pwa/offlineQueue', () => ({ cacheApiResponse: mocks.cache }))
vi.mock('../src/pwa/offlineSecurity', () => ({ clearOfflineReadCache: mocks.clear }))
import { primeOfflineData } from '../src/pwa/offlineBootstrap'

const schema = { mobile_doctype: 'daily-timesheet', fields: [{ fieldname: 'notes', fieldtype: 'Data' }] }
const payload = () => ({ message: {
  contract_version: 2, user: 'viewer', generated_at: '2026-09-15', schemas: { 'daily-timesheet': schema },
  edit_schemas: { 'daily-timesheet': schema }, edit_docs: {
    'daily-timesheet:TS-1': { schema_key: 'daily-timesheet', name: 'TS-1', values: { notes: 'Saved notes' }, files: [{ name: 'FILE-1' }], can_write: false },
  },
} })
beforeEach(() => {
  vi.clearAllMocks(); window.localStorage.clear()
  Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
  mocks.api.mockResolvedValue(payload())
  mocks.cache.mockResolvedValue(undefined); mocks.clear.mockResolvedValue(undefined)
})
afterEach(() => vi.unstubAllGlobals())

describe('Compact offline download compatibility', () => {
  it('restores complete editor responses and stores only a small service-worker actor marker', async () => {
    await primeOfflineData()
    expect(mocks.api.mock.calls[0][0]).toContain('contract_version=2')
    const edit = mocks.cache.mock.calls.find(([key]) => key.includes('get_mobile_doc_for_edit'))[1].message
    expect(edit.schema).toEqual(schema)
    expect(edit.values).toEqual({ notes: 'Saved notes' })
    expect(edit.files).toEqual([{ name: 'FILE-1' }])
    expect(edit.can_write).toBe(false)
    expect(edit.schema_key).toBeUndefined()
    const marker = mocks.cache.mock.calls.find(([key]) => key === 'offline-bootstrap:latest')[1]
    expect(marker).toEqual({ message: { user: 'viewer', generated_at: '2026-09-15' } })
  })

  it('accepts legacy server responses containing an inline schema', async () => {
    const legacy = payload(); delete legacy.message.edit_schemas
    legacy.message.edit_docs['daily-timesheet:TS-1'].schema = schema
    mocks.api.mockResolvedValue(legacy)
    await primeOfflineData()
    expect(mocks.cache.mock.calls.find(([key]) => key.includes('get_mobile_doc_for_edit'))[1].message.schema).toEqual(schema)
  })

  it('rejects incomplete definitions before changing the actor or caches', async () => {
    const invalid = payload(); delete invalid.message.edit_schemas
    mocks.api.mockResolvedValue(invalid)
    window.localStorage.setItem('verto:offline-actor', 'old-viewer')
    await expect(primeOfflineData()).rejects.toThrow('form definition')
    expect(mocks.cache).not.toHaveBeenCalled(); expect(mocks.clear).not.toHaveBeenCalled()
    expect(window.localStorage.getItem('verto:offline-actor')).toBe('old-viewer')
  })

  it('clears the previous user cache before saving a new user dataset', async () => {
    window.localStorage.setItem('verto:offline-actor', 'old-viewer')
    await primeOfflineData()
    expect(mocks.clear).toHaveBeenCalledOnce()
    expect(mocks.clear.mock.invocationCallOrder[0]).toBeLessThan(mocks.cache.mock.invocationCallOrder[0])
    expect(window.localStorage.getItem('verto:offline-actor')).toBe('viewer')
  })

  it('does not download or overwrite cached data while offline', async () => {
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: false })
    expect(await primeOfflineData()).toBeNull()
    expect(mocks.api).not.toHaveBeenCalled(); expect(mocks.cache).not.toHaveBeenCalled()
  })

  it('does not automatically cache another copy of the aggregate API response', async () => {
    const { apiRequest } = await vi.importActual('../src/lib/api')
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(payload()))))
    await apiRequest('/api/method/verto.api.mobile.offline.get_offline_bootstrap?contract_version=2')
    expect(mocks.cache).not.toHaveBeenCalled()
  })
})
