import { afterEach, beforeEach, describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createRouter, createMemoryHistory } from 'vue-router'
import { Combobox, setConfig } from 'frappe-ui'

const wire = vi.hoisted(() => ({ send: vi.fn(), socket: null }))
vi.mock('frappe-ui', async original => ({ ...await original(), frappeRequest: (...args) => wire.send(...args) }))
vi.mock('socket.io-client', () => ({ Manager: class {
  socket() {
    const handlers = {}
    const socket = {
      connected: false, ack: null,
      on(name, callback) { handlers[name] = callback; return socket },
      emit(name, callback) { if (name === 'verto:planner_subscribe') socket.ack = callback },
      timeout: () => socket, connect() {}, disconnect() {}, removeAllListeners() {},
      receive(name, payload) { if (name === 'connect') socket.connected = true; handlers[name]?.(payload) },
    }
    wire.socket = socket
    return socket
  }
} }))
import Home from '../src/views/Home.vue'
import Header from '../src/components/MonthViewHeader.vue'
import ShiftDialog from '../src/components/ShiftAssignmentDialog.vue'
import { plannerRequest } from '../src/utils/requestCoordinator'
import { usePlannerBootstrap } from '../src/utils/bootstrap'
import { raiseToast } from '../src/utils'
vi.mock('../src/utils', async original => ({ ...await original(), raiseToast: vi.fn() }))

let wrapper, defaultView, deniedProjects
const bootstrapData = () => ({
  user: { name: 'alex@example.com', full_name: 'Alex', roles: [] },
  settings: { planner_view_default: defaultView }, apps: [], projects: [], errors: {},
  default_company: 'MSS',
  references: { company: [{ name: 'MSS' }, { name: 'DG' }],
    department: [{ name: 'Engineering', company: 'MSS' }, { name: 'Delivery', company: 'DG' }],
    branch: [], designation: [], shift_type: [{ name: 'DS' }], shift_location: [] },
})
const settle = async (ms = 30) => { await flushPromises(); await nextTick(); await vi.advanceTimersByTimeAsync(ms); await flushPromises(); await nextTick() }
const batchCalls = () => wire.send.mock.calls.map(([call]) => call).filter(call => call.url.endsWith('get_planner_data'))

beforeEach(async () => {
  vi.useFakeTimers()
  defaultView = 'Month'
  deniedProjects = false
  Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' })
  wire.send.mockReset().mockImplementation(async ({ url, params }) => {
    if (url.endsWith('get_bootstrap')) {
      const data = bootstrapData()
      if (!params?.sections) return data
      return { sections: params.sections, errors: {}, ...Object.fromEntries(params.sections.map(key => [key, data[key]])) }
    }
    if (url.endsWith('get_planner_data')) return { results: params.requests.map(read => {
      if (read.method === 'frappe.client.get_list') {
        if (deniedProjects && read.params.doctype === 'Project') return { error: { message: 'Project access denied', exc_type: 'PermissionError' } }
        return { data: read.params.doctype === 'Employee' ? [{ name: 'EMP-1', employee_name: 'Alex' }] : [] }
      }
      return { data: {} }
    }) }
    throw new Error(`Unexpected HTTP request: ${url}`)
  })
  setConfig('resourceFetcher', plannerRequest)
})
afterEach(() => { wrapper?.unmount(); document.body.innerHTML = ''; vi.useRealTimers() })

async function open(view) {
  defaultView = view
  // The singleton lasts one page session; reset its data for each simulated visit.
  const bootstrap = usePlannerBootstrap()
  await bootstrap.fetch({})
  bootstrap.reset()
  wire.send.mockClear()
  void bootstrap.fetch({})
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: Home }] })
  await router.push('/'); await router.isReady()
  wrapper = mount(Home, { attachTo: document.body, global: { plugins: [router] } })
  await settle(); await settle()
}

describe('Planner HTTP request budget', () => {
  it.each(['Month', 'Annual'])('loads %s using one bootstrap and one data request, including closed dialogs', async view => {
    await open(view)
    expect(wire.send.mock.calls.map(([call]) => call.url)).toEqual([
      'verto.api.planner_data.get_bootstrap', 'verto.api.planner_data.get_planner_data',
    ])
    const reads = batchCalls()[0].params.requests
    expect(reads.filter(read => read.params.doctype === 'Employee')).toHaveLength(1)
    expect(reads.filter(read => read.params.doctype === 'Project')).toHaveLength(view === 'Month' ? 1 : 0)
    expect(reads.find(read => read.method.includes(view === 'Month' ? 'get_events' : 'get_year_events')).params.employee_filters.company).toBe('MSS')
    expect(wrapper.findAllComponents(ShiftDialog).length).toBeGreaterThanOrEqual(2)
    expect(wrapper.text()).toContain('Alex')
  })

  it('keeps dropdown refreshes from fetching employees and batches a company change once', async () => {
    await open('Month')
    const before = batchCalls().length
    await usePlannerBootstrap().fetch(); await settle()
    expect(batchCalls()).toHaveLength(before)
    const company = wrapper.findComponent(Header).findAllComponents(Combobox).find(c => c.props('label') === 'Company')
    company.vm.$emit('update:modelValue', 'DG'); await settle(); await settle()
    expect(batchCalls()).toHaveLength(before + 1)
    const reads = batchCalls().at(-1).params.requests
    expect(reads.filter(read => read.params.doctype === 'Employee')).toHaveLength(1)
    expect(reads.find(read => read.params.doctype === 'Employee').params.filters.company).toBe('DG')
  })

  it('batches reconnect recovery and applies roster event bursts in one data request', async () => {
    await open('Month')
    wire.send.mockClear()
    wire.socket.receive('connect'); wire.socket.ack(null, { ok: true })
    await settle(700); await settle()
    expect(wire.send).toHaveBeenCalledTimes(2)
    expect(batchCalls()).toHaveLength(1)
    expect(batchCalls()[0].params.requests).toHaveLength(3)
    wire.send.mockClear()
    for (let i = 0; i < 50; i++) wire.socket.receive('verto:planner_changed', { scope: 'roster' })
    await settle(700); await settle()
    expect(wire.send).toHaveBeenCalledOnce()
    expect(batchCalls()[0].params.requests).toHaveLength(1)
  })

  it('keeps employees visible when the project dataset is denied', async () => {
    deniedProjects = true
    await open('Month')
    expect(wire.send).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('Alex')
    expect(raiseToast).toHaveBeenCalledWith('error', 'Project access denied')
  })

  it('refreshes only project choices for project changes and preserves selected filters', async () => {
    await open('Month')
    wire.send.mockClear()
    wire.socket.receive('verto:planner_changed', { scope: 'projects' })
    await settle(700); await settle()
    const bootstrapCall = wire.send.mock.calls.map(([call]) => call).find(call => call.url.endsWith('get_bootstrap'))
    expect(bootstrapCall.params.sections).toEqual(['projects'])
    expect(batchCalls()).toHaveLength(1)
    expect(batchCalls()[0].params.requests.some(read => read.params.doctype === 'Employee')).toBe(false)
    const company = wrapper.findComponent(Header).findAllComponents(Combobox).find(c => c.props('label') === 'Company')
    expect(company.props('modelValue')).toBe('MSS')
    expect(company.props('options')).toEqual(['MSS', 'DG'])
  })
})
