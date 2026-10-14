import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { apiRequest } from '../src/lib/api'
import JhaFieldwork from '../src/components/JhaFieldwork.vue'
import JhaWorkpack from '../src/pages/JhaWorkpack.vue'

vi.mock('../src/lib/api', () => ({ apiRequest: vi.fn() }))
vi.mock('vue-router', () => ({ useRoute: () => ({ params: { jhaName: 'JHA-1' }, query: { revision: '1' } }) }))
let wrapper, fieldwork
const originalOnline = Object.getOwnPropertyDescriptor(navigator, 'onLine')
const originalVisibility = Object.getOwnPropertyDescriptor(document, 'visibilityState')
const button = text => wrapper.findAll('button').find(item => item.text() === text)
const jha = { name: 'JHA-1', revision: 1, status: 'Signed' }
beforeEach(() => {
  vi.clearAllMocks()
  Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
  fieldwork = { name: 'JHA-1', revision: 1, today: '2026-10-14', can_verify: true, can_revalidate: true,
    controls: [{ name: 'H-1', step: 1, control: 'Mechanical restraint', owner: 'Supervisor', status: 'Pending', history: [] }],
    ccv_options: [{ name: 'CCV-1', ccv_selected: 'Uncontrolled Release of Energy', safety_category: 'Good Controls' }], shift_reviews: [] }
  apiRequest.mockImplementation(async url => {
    if (url.includes('get_jha_fieldwork')) return { message: structuredClone(fieldwork) }
    if (url.includes('record_jha_control_verification')) return { message: { name: 'CHECK-1' } }
    if (url.includes('upload_file')) return { message: { file_url: '/private/files/checked-restraint.jpg' } }
    if (url.includes('confirm_jha_shift_review')) return { message: { name: 'SHIFT-1', jha: 'JHA-1', status: 'No Change' } }
    throw Error(`Unexpected request: ${url}`)
  })
})
afterEach(() => {
  wrapper?.unmount(); wrapper = null; vi.restoreAllMocks()
  if (originalOnline) Object.defineProperty(navigator, 'onLine', originalOnline)
  else Reflect.deleteProperty(navigator, 'onLine')
  if (originalVisibility) Object.defineProperty(document, 'visibilityState', originalVisibility)
  else Reflect.deleteProperty(document, 'visibilityState')
})

describe('JHA field checks', () => {
  it('requires a human confirmation and sends the exact revision hazard with its CCV and evidence', async () => {
    wrapper = mount(JhaFieldwork, { props: { jha } }); await flushPromises()
    await button('Record field check').trigger('click')
    expect(button('Save field check').attributes('disabled')).toBeDefined()
    await wrapper.findAll('select')[1].setValue('CCV-1')
    await wrapper.find('textarea').setValue('Restraint checked in place')
    const file = wrapper.find('input[type=file]')
    Object.defineProperty(file.element, 'files', { configurable: true, value: [new File(['photo'], 'restraint.jpg', { type: 'image/jpeg' })] })
    await file.trigger('change'); await flushPromises()
    const upload = apiRequest.mock.calls.find(([url]) => url.includes('upload_file'))[1].body
    expect(upload.get('is_private')).toBe('1')
    expect(upload.get('docname')).toBe('JHA-1')
    await wrapper.find('input[type=checkbox]').setValue(true)
    await wrapper.find('form').trigger('submit'); await flushPromises()
    const [, options] = apiRequest.mock.calls.find(([url]) => url.includes('record_jha_control_verification'))
    expect(Object.fromEntries(options.body)).toMatchObject({ jha_name: 'JHA-1', hazard_row: 'H-1', ccv: 'CCV-1', result: 'Verified', confirmation: '1', evidence: '/private/files/checked-restraint.jpg' })
    expect(options.body.get('request_id')).toBeTruthy()
    expect(options.body.has('verified_by')).toBe(false)
    expect(apiRequest.mock.calls.filter(([url]) => url.includes('get_jha_fieldwork')).every(([, options]) => options.cache === 'no-store')).toBe(true)
  })
  it('shows failed control alerts and keeps server rejections visible', async () => {
    fieldwork.controls[0].status = 'Failed'
    wrapper = mount(JhaFieldwork, { props: { jha } }); await flushPromises()
    expect(wrapper.find('[role=alert]').text()).toContain('Hold affected work')
    await button('Record field check').trigger('click')
    await wrapper.find('input[type=checkbox]').setValue(true)
    apiRequest.mockRejectedValueOnce(Error('CCV has an unanswered check'))
    await wrapper.find('form').trigger('submit'); await flushPromises()
    expect(wrapper.text()).toContain('CCV has an unanswered check')
  })
  it('starts a shift review and routes detected changes through a human action', async () => {
    fieldwork.shift_reviews = [{ name: 'SHIFT-1', jha: 'JHA-1', shift_date: '2026-10-14', shift: 'Night', status: 'Change Required', checks: { equipment: { changed: true, notes: 'Different crane' } } }]
    wrapper = mount(JhaFieldwork, { props: { jha } }); await flushPromises()
    await wrapper.find('form').trigger('submit')
    expect(wrapper.emitted('startReview')[0][0]).toEqual({ shift_date: '2026-10-14', shift: 'Day' })
    await button('Review Changes with PERI').trigger('click')
    expect(wrapper.emitted('reviewChanges')[0][0].name).toBe('SHIFT-1')
    expect(button('Confirm No Changes')).toBeUndefined()
  })
  it('requires the on-screen action to confirm a completed no-change discussion', async () => {
    const review = { name: 'SHIFT-1', jha: 'JHA-1', shift_date: '2026-10-14', shift: 'Day', status: 'Awaiting Confirmation', checks: {} }
    wrapper = mount(JhaFieldwork, { props: { jha, voiceReview: review } }); await flushPromises()
    expect(apiRequest.mock.calls.some(([url]) => url.includes('confirm_jha_shift_review'))).toBe(false)
    await button('Confirm No Changes').trigger('click'); await flushPromises()
    expect(wrapper.emitted('reviewUpdated')[0][0]).toMatchObject({ name: 'SHIFT-1', status: 'No Change' })
  })
  it('does not apply a field response from a previously open revision', async () => {
    let resolveOld
    apiRequest.mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve }))
    wrapper = mount(JhaFieldwork, { props: { jha } })
    fieldwork = { ...fieldwork, name: 'JHA-2', controls: [], shift_reviews: [] }
    await wrapper.setProps({ jha: { name: 'JHA-2', revision: 2, status: 'Signed' } }); await flushPromises()
    resolveOld({ message: { ...fieldwork, name: 'JHA-1', controls: [{ name: 'OLD', control: 'Stale control', history: [] }] } }); await flushPromises()
    expect(wrapper.text()).not.toContain('Stale control')
  })
})

describe('printed workpack revision check', () => {
  const status = { requested: { name: 'JHA-1', revision: 1, status: 'Superseded' }, is_current: false, requires_review: true,
    current: { name: 'JHA-2', revision: 2, status: 'Signed', work_summary: 'WS-1', title: 'Pump maintenance' }, controls: [], checked_at: '2026-10-14 10:00' }
  it('warns for old copies and opens the exact current revision', async () => {
    apiRequest.mockResolvedValue({ message: status })
    wrapper = mount(JhaWorkpack); await flushPromises()
    expect(wrapper.text()).toContain('This printed copy is not the current revision')
    expect(wrapper.find('a').attributes('href')).toBe('/verto-mobile/voice-jha/WS-1?jha=JHA-2')
    expect(apiRequest.mock.calls[0][0]).toContain('revision=1')
    expect(apiRequest.mock.calls[0][1].cache).toBe('no-store')
  })
  it('removes a previous live status when a fresh check fails', async () => {
    apiRequest.mockResolvedValueOnce({ message: { ...status, is_current: true, requires_review: false } })
    wrapper = mount(JhaWorkpack); await flushPromises()
    expect(wrapper.text()).toContain('current signed revision')
    apiRequest.mockRejectedValueOnce(Error('Network unavailable'))
    await button('Check again').trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('Current status could not be confirmed')
    expect(wrapper.text()).not.toContain('current signed revision')
    expect(wrapper.find('a').exists()).toBe(false)
  })
  it('does not assert revision status while offline', async () => {
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: false })
    wrapper = mount(JhaWorkpack); await flushPromises()
    expect(apiRequest).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Connect to the internet')
  })
  it('clears a previous result as soon as the connection goes offline', async () => {
    apiRequest.mockResolvedValue({ message: { ...status, is_current: true, requires_review: false } })
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' })
    wrapper = mount(JhaWorkpack); await flushPromises()
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: false })
    window.dispatchEvent(new Event('offline')); await flushPromises()
    expect(wrapper.text()).not.toContain('current signed revision')
    expect(wrapper.text()).toContain('Current status could not be confirmed')
  })
})
