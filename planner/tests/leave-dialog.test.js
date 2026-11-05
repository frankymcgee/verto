import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'
import { Combobox, setConfig } from 'frappe-ui'
import LeaveApplicationDialog from '../src/components/LeaveApplicationDialog.vue'
import MonthViewTable from '../src/components/MonthViewTable.vue'
import { dayjs } from '../src/utils'

vi.mock('../src/utils', async original => ({ ...await original(), raiseToast: vi.fn() }))
let wrapper, details, requests, failSave
const settle = async () => { await flushPromises(); await nextTick() }
const button = label => new DOMWrapper([...document.querySelectorAll('button')].find(el => el.textContent.trim() === label))
const field = label => new DOMWrapper(document.querySelector(`[aria-label="${label}"]`))
const fields = [
  { fieldname: 'employee', fieldtype: 'Link', label: 'Employee', options: 'Employee', reqd: 1 },
  { fieldname: 'leave_type', fieldtype: 'Link', label: 'Leave Type', options: 'Leave Type', reqd: 1 },
  { fieldname: 'from_date', fieldtype: 'Date', label: 'From Date', reqd: 1 },
  { fieldname: 'to_date', fieldtype: 'Date', label: 'To Date', reqd: 1 },
  { fieldname: 'description', fieldtype: 'Small Text', label: 'Reason' },
  { fieldname: 'status', fieldtype: 'Select', label: 'Status', options: 'Open\nApproved\nRejected\nCancelled' },
  { fieldname: 'follow_via_email', fieldtype: 'Check', label: 'Follow via Email', default: 1 },
  { fieldname: 'total_leave_days', fieldtype: 'Float', label: 'Total Leave Days', read_only: true },
]
beforeEach(() => {
  requests = []; failSave = false
  details = {
    name: 'LEAVE-1', modified: 'revision-one', docstatus: 0, status: 'Open',
    can_write: true, can_submit: true, can_cancel: false, workflow_actions: [], fields: structuredClone(fields),
    values: { employee: 'EMP-1', leave_type: 'Annual Leave', from_date: '2026-09-10', to_date: '2026-09-12',
      description: 'Original reason', status: 'Open', follow_via_email: 1, total_leave_days: 3 },
  }
  setConfig('resourceFetcher', async ({ url, params }) => {
    requests.push({ url, params })
    if (url.endsWith('get_details')) return structuredClone(details)
    if (url.endsWith('get_leave_application_create_meta')) return { fields: structuredClone(fields.filter(f => !f.read_only)), can_submit: false }
    if (url.endsWith('search_leave_application_link_options')) return [{ value: 'EMP-1', label: 'Alex' }]
    if (url.endsWith('planner_leave.update')) {
      if (failSave) throw new Error('This Leave Application changed elsewhere. Reload it before saving.')
      return { name: 'LEAVE-1' }
    }
    if (url.endsWith('create_planner_leave_application')) return { name: 'LEAVE-NEW' }
    if (url.endsWith('get_events')) return { 'EMP-1': [{ leave: 'LEAVE-1', leave_type: 'Annual Leave', from_date: '2026-09-10', to_date: '2026-09-12' }] }
    throw new Error(`Unexpected request: ${url}`)
  })
})
afterEach(() => { wrapper?.unmount(); document.body.innerHTML = ''; vi.restoreAllMocks() })
async function open(props = {}) {
  wrapper = mount(LeaveApplicationDialog, { attachTo: document.body,
    props: { modelValue: true, isDialogOpen: true, leaveApplicationName: 'LEAVE-1', ...props } })
  await settle()
}

describe('Planner Leave Application dialog', () => {
  it('loads lazily, preserves the saved dates and updates the existing record', async () => {
    await open({ modelValue: false, isDialogOpen: false })
    expect(requests).toHaveLength(0)
    await wrapper.setProps({ modelValue: true, isDialogOpen: true }); await settle()
    expect(field('From Date').element.value).toBe('2026-09-10')
    expect(field('To Date').element.value).toBe('2026-09-12')
    expect(field('Reason').element.value).toBe('Original reason')
    expect(field('Total Leave Days').attributes('disabled')).toBeDefined()
    await field('Reason').setValue('Updated reason')
    await button('Save Changes').trigger('click'); await settle()
    expect(requests.find(r => r.url.endsWith('planner_leave.update')).params).toMatchObject({
      name: 'LEAVE-1', expected_modified: 'revision-one', action: 'save', values: { description: 'Updated reason' },
    })
    expect(wrapper.emitted('fetchEvents')).toHaveLength(1)
    expect(wrapper.emitted('update:modelValue').at(-1)).toEqual([false])
    expect(requests.some(r => r.url.includes('create_planner_leave'))).toBe(false)
  })
  it('clears optional values and retains edits when a stale save fails', async () => {
    await open(); await field('Reason').setValue(''); failSave = true
    await button('Save Changes').trigger('click'); await settle()
    expect(requests.find(r => r.url.endsWith('planner_leave.update')).params.values).toEqual({ description: '' })
    expect(field('Reason').element.value).toBe('')
    expect(document.body.textContent).toContain('changed elsewhere')
    expect(wrapper.emitted('fetchEvents')).toBeUndefined()
    details.modified = 'revision-two'; details.values.description = 'Updated by another planner'
    await button('Discard edits and reload').trigger('click'); await settle()
    expect(field('Reason').element.value).toBe('Updated by another planner')
  })
  it.each([1, 2])('respects field restrictions for docstatus %s', async docstatus => {
    details.docstatus = docstatus; details.can_submit = false; details.can_write = docstatus === 1; details.can_cancel = docstatus === 1
    details.status = docstatus === 1 ? 'Approved' : 'Cancelled'; details.values.status = details.status
    details.fields.forEach(f => { f.read_only = docstatus === 2 || f.fieldname !== 'follow_via_email' })
    await open()
    expect(field('From Date').attributes('disabled')).toBeDefined()
    expect(field('Reason').attributes('disabled')).toBeDefined()
    if (docstatus === 2) {
      expect(document.body.textContent).not.toContain('Save Changes')
      expect(document.body.textContent).not.toContain('Cancel Leave Application')
    } else {
      await button('Cancel Leave Application').trigger('click'); await settle()
      expect(requests.some(r => r.url.endsWith('planner_leave.update'))).toBe(false)
      await button('Confirm Cancellation').trigger('click'); await settle()
      expect(requests.find(r => r.url.endsWith('planner_leave.update')).params).toMatchObject({ name: 'LEAVE-1', action: 'cancel', values: {} })
    }
  })
  it('uses workflow actions supplied by the server', async () => {
    details.workflow_actions = ['Approve request']; details.can_submit = false; details.can_write = false
    details.fields.forEach(f => { f.read_only = true })
    await open(); await button('Approve request').trigger('click'); await settle()
    await button('Confirm Approve request').trigger('click'); await settle()
    expect(requests.find(r => r.url.endsWith('planner_leave.update')).params).toMatchObject({ action: 'workflow', workflow_action: 'Approve request', values: {} })
  })
  it('preserves the creation path and defaults for an employee', async () => {
    await open({ leaveApplicationName: '' })
    expect(field('From Date').element.value).toBe(dayjs().format('YYYY-MM-DD'))
    const combos = wrapper.findAllComponents(Combobox)
    combos.find(c => c.props('placeholder') === 'Search Employee').vm.$emit('update:modelValue', 'EMP-1')
    combos.find(c => c.props('placeholder') === 'Search Leave Type').vm.$emit('update:modelValue', 'Annual Leave')
    await settle(); await button('Create Leave Application').trigger('click'); await settle()
    expect(requests.find(r => r.url.endsWith('create_planner_leave_application')).params.values).toMatchObject({ employee: 'EMP-1', leave_type: 'Annual Leave', status: 'Open', follow_via_email: true })
  })
  it('shows a failed load without stale fields or a save button', async () => {
    setConfig('resourceFetcher', async () => { throw new Error('Not permitted to view this request') })
    await open()
    expect(document.body.textContent).toContain('Not permitted')
    expect(document.querySelector('[aria-label="Reason"]')).toBeNull()
    expect(document.body.textContent).not.toContain('Save Changes')
  })
  it('opens the monthly roster leave in a planner dialog', async () => {
    const openWindow = vi.spyOn(window, 'open').mockReturnValue(null)
    wrapper = mount(MonthViewTable, { attachTo: document.body,
      props: { firstOfMonth: dayjs('2026-09-01'), employees: [{ name: 'EMP-1', employee_name: 'Alex' }], employeeFilters: {}, shiftFilters: {} } })
    await settle(); await wrapper.find('button.blocked-cell').trigger('click'); await settle()
    expect(wrapper.findComponent(LeaveApplicationDialog).props('leaveApplicationName')).toBe('LEAVE-1')
    expect(field('Reason').element.value).toBe('Original reason')
    expect(openWindow).not.toHaveBeenCalled()
  })
})
