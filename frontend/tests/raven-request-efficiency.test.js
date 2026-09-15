import { describe, it, expect, vi, beforeEach } from 'vitest'
const mocks = vi.hoisted(() => ({ api: vi.fn() }))
vi.mock('../src/lib/api', () => ({ apiRequest: mocks.api }))
import { getThreadCounts, getMessages } from '../src/lib/ravenClient'
beforeEach(() => vi.clearAllMocks())

describe('Compact Raven metadata requests', () => {
  it('requests counts for 12 threads in one call and preserves zero counts', async () => {
    mocks.api.mockResolvedValue({ message: { one: 0, two: 123 } })
    const names = Array.from({ length: 12 }, (_, i) => `thread-${i}`)
    expect(await getThreadCounts(names)).toEqual({ one: 0, two: 123 })
    expect(mocks.api).toHaveBeenCalledOnce()
    const url = new URL(mocks.api.mock.calls[0][0], 'https://test.example')
    expect(url.pathname).toBe('/api/method/verto.api.mobile.raven.get_thread_counts')
    expect(JSON.parse(url.searchParams.get('messages'))).toEqual(names)
  })

  it('deduplicates thread IDs and splits requests at the server limit', async () => {
    mocks.api.mockResolvedValue({ message: {} })
    const names = Array.from({ length: 51 }, (_, i) => `thread-${i}`)
    await getThreadCounts([...names, ...names])
    expect(mocks.api).toHaveBeenCalledTimes(2)
    expect(mocks.api.mock.calls.map(([url]) => JSON.parse(new URL(url, 'https://test.example').searchParams.get('messages')).length)).toEqual([50, 1])
  })

  it('does not refetch embedded previews or fetch unused secondary previews', async () => {
    mocks.api.mockImplementation(async (url) => url.includes('get_messages') ? { message: { messages: [
      { name: 'one', creation: '2026-09-15', document_preview: { doctype: 'Task', docname: 'embedded' } },
      { name: 'two', creation: '2026-09-15', document_links: [{ doctype: 'Task', docname: 'primary' }, { doctype: 'Task', docname: 'unused' }] },
      { name: 'three', creation: '2026-09-15', document_links: [{ doctype: 'Task', docname: 'primary' }] },
    ] } } : { message: { id: 'primary' } })
    const result = await getMessages('general')
    expect(result.messages).toHaveLength(3)
    expect(mocks.api).toHaveBeenCalledTimes(2) // Stream plus one unique displayed preview.
    expect(mocks.api.mock.calls[1][0]).toContain('docname=primary')
  })
})
