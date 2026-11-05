import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { setConfig } from 'frappe-ui'
import YearViewTable from '../src/components/YearViewTable.vue'
import YearHoverCard from '../src/components/YearHoverCard.vue'
import { dayjs } from '../src/utils'

let wrapper, data, updates
const settle = async () => { await flushPromises(); await nextTick() }
const project = { project: 'PROJ-1', project_name: 'Annual shutdown', customer: 'MSS',
  start_date: '2026-01-01', end_date: '2026-12-31', assignments: {} }

beforeEach(() => {
  vi.useFakeTimers()
  updates = vi.fn()
  data = { project_rows: [project], events: { 'EMP-1': [{ name: 'SHIFT-1', shift_type: 'DS',
    status: 'Active', start_date: '2026-01-01', end_date: '2026-12-31', color: 'blue' }] } }
  setConfig('resourceFetcher', async ({ url }) => url.endsWith('get_year_events') ? structuredClone(data) : [])
})
afterEach(() => { wrapper?.unmount(); document.body.innerHTML = ''; vi.useRealTimers() })

async function open() {
  wrapper = mount(YearViewTable, { attachTo: document.body,
    props: { firstOfMonth: dayjs('2026-01-01'), employees: [{ name: 'EMP-1', employee_name: 'Alex' }],
      employeeFilters: {}, shiftFilters: {}, maxHeightPx: 750 },
    global: { mixins: [{ updated() { if (this.$options.__name === 'YearViewTable') updates() } }] },
  })
  await settle()
  updates.mockClear()
  return wrapper.findAll('.year-roster-scroller').map(node => node.element)
}
function scroll(element, left, top = element.scrollTop) {
  element.scrollLeft = left
  element.scrollTop = top
  element.dispatchEvent(new Event('scroll'))
}

describe('Annual planner scroll and hover performance', () => {
  it.each([0, 1])('keeps fast input from panel %s aligned without dropping events or echoing old positions', async sourceIndex => {
    const panels = await open()
    const source = panels[sourceIndex], peer = panels[1 - sourceIndex]
    scroll(source, 100)
    scroll(source, 240)
    expect(peer.scrollLeft).toBe(240)
    // Browsers deliver the programmatic peer scroll after the source input.
    peer.dispatchEvent(new Event('scroll'))
    await vi.advanceTimersByTimeAsync(32)
    expect(source.scrollLeft).toBe(240)
    scroll(peer, 315.5)
    expect(source.scrollLeft).toBe(315.5)
    scroll(peer, 315.5, 78)
    expect(source.scrollTop).toBe(0)
    expect(source.scrollLeft).toBe(315.5)
    await nextTick()
    expect(updates).not.toHaveBeenCalled()
  })

  it('does not bounce at unequal scrollbar limits, and accepts reverse scrolling from either panel', async () => {
    const [source, peer] = await open()
    let peerLeft = 0
    Object.defineProperty(peer, 'scrollLeft', { configurable: true,
      get: () => peerLeft, set: value => { peerLeft = Math.min(900, Math.max(0, value)) } })
    scroll(source, 917)
    expect(peer.scrollLeft).toBe(900)
    peer.dispatchEvent(new Event('scroll'))
    scroll(peer, 900, 100)
    expect(source.scrollLeft).toBe(917)
    scroll(peer, 700)
    expect(source.scrollLeft).toBe(700)
    scroll(source, 0)
    expect(peer.scrollLeft).toBe(0)
  })

  it('aligns a project panel that arrives after the employee table has already scrolled', async () => {
    data.project_rows = []
    const [employee] = await open()
    scroll(employee, 500)
    data.project_rows = [project]
    await wrapper.vm.events.fetch(); await settle()
    expect(wrapper.find('.year-roster-scroller').element.scrollLeft).toBe(500)
    expect(employee.scrollLeft).toBe(500)
  })

  it('updates and removes hover cards without rerendering the annual grid', async () => {
    await open()
    const cells = wrapper.findAll('.year-employee-row .year-cell')
    await cells[0].trigger('mouseenter', { clientX: 400, clientY: 300 })
    expect(document.querySelector('[role="tooltip"]').textContent).toContain('01 Jan 2026')
    await cells[1].trigger('mouseenter', { clientX: 430, clientY: 300 })
    expect(document.querySelector('[role="tooltip"]').textContent).toContain('02 Jan 2026')
    await cells[1].trigger('mousemove', { clientX: 440, clientY: 310 })
    await vi.advanceTimersByTimeAsync(20)
    expect(document.querySelector('[role="tooltip"]').style.transform).toContain('translate3d(')
    await cells[1].trigger('mouseleave')
    await vi.advanceTimersByTimeAsync(100)
    expect(document.querySelector('[role="tooltip"]')).toBeNull()
    expect(updates).not.toHaveBeenCalled()
  })

  it('cancels pending hover frames and hide timers on unmount', async () => {
    await open()
    const tooltip = wrapper.findComponent(YearHoverCard)
    const cell = wrapper.find('.year-employee-row .year-cell')
    await cell.trigger('mouseenter', { clientX: 400, clientY: 300 })
    await cell.trigger('mouseleave')
    expect(vi.getTimerCount()).toBeGreaterThan(0)
    wrapper.unmount(); wrapper = null
    expect(tooltip.exists()).toBe(false)
    expect(vi.getTimerCount()).toBe(0)
    expect(document.querySelector('[role="tooltip"]')).toBeNull()
  })
})
