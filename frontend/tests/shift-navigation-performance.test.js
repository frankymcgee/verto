import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, it, expect, vi } from 'vitest'
import Shifts from '../src/pages/Shifts.vue'
const mocks = vi.hoisted(() => ({ api: vi.fn() }))
vi.mock('../src/lib/api', () => ({ apiRequest: mocks.api }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
let wrapper
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
const empty = { message: { shifts: [], timesheets: [] } }
beforeEach(() => { vi.clearAllMocks(); mocks.api.mockResolvedValue(empty) })
afterEach(() => wrapper?.unmount())
describe('Shift month navigation', () => {
  it('retains only the final month while a read is pending', async () => {
    const first = deferred(), last = deferred()
    mocks.api.mockReturnValueOnce(first.promise).mockReturnValueOnce(last.promise)
    wrapper = mount(Shifts)
    const next = wrapper.findAll('button').find(button => button.text() === '›')
    for (let i = 0; i < 8; i++) await next.trigger('click')
    expect(mocks.api).toHaveBeenCalledOnce()
    first.resolve(empty); await flushPromises()
    expect(mocks.api).toHaveBeenCalledTimes(2)
    const target = new Date(); target.setDate(1); target.setMonth(target.getMonth() + 8)
    expect(mocks.api.mock.calls[1][0]).toContain(`start_date=${target.getFullYear()}-${String(target.getMonth()+1).padStart(2,'0')}-01`)
    expect(wrapper.text()).toContain('Loading shifts...')
    last.resolve(empty); await flushPromises()
    expect(wrapper.text()).not.toContain('Loading shifts...')
  })
  it('does not send a queued month after navigating away', async () => {
    const first = deferred(); mocks.api.mockReturnValueOnce(first.promise)
    wrapper = mount(Shifts)
    await wrapper.findAll('button').find(button => button.text() === '›').trigger('click')
    wrapper.unmount(); wrapper = null
    first.resolve(empty); await flushPromises()
    expect(mocks.api).toHaveBeenCalledOnce()
  })
  it('can load the latest month after an earlier request fails', async () => {
    const first = deferred(); mocks.api.mockReturnValueOnce(first.promise)
    wrapper = mount(Shifts)
    await wrapper.findAll('button').find(button => button.text() === '›').trigger('click')
    first.reject(new Error('Old month failed')); await flushPromises()
    expect(mocks.api).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).not.toContain('Old month failed')
    expect(wrapper.text()).not.toContain('Loading shifts...')
  })
})
