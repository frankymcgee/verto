import { beforeEach, afterEach, describe, it, expect, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const script = readFileSync(resolve(root, 'verto/verto/page/internal_timesheet_approval/internal_timesheet_approval.js'), 'utf8')
const listScript = readFileSync(resolve(root, 'verto/public/js/internal-timesheet-approval-list.js'), 'utf8')
const dates = ['2026-10-05', '2026-10-06', '2026-10-07', '2026-10-08', '2026-10-09', '2026-10-10', '2026-10-11']
let calls, view, context
const find = name => document.querySelector(`[data-${name}]`)
const row = (name, options = {}) => {
  const result = {
    name, employee_name: name === 'CLEAN' ? 'Advisor' : 'Night Worker', role: 'Safety Advisor', docstatus: 0,
    internal_approved: false, can_approve: true, flag_count: 0, flags: [], total: 12, review_hash: 'hash-' + name,
    days: Object.fromEntries(dates.map(date => [date, { ds: date === dates[0] ? 12 : 0, ns: 0, flag_count: 0, allocations: ['NS'] }])),
    entries: [{ date: dates[0], from_time: '2026-10-05 06:00', to_time: '2026-10-05 18:00', hours: 12,
      allocated_shift: 'NS', allocated_kind: 'NS', declared_shift: 'DS', recorded_shift: 'DS', allocation: 'SHIFT-1',
      comments: 'Checked scaffold', daily_comments: 'Checked scaffold; extra detail', daily_timesheet: 'DAILY-1', flags: [] }],
    ...options,
  }
  return result
}
const dataset = () => ({
  timesheet_count: 4, pending_count: 3, flagged_count: 1, signer_name: 'Office Manager', today: '2026-10-13',
  groups: [{ project: 'PROJ-1', project_name: 'Shutdown', week_start: dates[0], week_end: dates[6], dates, total: 48, rows: [
    row('CLEAN'), row('FLAGGED', { flag_count: 1, flags: [{ code: 'allocation_time_mismatch', message: 'Allocated NS but entered times are DS.' }] }),
    row('APPROVED', { internal_approved: true, approved_by: 'Original approver' }), row('READONLY', { can_approve: false }),
  ] }],
})
function load(data = dataset()) { calls.at(-1).callback({ message: data }) }
function chooseType() {
  const input = document.querySelector('input[name="internal-signature-mode"][value="type"]')
  input.checked = true
  input.dispatchEvent(new Event('change', { bubbles: true }))
}

beforeEach(() => {
  calls = []
  document.body.innerHTML = ''
  context = { clearRect: vi.fn(), beginPath: vi.fn(), arc: vi.fn(), fill: vi.fn(), moveTo: vi.fn(), lineTo: vi.fn(), stroke: vi.fn(), fillText: vi.fn(), measureText: () => ({ width: 200 }) }
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(context)
  vi.spyOn(HTMLCanvasElement.prototype, 'toDataURL').mockReturnValue('data:image/png;base64,TEST')
  vi.stubGlobal('__', value => value)
  vi.stubGlobal('frappe', {
    pages: { 'internal-timesheet-approval': {} }, session: { user: 'manager@example.test' }, user_roles: ['HR Manager'],
    datetime: { get_today: () => '2026-10-13' }, route_options: null, listview_settings: {}, set_route: vi.fn(), msgprint: vi.fn(),
    show_alert: vi.fn(), call: options => calls.push(options),
    ui: { make_app_page: () => ({ body: document.body }), form: { make_control: () => ({ get_value: () => '' }) } },
  })
  new Function(script)()
  const wrapper = {}
  frappe.pages['internal-timesheet-approval'].on_page_load(wrapper)
  view = wrapper.internal_review
  frappe.pages['internal-timesheet-approval'].on_page_show(wrapper)
})
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); document.body.innerHTML = '' })

describe('Consolidated internal Timesheet review', () => {
  it('loads the previous Monday and selects only clean, pending, writable records', () => {
    expect(calls[0].args.week_start).toBe('2026-10-05')
    load()
    expect(document.querySelector('[data-timesheet="CLEAN"]').checked).toBe(true)
    expect(document.querySelector('[data-timesheet="FLAGGED"]').checked).toBe(false)
    expect(document.querySelector('[data-timesheet="APPROVED"]').disabled).toBe(true)
    expect(document.querySelector('[data-timesheet="READONLY"]').disabled).toBe(true)
    expect(find('selected').textContent).toContain('1 selected')
    expect(document.body.textContent).toContain('Allocated NS but entered times are DS.')
    expect(document.body.textContent).toContain('Current daily comments:')
    expect(document.body.textContent).toContain('Checked scaffold; extra detail')
  })

  it('requires explicit acknowledgment and a reason for selected flagged timesheets', () => {
    load(); chooseType(); find('select-all').click(); find('approve').click()
    expect(calls).toHaveLength(1)
    expect(find('status').textContent).toContain('enter a review note')
    find('acknowledge').checked = true
    find('review-note').value = 'Verified overtime and allocation correction with supervisor'
    find('approve').click()
    expect(calls).toHaveLength(2)
    expect(calls[1].type).toBe('POST')
    expect(calls[1].args.selections.map(row => row.name)).toEqual(['CLEAN', 'FLAGGED'])
    expect(calls[1].args.review_timesheets).toEqual(['CLEAN', 'FLAGGED', 'APPROVED', 'READONLY'])
    expect(calls[1].args.signature_mode).toBe('type')
    expect(calls[1].args.acknowledge_flags).toBe(1)
    expect(context.fillText).toHaveBeenCalledWith('Office Manager', 400, 120)
  })

  it('requires drawn ink, supports drawn signing and prevents duplicate submissions', () => {
    load(); find('approve').click()
    expect(calls).toHaveLength(1)
    const canvas = find('canvas')
    canvas.getBoundingClientRect = () => ({ left: 0, top: 0, width: 800, height: 240 })
    canvas.dispatchEvent(new PointerEvent('pointerdown', { clientX: 20, clientY: 30, pointerId: 1 }))
    find('approve').click(); find('approve').click()
    expect(calls).toHaveLength(2)
    expect(calls[1].args.signature_mode).toBe('draw')
    expect(calls[1].args.selections).toEqual([{ name: 'CLEAN', review_hash: 'hash-CLEAN' }])
    expect(find('load').disabled).toBe(true)
  })

  it('reloads the recorded approvals after success and preserves input on a stale-review error', () => {
    load(); chooseType(); find('approve').click()
    calls[1].error({ responseJSON: { exception: 'ValidationError: Timesheet has changed. Reload before signing.' } })
    expect(find('status').textContent).toContain('has changed')
    expect(find('approve').disabled).toBe(false)
    expect(find('name').value).toBe('Office Manager')
    find('approve').click()
    calls[2].callback({ message: { status: 'Approved', approved: ['CLEAN'], skipped: [] } })
    expect(calls[3].method).toBe('verto.api.internal_timesheet_approval.get_internal_timesheet_review')
    expect(frappe.show_alert).toHaveBeenCalledOnce()
  })

  it('renders employee names, comments and flag messages as text without executing markup', () => {
    const data = dataset()
    data.groups[0].rows[0].employee_name = 'Worker <img src=x onerror=alert(1)>'
    data.groups[0].rows[0].entries[0].comments = '<script>alert(1)</script>'
    data.groups[0].rows[1].flags[0].message = '<img src=x onerror=alert(2)>'
    load(data)
    expect(document.querySelector('img,script')).toBeNull()
    expect(document.body.textContent).toContain('Worker <img')
    expect(document.body.textContent).toContain('<script>alert(1)</script>')
  })

  it('keeps exact selections from the list and can switch back to the whole week', () => {
    load()
    frappe.route_options = { timesheets: ['CLEAN', 'FLAGGED'] }
    view.show()
    expect(calls[1].args.timesheets).toEqual(['CLEAN', 'FLAGGED'])
    load(); find('load').click()
    expect(calls[2].args.timesheets).toBeUndefined()
    expect(calls[2].args.week_start).toBe('2026-10-05')
  })
})

describe('Existing Timesheet list actions', () => {
  it('adds review actions after the site Client Script while preserving its onload', async () => {
    new Function(listScript)()
    const old = vi.fn()
    frappe.listview_settings.Timesheet = { onload: old }
    await Promise.resolve()
    const list = { page: { add_inner_button: vi.fn(), add_action_item: vi.fn() }, get_checked_items: () => [{ name: 'CLEAN' }] }
    frappe.listview_settings.Timesheet.onload(list)
    expect(old).toHaveBeenCalledWith(list)
    expect(list.page.add_inner_button.mock.calls[0][0]).toBe('Internal Review')
    list.page.add_action_item.mock.calls[0][1]()
    expect(frappe.route_options).toEqual({ timesheets: ['CLEAN'] })
    expect(frappe.set_route).toHaveBeenCalledWith('internal-timesheet-approval')
  })
})
