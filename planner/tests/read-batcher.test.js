import { afterEach, beforeEach, describe, it, expect, vi } from 'vitest'
import { createReadBatcher } from '../src/utils/readBatcher'

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }
const response = requests => ({ results: requests.map(read => ({ data: read.params })) })

describe('Planner read batching', () => {
  it('combines independent reads and shares identical reads with independent results', async () => {
    const send = vi.fn(async requests => response(requests))
    const batch = createReadBatcher(send)
    const filters = { company: 'MSS' }
    const a = batch.read('employees', filters)
    const b = batch.read('employees', filters)
    const c = batch.read('roster', { year: 2026 })
    filters.company = 'Changed'
    await vi.advanceTimersByTimeAsync(10)
    expect(send).toHaveBeenCalledOnce()
    expect(send.mock.calls[0][0]).toHaveLength(2)
    const [one, two, three] = await Promise.all([a, b, c])
    one.company = 'Edited locally'
    expect(two).toEqual({ company: 'MSS' })
    expect(three).toEqual({ year: 2026 })
  })

  it('cancels one subscriber without cancelling another or sending abandoned queued reads', async () => {
    const send = vi.fn(async requests => response(requests))
    const batch = createReadBatcher(send)
    const controller = new AbortController()
    const cancelled = batch.read('employees', {}, controller.signal).catch(error => error)
    const active = batch.read('employees', {})
    const abandoned = batch.read('projects', {}, controller.signal).catch(error => error)
    controller.abort()
    await vi.advanceTimersByTimeAsync(10)
    expect(send.mock.calls[0][0]).toHaveLength(1)
    expect((await cancelled).name).toBe('AbortError')
    expect((await abandoned).name).toBe('AbortError')
    expect(await active).toEqual({})
  })

  it('isolates a denied dataset while returning the successful one', async () => {
    const batch = createReadBatcher(async () => ({ results: [
      { error: { message: 'Project access denied', exc_type: 'PermissionError' } },
      { data: [{ name: 'EMP-1' }] },
    ] }))
    const denied = batch.read('projects', {}).catch(error => error)
    const employees = batch.read('employees', {})
    await vi.advanceTimersByTimeAsync(10)
    expect((await denied).messages).toEqual(['Project access denied'])
    expect(await employees).toEqual([{ name: 'EMP-1' }])
  })

  it('does not reuse a pre-mutation response for a new read', async () => {
    const first = deferred()
    const send = vi.fn().mockReturnValueOnce(first.promise).mockResolvedValue({ results: [{ data: 'new' }] })
    const batch = createReadBatcher(send)
    const before = batch.read('employees', {})
    await vi.advanceTimersByTimeAsync(10)
    batch.invalidate()
    const after = batch.read('employees', {})
    first.resolve({ results: [{ data: 'old' }] })
    await vi.advanceTimersByTimeAsync(10)
    expect(await before).toBe('old')
    expect(await after).toBe('new')
    expect(send).toHaveBeenCalledTimes(2)
  })

  it('caps batches at twenty and runs one HTTP batch at a time', async () => {
    const first = deferred()
    const send = vi.fn().mockReturnValueOnce(first.promise).mockImplementation(async requests => response(requests))
    const batch = createReadBatcher(send)
    const reads = Array.from({ length: 25 }, (_, i) => batch.read('employees', { i }))
    await vi.advanceTimersByTimeAsync(100)
    expect(send).toHaveBeenCalledOnce()
    expect(send.mock.calls[0][0]).toHaveLength(20)
    first.resolve(response(send.mock.calls[0][0]))
    await vi.advanceTimersByTimeAsync(10)
    expect(send.mock.calls[1][0]).toHaveLength(5)
    expect(await Promise.all(reads)).toHaveLength(25)
  })

  it('rejects all subscribers on network failure and allows a subsequent retry', async () => {
    const send = vi.fn().mockRejectedValueOnce(new Error('Offline')).mockImplementation(async requests => response(requests))
    const batch = createReadBatcher(send)
    const first = batch.read('employees', {}).catch(error => error)
    const second = batch.read('roster', {}).catch(error => error)
    await vi.advanceTimersByTimeAsync(10)
    expect((await first).message).toBe('Offline')
    expect((await second).message).toBe('Offline')
    const retry = batch.read('employees', {})
    await vi.advanceTimersByTimeAsync(10)
    expect(await retry).toEqual({})
  })
})
