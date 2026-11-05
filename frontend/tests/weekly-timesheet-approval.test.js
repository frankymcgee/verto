// @vitest-environment happy-dom
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { resolve, dirname } from 'node:path'

const sourceRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const markup = readFileSync(resolve(sourceRoot, 'verto/templates/timesheets/weekly-timesheet-approval.html'), 'utf8')
const script = readFileSync(resolve(sourceRoot, 'verto/public/js/weekly-timesheet-approval.js'), 'utf8')
let calls
const byId = id => document.getElementById(id)
const hidden = id => byId(id).classList.contains('gta-hidden')
const week = overrides => ({
  project: 'PROJ-1', project_name: 'Shutdown', week_label: '28 Sep - 04 Oct 2026',
  employee_count: 1, signed_count: 0, is_already_signed: false,
  approval_status: 'Awaiting Signature', can_sign: true, can_reject: true,
  dates: [{date: '2026-09-28', day_short: 'Mon', label: '28 Sep'}],
  employees: [{employee_name: 'Advisor', days: {'2026-09-28': {ds: 12, ns: 0}}, total_ds: 12, total_ns: 0, total: 12}],
  day_totals: {'2026-09-28': {ds: 12, ns: 0}}, totals: {ds: 12, ns: 0, total: 12}, ...overrides,
})
function load(data = week()) {
  new Function('frappe', script)({ready: fn => fn(), call: options => calls.push(options)})
  calls[0].callback({message: data})
}
function openRejection(name = 'Client Supervisor', reason = 'Wrong Monday hours') {
  byId('grouped-reject-button').click()
  byId('grouped-rejection-name').value = name
  byId('grouped-rejection-input').value = reason
}
const submit = () => byId('grouped-rejection-form').dispatchEvent(new Event('submit', {cancelable: true, bubbles: true}))
beforeEach(() => {
  calls = []
  document.body.innerHTML = markup
  window.history.replaceState({}, '', '?token=original-token')
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({clearRect() {}, beginPath() {}, arc() {}, fill() {}, moveTo() {}, lineTo() {}, stroke() {}, fillText() {}, measureText: text => ({width: text.length * 20})})
  vi.spyOn(HTMLCanvasElement.prototype, 'toDataURL').mockReturnValue('data:image/png;base64,UE5H')
  byId('grouped-rejection-dialog').showModal = function () {this.open = true}
  byId('grouped-rejection-dialog').close = function () {this.open = false}
})
afterEach(() => vi.restoreAllMocks())
describe('client weekly timesheet decisions', () => {
  it('offers rejection without requiring a signature or signing date', () => {
    load()
    expect(hidden('grouped-reject-button')).toBe(false)
    openRejection('  Client Supervisor  ', '  Wrong Monday hours  ')
    byId('grouped-date-signed').value = ''
    submit()
    expect(calls[1].method).toBe('verto.api.timesheet_approval.reject_grouped_timesheets')
    expect(calls[1].type).toBe('POST')
    expect(calls[1].args).toEqual({token: 'original-token', full_name: 'Client Supervisor', reason: 'Wrong Monday hours'})
  })
  it('requires a nonblank reason and name while keeping the dialog open', () => {
    load()
    openRejection('Client', ' \n ')
    submit()
    expect(calls).toHaveLength(1)
    expect(byId('grouped-rejection-dialog').open).toBe(true)
    expect(byId('grouped-rejection-error').textContent).toContain('rejection reason')
    byId('grouped-rejection-input').value = 'Wrong hours'
    byId('grouped-rejection-name').value = ' '
    submit()
    expect(calls).toHaveLength(1)
  })
  it('prevents competing decisions and repeat clicks while rejection is pending', () => {
    load(); openRejection(); submit(); submit()
    byId('grouped-submit-button').click()
    expect(calls).toHaveLength(2)
    expect(byId('grouped-submit-button').disabled).toBe(true)
    expect(byId('grouped-rejection-cancel').disabled).toBe(true)
    const cancel = new Event('cancel', {cancelable: true})
    byId('grouped-rejection-dialog').dispatchEvent(cancel)
    expect(cancel.defaultPrevented).toBe(true)
  })
  it('reloads the recorded decision and renders the reason as text', () => {
    load(); openRejection(); submit()
    calls[1].callback({message: {status: 'Rejected', message: 'Your reason will be emailed.'}})
    expect(byId('grouped-rejection-dialog').open).toBe(false)
    expect(calls[2].args).toEqual({token: 'original-token'})
    calls[2].callback({message: week({approval_status: 'Rejected', can_sign: false, can_reject: false, rejected_by: 'Client <img>', rejection_reason: 'Wrong hours\n<img src=x onerror=alert(1)>'})})
    expect(hidden('grouped-signature-section')).toBe(true)
    expect(hidden('grouped-download-section')).toBe(true)
    expect(hidden('grouped-rejected-panel')).toBe(false)
    expect(byId('grouped-rejection-reason').textContent).toContain('<img')
    expect(byId('grouped-rejected-panel').querySelector('img')).toBeNull()
    expect(byId('grouped-status-badge').textContent).toBe('Rejected')
  })
  it('keeps entered reasons on failure and allows retry', () => {
    load(); openRejection(); submit()
    calls[1].error({responseJSON: {exception: 'ValidationError: Link has been replaced'}})
    expect(byId('grouped-rejection-error').textContent).toContain('replaced')
    expect(byId('grouped-rejection-input').value).toBe('Wrong Monday hours')
    expect(byId('grouped-rejection-dialog').open).toBe(true)
    expect(byId('grouped-rejection-confirm').disabled).toBe(false)
    submit()
    expect(calls).toHaveLength(3)
  })
  it('shows email failures without offering another rejection', () => {
    load(week({approval_status: 'Rejected', can_sign: false, can_reject: false, notification_failed: true, rejection_reason: 'Wrong hours'}))
    expect(byId('grouped-decision-note').textContent).toContain('email could not be queued')
    expect(hidden('grouped-reject-button')).toBe(true)
  })
  it('replaced links show history and cannot sign or download', () => {
    load(week({approval_status: 'Superseded', can_sign: false, can_reject: false, rejection_reason: 'Prior rejection'}))
    expect(byId('grouped-decision-note').textContent).toContain('latest approval email')
    expect(byId('grouped-rejection-reason').textContent).toBe('Prior rejection')
    expect(hidden('grouped-signature-section')).toBe(true)
    expect(hidden('grouped-download-section')).toBe(true)
    expect(hidden('grouped-reject-button')).toBe(true)
  })
  it('preserves PDF access for signed weeks and approval controls for legacy links', () => {
    load(week({approval_status: 'Signed', is_already_signed: true, can_sign: false, can_reject: false, signed_by: 'Client Supervisor', date_signed: '2026-10-05'}))
    expect(hidden('grouped-signature-section')).toBe(true)
    expect(hidden('grouped-download-section')).toBe(false)
    expect(byId('grouped-signed-panel').textContent).toContain('Client Supervisor')
    calls[0].callback({message: week({can_reject: false})})
    expect(hidden('grouped-signature-section')).toBe(false)
    expect(hidden('grouped-reject-button')).toBe(true)
  })
})
