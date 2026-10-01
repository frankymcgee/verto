import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { setConfig } from 'frappe-ui'
import YearViewTable from '../src/components/YearViewTable.vue'
import MonthViewTable from '../src/components/MonthViewTable.vue'
import { usePlannerBootstrap } from '../src/utils/bootstrap'
import { dayjs } from '../src/utils'

let wrapper, types
const settle = async () => { await flushPromises(); await nextTick() }
const employee = (name, employment_type) => ({ name, employee_name: name, employment_type })
const blue = '#3b82f6'

beforeEach(async () => {
  types = [
    { name: 'Full-time', custom_planner_colour: '#1555cc' },
    { name: 'Casual', custom_planner_colour: '#eab308' },
    { name: 'Sub-contractor', custom_planner_colour: '#9333ea' },
    { name: 'Blank', custom_planner_colour: '' },
    { name: 'Invalid', custom_planner_colour: 'url(https://example.com/colour)' },
  ]
  setConfig('resourceFetcher', async ({ url }) => {
    if (url.endsWith('get_bootstrap')) return { references: { employment_type: structuredClone(types) }, projects: [] }
    if (url.endsWith('get_year_events') || url.endsWith('get_events')) return {}
    if (url === 'frappe.client.get_list') return []
    throw new Error(`Unexpected request: ${url}`)
  })
  await usePlannerBootstrap().fetch({ sections: ['references'] })
})
afterEach(() => { wrapper?.unmount(); document.body.innerHTML = '' })

async function open(component, employees) {
  wrapper = mount(component, { attachTo: document.body,
    props: { firstOfMonth: dayjs('2026-01-01'), employees, employeeFilters: {}, shiftFilters: {} },
  })
  await settle()
}

function rowCells(component) {
  return wrapper.findAll(component === YearViewTable ? '.year-employee-name-cell' : 'tbody tr > td:first-child')
}

describe('Employment Type employee colours', () => {
  it.each([['annual', YearViewTable], ['monthly', MonthViewTable]])('uses configured colours in the %s roster and blue for absent or invalid colours', async (_view, component) => {
    await open(component, ['Full-time', 'Casual', 'Sub-contractor', 'Blank', 'Invalid', 'Missing', null]
      .map((type, i) => employee(`EMP-${i}`, type)))
    expect(rowCells(component).map(cell => cell.element.style.boxShadow)).toEqual(
      ['#1555cc', '#eab308', '#9333ea', blue, blue, blue, blue].map(colour => `inset 4px 0 0 ${colour}`),
    )
  })

  it('keeps the open employee hover and row matched when a colour is changed or cleared', async () => {
    await open(YearViewTable, [employee('EMP-1', 'Casual')])
    const cell = wrapper.find('.year-employee-name-cell')
    await cell.trigger('mouseenter', { clientX: 400, clientY: 300 })
    const accent = () => document.querySelector('[role="tooltip"]').style.getPropertyValue('--year-hover-accent')
    expect(accent()).toBe('#eab308')
    expect(document.querySelector('[role="tooltip"]').textContent).toContain('Casual')
    types[1].custom_planner_colour = '#f97316'
    await usePlannerBootstrap().fetch({ sections: ['references'] }); await settle()
    expect(cell.element.style.boxShadow).toContain('#f97316')
    expect(accent()).toBe('#f97316')
    types[1].custom_planner_colour = ''
    await usePlannerBootstrap().fetch({ sections: ['references'] }); await settle()
    expect(cell.element.style.boxShadow).toContain(blue)
    expect(accent()).toBe(blue)
  })

  it('uses the current employment type when an employee record is refreshed', async () => {
    await open(YearViewTable, [employee('EMP-1', 'Full-time')])
    const cell = wrapper.find('.year-employee-name-cell')
    await cell.trigger('mouseenter', { clientX: 400, clientY: 300 })
    await wrapper.setProps({ employees: [employee('EMP-1', 'Sub-contractor')] })
    const tooltip = document.querySelector('[role="tooltip"]')
    expect(cell.element.style.boxShadow).toContain('#9333ea')
    expect(tooltip.style.getPropertyValue('--year-hover-accent')).toBe('#9333ea')
    expect(tooltip.textContent).toContain('Sub-contractor')
  })
})
