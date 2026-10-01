import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { setConfig } from 'frappe-ui'
import YearViewTable from '../src/components/YearViewTable.vue'
import MonthViewTable from '../src/components/MonthViewTable.vue'
import PlannerTableSurface from '../src/components/PlannerTableSurface.vue'
import ProjectSpanDialog from '../src/components/ProjectSpanDialog.vue'
import ShiftAssignmentDialog from '../src/components/ShiftAssignmentDialog.vue'
import LeaveApplicationDialog from '../src/components/LeaveApplicationDialog.vue'
import { dayjs } from '../src/utils'

let wrapper, project, events, gridUpdates
const employees = [{ name: 'EMP-DIALOG', employee_name: 'Alex' }]
const settle = async () => { await flushPromises(); await nextTick() }

beforeEach(() => {
  gridUpdates = vi.fn()
  project = { project: 'PROJ-DIALOG', project_name: 'Test project', customer: 'MSS',
    custom_project_location: 'Mine', start_date: '2026-01-01', end_date: '2026-12-31', assignments: {} }
  events = { 'EMP-DIALOG': [
    { name: 'SHIFT-DIALOG', shift_type: 'DS', status: 'Active', start_date: '2026-01-01', end_date: '2026-01-01', color: 'blue' },
    { leave: 'LEAVE-DIALOG', leave_type: 'Annual Leave', from_date: '2026-01-02', to_date: '2026-01-02', status: 'Approved' },
  ] }
  setConfig('resourceFetcher', async ({ url }) => {
    if (url.endsWith('get_year_events')) return structuredClone({ events, project_rows: [project] })
    if (url.endsWith('get_events')) return structuredClone(events)
    if (url.endsWith('get_project_planner_details')) return structuredClone({ ...project, execution_tasks: [] })
    if (url.endsWith('planner_leave.get_details')) return { name: 'LEAVE-DIALOG', fields: [], values: {}, docstatus: 1, status: 'Approved' }
    if (url.endsWith('get_values')) return { employee_name: 'Alex', company: 'MSS', department: 'Operations' }
    if (url === 'frappe.client.get') return { name: 'SHIFT-DIALOG', employee: 'EMP-DIALOG', employee_name: 'Alex',
      start_date: '2026-01-01', end_date: '2026-01-01', shift_type: 'DS', status: 'Active' }
    if (url === 'frappe.client.get_list') return []
    if (url.endsWith('get_bootstrap')) return { references: { shift_type: [{ name: 'DS' }], shift_location: [], designation: [] }, projects: [] }
    throw new Error(`Unexpected request: ${url}`)
  })
})
afterEach(() => { wrapper?.unmount(); document.body.innerHTML = ''; vi.restoreAllMocks() })

async function open(component = YearViewTable) {
  wrapper = mount(component, { attachTo: document.body,
    props: { firstOfMonth: dayjs('2026-01-01'), employees, employeeFilters: {}, shiftFilters: {}, maxHeightPx: 750 },
    global: { mixins: [{ updated() { if (this.$.type === PlannerTableSurface) gridUpdates() } }] },
  })
  await settle()
  gridUpdates.mockClear()
}

describe('Planner dialog rendering', () => {
  it.each([
    ['project details', '.year-project-span', ProjectSpanDialog],
    ['new shift', '.year-employee-row .year-cell:nth-child(4)', ShiftAssignmentDialog],
    ['existing shift', '.year-employee-row .year-cell:nth-child(2)', ShiftAssignmentDialog],
    ['existing leave', '.year-employee-row .year-cell:nth-child(3)', LeaveApplicationDialog],
  ])('opens and closes %s without rebuilding the annual tables', async (_label, selector, component) => {
    await open()
    const scrollers = wrapper.findAll('.year-roster-scroller').map(node => node.element)
    scrollers[0].scrollLeft = 840
    scrollers[0].dispatchEvent(new Event('scroll'))
    const employeeCell = wrapper.find('.year-employee-name-cell').element
    await wrapper.find(selector).trigger('click'); await settle()
    const dialog = wrapper.findComponent(component)
    expect(dialog.props('modelValue')).toBe(true)
    expect(document.querySelector('[role="dialog"]')).not.toBeNull()
    expect(wrapper.find('.year-employee-name-cell').element).toBe(employeeCell)
    expect(gridUpdates).not.toHaveBeenCalled()
    dialog.vm.$emit('update:modelValue', false)
    await settle()
    expect(dialog.props('modelValue')).toBe(false)
    expect(gridUpdates).not.toHaveBeenCalled()
    expect(scrollers.map(scroller => scroller.scrollLeft)).toEqual([840, 840])
  })

  it('still renders employee and roster data changes while a dialog is open', async () => {
    await open()
    await wrapper.find('.year-project-span').trigger('click'); await settle()
    await wrapper.setProps({ employees: [{ ...employees[0], employee_name: 'Alex Updated' }] })
    expect(wrapper.find('.year-employee-name-cell').text()).toContain('Alex Updated')
    events['EMP-DIALOG'][0].shift_type = 'NS'
    await wrapper.vm.events.fetch(); await settle()
    expect(wrapper.find('.year-employee-row .year-cell').attributes('aria-label')).toContain('NS')
    expect(gridUpdates).toHaveBeenCalled()
    expect(wrapper.findComponent(ProjectSpanDialog).props('modelValue')).toBe(true)
  })

  it('keeps the monthly grid stable when opening and closing its leave dialog', async () => {
    await open(MonthViewTable)
    await wrapper.find('button.blocked-cell').trigger('click'); await settle()
    const dialog = wrapper.findComponent(LeaveApplicationDialog)
    expect(dialog.props('modelValue')).toBe(true)
    expect(gridUpdates).not.toHaveBeenCalled()
    dialog.vm.$emit('update:modelValue', false); await settle()
    expect(gridUpdates).not.toHaveBeenCalled()
  })
})
