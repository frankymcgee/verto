import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { FormControl } from 'frappe-ui'
import TimesheetExceptions from '../src/pages/TimesheetExceptions.vue'

const mocks = vi.hoisted(() => ({ api: vi.fn(), query: {} }))
vi.mock('vue-router', () => ({ useRoute: () => ({ query: mocks.query }) }))
vi.mock('../src/lib/api', () => ({ apiRequest: mocks.api }))
let wrapper
function item(index = 1, extra = {}) {
  return { id: `entry:TS-${index}:1`, employee: `EMP-${index}`, employee_name: `Advisor ${index}`, project: 'PROJ-1', project_name: 'Shutdown',
    date: '2026-10-05', title: 'Hours need review', hours: 13, categories: ['hours'], severity: 'high',
    issues: [{ code: 'hours_exceeded', message: '13 hours claimed; the project maximum is 12.' }],
    links: [{ doctype: 'Timesheet', name: `TS-${index}`, label: 'Open weekly timesheet' }], internal_approved: false, ...extra }
}
function report(items = [item()]) {
  return { week_start: '2026-10-05', week_end: '2026-10-11', generated_at: '2026-10-12 12:00:00', items,
    categories: [{ value: 'hours', label: 'Hours and totals', count: items.filter(row => row.categories.includes('hours')).length },
      { value: 'missing', label: 'Missing hours', count: items.filter(row => row.categories.includes('missing')).length }],
    projects: [{ value: 'PROJ-1', label: 'Shutdown' }], warnings: ['Only readable records are checked.'] }
}
async function render(data = report()) {
  mocks.api.mockResolvedValueOnce({ message: data })
  wrapper = mount(TimesheetExceptions)
  await flushPromises()
}
async function click(label) {
  const button = wrapper.findAll('button').find(button => button.text() === label)
  expect(button, label).toBeTruthy()
  await button.trigger('click'); await flushPromises()
}
const field = label => wrapper.findAllComponents(FormControl).find(control => control.props('label') === label)
beforeEach(() => { vi.clearAllMocks(); mocks.query = {} })
afterEach(() => { wrapper?.unmount(); document.body.innerHTML = '' })

describe('Timesheet exceptions queue', () => {
  it('loads a live report and links to the exact source and approval selection', async () => {
    await render()
    expect(mocks.api.mock.calls[0][1]).toEqual({ cache: 'no-store' })
    expect(wrapper.text()).toContain('1 exception · 1 high priority')
    expect(wrapper.text()).toContain('13 hours claimed; the project maximum is 12.')
    const links = wrapper.findAll('a')
    expect(links.find(link => link.text() === 'Open weekly timesheet').attributes('href')).toBe('/app/timesheet/TS-1')
    const review = new URL(links.find(link => link.text() === 'Review for approval').attributes('href'), 'https://site.test')
    expect(JSON.parse(review.searchParams.get('timesheets'))).toEqual(['TS-1'])
    expect(review.searchParams.get('project')).toBe('PROJ-1')
    expect(review.searchParams.get('week_start')).toBe('2026-10-05')
  })

  it('filters by type and employee, resets pagination and never drops missing staff', async () => {
    const items = Array.from({ length: 28 }, (_, index) => item(index + 1))
    items.push(item(29, { employee_name: 'No weekly record', categories: ['missing'], hours: null, severity: 'review', links: [
      { doctype: 'Shift Assignment', name: 'SHIFT-29', label: 'Open allocation' },
    ] }))
    await render(report(items))
    expect(wrapper.findAll('ol > li')).toHaveLength(25)
    await click('Next')
    expect(wrapper.findAll('ol > li')).toHaveLength(4)
    field('Employee or record').vm.$emit('update:modelValue', 'No weekly')
    await flushPromises()
    expect(wrapper.findAll('ol > li')).toHaveLength(1)
    expect(wrapper.text()).toContain('No weekly record')
    field('Employee or record').vm.$emit('update:modelValue', '')
    await click('Missing hours (1)')
    expect(wrapper.findAll('ol > li')).toHaveLength(1)
    expect(wrapper.find('a[href="/app/shift-assignment/SHIFT-29"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Review for approval')
  })

  it('sends week and project filters and refuses a non-Monday without a request', async () => {
    mocks.query = { week_start: '2026-10-05', project: 'PROJ-1' }
    await render()
    expect(mocks.api.mock.calls[0][0]).toContain('week_start=2026-10-05&project=PROJ-1')
    field('Week beginning (Monday)').vm.$emit('update:modelValue', '2026-10-06')
    await wrapper.find('form').trigger('submit'); await flushPromises()
    expect(wrapper.find('[role="alert"]').text()).toContain('Choose a Monday')
    expect(mocks.api).toHaveBeenCalledTimes(1)
    expect(wrapper.find('ol').exists()).toBe(false)
  })

  it('clears an old report on refresh failure and shows limited permission coverage', async () => {
    const data = report()
    data.warnings.push('Attendance checks are unavailable with your current permissions.')
    await render(data)
    expect(wrapper.find('details').attributes('open')).toBeDefined()
    expect(wrapper.text()).toContain('Attendance checks are unavailable')
    mocks.api.mockRejectedValueOnce(new Error('Read permission is required.'))
    await wrapper.find('form').trigger('submit'); await flushPromises()
    expect(wrapper.find('[role="alert"]').text()).toBe('Read permission is required.')
    expect(wrapper.find('ol').exists()).toBe(false)
  })

  it('renders empty results and escapes record names and messages', async () => {
    const data = report([item(1, { employee_name: '<img src=x onerror=alert(1)>', issues: [{ code: 'hours_exceeded', message: '<script>bad()</script>' }], links: [
      { doctype: 'Daily Timesheet', name: 'DAILY-"/?<>', label: 'Open daily timesheet' },
    ] })])
    await render(data)
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('script').exists()).toBe(false)
    expect(wrapper.find('a[target="_blank"]').attributes('href')).toBe('/app/daily-timesheet/DAILY-%22%2F%3F%3C%3E')
    field('Priority').vm.$emit('update:modelValue', 'none')
    await flushPromises()
    expect(wrapper.text()).toContain('No exceptions match these filters.')
    mocks.api.mockResolvedValueOnce({ message: report([]) })
    await wrapper.find('form').trigger('submit'); await flushPromises()
    expect(wrapper.text()).toContain('No exceptions found in the records checked')
  })
})
