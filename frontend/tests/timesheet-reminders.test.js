import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import MissingHoursReminder from '../src/components/MissingHoursReminder.vue'
import Shifts from '../src/pages/Shifts.vue'

const mocks = vi.hoisted(() => ({ api: vi.fn(), push: vi.fn(), boot: null, route: null }))
vi.mock('../src/lib/api', () => ({ apiRequest: mocks.api }))
vi.mock('../src/lib/mobileBoot', () => ({ useMobileBoot: () => ({ boot: mocks.boot }) }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.push, currentRoute: mocks.route }) }))

let wrapper
const row = { name: 'R1', date: '2026-09-30', shift_type: 'NS', project: 'PROJ-1', shift_assignment: 'SHIFT-1' }
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { resolve, promise } }
const response = (rows = [row]) => ({ message: { enabled: true, reminders: rows } })
const render = async () => {
  wrapper = mount(MissingHoursReminder, { global: { stubs: { MobileSheet: { props: ['open'], template: '<div v-if="open" role="dialog"><slot /></div>' } } } })
  await flushPromises()
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.useFakeTimers()
  mocks.boot = ref({ navigation_access: { has_employee_profile: true } })
  mocks.route = ref({ fullPath: '/', query: {} })
  mocks.api.mockResolvedValue(response())
  Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
})
afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.clearAllTimers()
  vi.useRealTimers()
})

describe('Persistent missing-hours alert', () => {
  it('retains the banner when the drawer closes and opens the correct overdue shift', async () => {
    await render()
    expect(wrapper.text()).toContain('1 shift needs hours')
    await wrapper.find('button').trigger('click')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
    await wrapper.findAll('button').find(button => button.text() === 'Close').trigger('click')
    expect(wrapper.text()).toContain('1 shift needs hours')
    await wrapper.find('button').trigger('click')
    await wrapper.findAll('button').find(button => button.text().includes('Enter hours')).trigger('click')
    expect(mocks.push).toHaveBeenCalledWith({ path: '/shifts', query: { date: '2026-09-30', shift: 'SHIFT-1' } })
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
  })

  it('clears saved hours immediately and clears offline hours only after server sync', async () => {
    await render()
    mocks.api.mockResolvedValue(response([]))
    window.dispatchEvent(new Event('verto:timesheet-saved'))
    await flushPromises()
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
    mocks.api.mockResolvedValue(response())
    window.dispatchEvent(new Event('focus'))
    await flushPromises()
    expect(wrapper.find('[role="status"]').exists()).toBe(true)
    mocks.api.mockResolvedValue(response([]))
    window.dispatchEvent(new Event('verto:offline-queue-synced'))
    await flushPromises()
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
  })

  it('preserves outstanding hours across a failed refresh and rereads on return', async () => {
    await render()
    mocks.api.mockRejectedValueOnce(new Error('offline'))
    window.dispatchEvent(new Event('focus'))
    await flushPromises()
    expect(wrapper.text()).toContain('1 shift needs hours')
    mocks.api.mockResolvedValue(response([row, { ...row, name: 'R2', date: '2026-10-01' }]))
    await vi.advanceTimersByTimeAsync(60_000)
    expect(wrapper.text()).toContain('2 shifts need hours')
  })

  it('coalesces concurrent refresh events and releases listeners after navigation', async () => {
    const first = deferred()
    mocks.api.mockReturnValueOnce(first.promise)
    wrapper = mount(MissingHoursReminder, { global: { stubs: { MobileSheet: true } } })
    for (let i = 0; i < 5; i++) window.dispatchEvent(new Event('focus'))
    expect(mocks.api).toHaveBeenCalledOnce()
    first.resolve(response())
    await flushPromises()
    expect(mocks.api).toHaveBeenCalledTimes(2)
    wrapper.unmount(); wrapper = null
    window.dispatchEvent(new Event('focus'))
    window.dispatchEvent(new Event('verto:timesheet-saved'))
    await vi.advanceTimersByTimeAsync(60_000)
    expect(mocks.api).toHaveBeenCalledTimes(2)
  })

  it('does not fetch for viewers without an Employee profile or while offline', async () => {
    mocks.boot.value.navigation_access.has_employee_profile = false
    await render()
    expect(mocks.api).not.toHaveBeenCalled()
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: false })
    mocks.boot.value.navigation_access.has_employee_profile = true
    window.dispatchEvent(new Event('focus'))
    await flushPromises()
    expect(mocks.api).not.toHaveBeenCalled()
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
    window.dispatchEvent(new Event('online'))
    await flushPromises()
    expect(mocks.api).toHaveBeenCalledOnce()
  })
})

describe('Reminder links into Shifts', () => {
  it('loads an overdue date in a previous month and selects its specific allocation', async () => {
    mocks.route.value = { fullPath: '/shifts?date=2026-09-30&shift=SHIFT-1', query: { date: '2026-09-30', shift: 'SHIFT-1' } }
    mocks.api.mockResolvedValue({ message: { shifts: [
      { name: 'OTHER', start_date: '2026-09-01', end_date: '2026-10-31', shift_type: 'DS', custom_project_name: 'Other' },
      { name: 'SHIFT-1', start_date: '2026-09-01', end_date: '2026-10-31', shift_type: 'NS', custom_project_name: 'Shutdown' },
    ], timesheets: [] } })
    wrapper = mount(Shifts)
    await flushPromises()
    expect(mocks.api.mock.calls[0][0]).toContain('start_date=2026-09-01')
    expect(wrapper.text()).toContain('Shutdown')
    await wrapper.findAll('button').find(button => button.text() === 'Submit Timesheet').trigger('click')
    expect(mocks.push).toHaveBeenCalledWith({ path: '/new/daily-timesheet', query: { date: '2026-09-30', shift_allocation: 'SHIFT-1' } })
    mocks.route.value = { fullPath: '/shifts?date=2026-08-28', query: { date: '2026-08-28' } }
    await flushPromises()
    expect(mocks.api.mock.calls[1][0]).toContain('start_date=2026-08-01')
  })
})
