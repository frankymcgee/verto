import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { apiRequest } from '../src/lib/api'
import JhaStepResources from '../src/components/JhaStepResources.vue'
import JhaJobLearning from '../src/components/JhaJobLearning.vue'
import JhaPhotoMarkers from '../src/components/JhaPhotoMarkers.vue'
import JhaOfflineCopy from '../src/components/JhaOfflineCopy.vue'
import { readOfflineJha, pendingJhaObservations, saveJhaObservation } from '../src/pwa/offlineJha'

vi.mock('../src/lib/api', () => ({ apiRequest: vi.fn() }))
vi.mock('../src/pwa/offlineJha', () => ({ readOfflineJha: vi.fn(), downloadOfflineJha: vi.fn(), pendingJhaObservations: vi.fn(), saveJhaObservation: vi.fn() }))
let wrapper, resources, learning
const originalOnline = Object.getOwnPropertyDescriptor(navigator, 'onLine')
const jha = { name: 'JHA-1', revision: 3, status: 'Signed', work_summary_title: 'Pump restraint', work_steps: [{ name: 'STEP-1', sequence: 1, activity: 'Restrain pump' }] }
const button = text => wrapper.findAll('button').find(item => item.text() === text)
beforeEach(() => {
  vi.clearAllMocks()
  Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
  resources = { can_record: true, items: [{ name: 'REF-1', kind: 'Permit', step_row: 'STEP-1', work_step: 1,
    reference: 'PERMIT-123', details: 'Check access', status: 'Confirmed', effective_status: 'Expired', annotations: [], recorded_by: 'viewer' }], earlier_observations: [] }
  learning = { can_select: true, can_propose: false, can_closeout: true, can_review: false,
    templates: [{ name: 'TEMPLATE-1', title: 'Pump restraint', jha: 'OLD-JHA', status: 'Approved', content: { steps: jha.work_steps, hazards: [] } }], closeouts: [], lessons: [] }
  apiRequest.mockImplementation(async url => {
    if (url.includes('get_jha_resources')) return { message: structuredClone(resources) }
    if (url.includes('record_jha_resource')) return { message: { name: 'REF-2', jha_status: 'Review Required - Work Changed' } }
    if (url.includes('upload_file')) return { message: { file_url: '/private/files/pump.png' } }
    if (url.includes('get_jha_job_learning')) return { message: structuredClone(learning) }
    return { message: { name: 'NEW-RECORD' } }
  })
  readOfflineJha.mockResolvedValue(null); pendingJhaObservations.mockResolvedValue([])
})
afterEach(() => {
  wrapper?.unmount(); wrapper = null; vi.restoreAllMocks()
  if (originalOnline) Object.defineProperty(navigator, 'onLine', originalOnline)
  else Reflect.deleteProperty(navigator, 'onLine')
})

describe('step supporting records', () => {
  it('shows expiry, pending confirmations and the exact linked step', async () => {
    wrapper = mount(JhaStepResources, { props: { jha } }); await flushPromises()
    expect(wrapper.text()).toContain('1 confirmations outstanding')
    expect(wrapper.text()).toContain('Step 1 · Permit · PERMIT-123')
    expect(wrapper.text()).toContain('Expired')
    expect(apiRequest.mock.calls[0][1].cache).toBe('no-store')
  })
  it('requires human confirmation and saves step-specific fields without signing the JHA', async () => {
    wrapper = mount(JhaStepResources, { props: { jha } }); await flushPromises()
    await button('Add Supporting Record').trigger('click')
    expect(button('Save Record').attributes('disabled')).toBeDefined()
    await wrapper.find('input[maxlength="140"]').setValue('PERMIT-456')
    await wrapper.find('textarea').setValue('Different access permit')
    await wrapper.findAll('input[type="checkbox"]')[0].setValue(true)
    await wrapper.findAll('input[type="checkbox"]')[1].setValue(true)
    await wrapper.find('form').trigger('submit'); await flushPromises()
    const call = apiRequest.mock.calls.find(([url]) => url.includes('record_jha_resource'))
    expect(Object.fromEntries(call[1].body)).toMatchObject({ jha_name: 'JHA-1', step_row: 'STEP-1', kind: 'Permit', reference: 'PERMIT-456', confirmation: '1', work_changed: '1' })
    expect(wrapper.emitted('updated')[0][0].status).toBe('Review Required - Work Changed')
    expect(jha.status).toBe('Signed')
  })
  it('uploads a private step photo and allows annotation before saving', async () => {
    wrapper = mount(JhaStepResources, { props: { jha } }); await flushPromises()
    await button('Add Supporting Record').trigger('click')
    await wrapper.findAll('select')[1].setValue('Photo')
    const file = new File(['png-data'], 'pump.png', { type: 'image/png' })
    const input = wrapper.find('input[type="file"]'); Object.defineProperty(input.element, 'files', { value: [file], configurable: true })
    await input.trigger('change'); await flushPromises()
    const call = apiRequest.mock.calls.find(([url]) => url.includes('upload_file'))
    expect(call[1].body.get('is_private')).toBe('1'); expect(call[1].body.get('docname')).toBe('JHA-1')
    expect(wrapper.findComponent(JhaPhotoMarkers).props('src')).toBe('/private/files/pump.png')
  })
  it('clears live resource state when the connection is lost', async () => {
    wrapper = mount(JhaStepResources, { props: { jha } }); await flushPromises()
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: false }); window.dispatchEvent(new Event('offline')); await flushPromises()
    expect(wrapper.text()).not.toContain('PERMIT-123'); expect(button('Add Supporting Record')).toBeUndefined()
  })
})

describe('photo markers', () => {
  it('records a labelled point in image-relative coordinates and retains the original image', async () => {
    wrapper = mount(JhaPhotoMarkers, { props: { src: '/private/files/photo.png', markers: [], editable: true } })
    await wrapper.find('input').setValue('Restraint point')
    const image = wrapper.find('div.relative')
    vi.spyOn(image.element, 'getBoundingClientRect').mockReturnValue({ left: 0, top: 0, width: 100, height: 80 })
    await image.trigger('click', { clientX: 25, clientY: 60 })
    expect(wrapper.emitted('update:markers')[0][0]).toEqual([{ x: .25, y: .75, label: 'Restraint point' }])
    expect(wrapper.find('img').attributes('src')).toBe('/private/files/photo.png')
  })
})

describe('reviewed job guidance', () => {
  it('records template differences and leaves steps and signatures for the normal JHA discussion', async () => {
    wrapper = mount(JhaJobLearning, { props: { jha: { ...jha, status: 'Draft' } } }); await flushPromises()
    await button('Use Job Template').trigger('click'); await wrapper.find('select').setValue('TEMPLATE-1')
    await wrapper.find('textarea').setValue('Different pump model and access')
    await wrapper.find('input[type="checkbox"]').setValue(true)
    await wrapper.find('form').trigger('submit'); await flushPromises()
    const call = apiRequest.mock.calls.find(([url]) => url.includes('select_jha_template'))
    expect(Object.fromEntries(call[1].body)).toMatchObject({ template_name: 'TEMPLATE-1', differences: 'Different pump model and access', confirmation: '1' })
    expect(apiRequest.mock.calls.some(([url]) => /sign|acknowledge|record_work_step/.test(url))).toBe(false)
  })
  it('does not expose review controls to someone who cannot approve lessons', async () => {
    learning.closeouts = [{ name: 'CLOSEOUT-1', status: 'Pending Review', deviations: 'Changed access' }]
    wrapper = mount(JhaJobLearning, { props: { jha } }); await flushPromises()
    expect(wrapper.text()).toContain('Pending Review'); expect(button('Review Closeout')).toBeUndefined()
  })
})

describe('offline signed reference copy', () => {
  const copy = { user: 'viewer', saved_at: '2026-10-14 10:00', jha: { ...jha, hazards_and_controls: [] }, review: { participants: [] }, resources: [], photos: {}, media_missing: 0, notice: 'Downloaded signed copy.' }
  it('shows the saved revision while offline without asserting it is current', async () => {
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: false }); readOfflineJha.mockResolvedValue(copy)
    wrapper = mount(JhaOfflineCopy, { props: { jhaName: 'JHA-1' } }); await flushPromises()
    expect(wrapper.text()).toContain('Downloaded signed revision 3'); expect(wrapper.text()).toContain('2026-10-14 10:00')
    expect(wrapper.text()).not.toContain('current signed revision'); expect(button('Save Signed Copy for Offline')).toBeUndefined()
  })
  it('saves an offline observation and clearly shows that it is pending server sync', async () => {
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: false }); readOfflineJha.mockResolvedValue(copy)
    saveJhaObservation.mockResolvedValue({ queued: true }); wrapper = mount(JhaOfflineCopy, { props: { jhaName: 'JHA-1' } }); await flushPromises()
    await wrapper.find('textarea').setValue('Changed restraint')
    await wrapper.find('input[type="checkbox"]').setValue(true)
    await wrapper.find('form').trigger('submit'); await flushPromises()
    expect(saveJhaObservation.mock.calls[0].slice(1, 4)).toEqual(['Changed restraint', '', true])
    expect(wrapper.text()).toContain('pending server sync')
    expect(apiRequest).not.toHaveBeenCalled()
  })
})
