import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import JhaPhotoImport from '../src/components/JhaPhotoImport.vue'
import { apiRequest } from '../src/lib/api'

vi.mock('../src/lib/api', () => ({ apiRequest: vi.fn() }))
let wrapper
const draft = { name: 'JHA-1', status: 'Draft', work_steps: [{ activity: 'Planned step' }], hazards_and_controls: [] }
const reading = () => ({ name: 'READ-1', status: 'Pending Review', pages: [{ url: '/private/files/page-one.jpg' }],
  content: { job_description: 'Pump work', uncertainties: ['Page 1: confirm the restraint control.'],
    steps: [{ page: 1, activity: 'Remove pump', hold_point: 'Check isolation',
      hazards: [{ hazard: 'Stored energy', controls: 'Isolate', critical_control: '', control_owner: '' }] }] } })
const button = label => wrapper.findAll('button').find(item => item.text() === label)
async function open(record = null, props = {}) {
  apiRequest.mockResolvedValueOnce({ message: { can_import: true, reading: record } })
  wrapper = mount(JhaPhotoImport, { props: { jha: draft, online: true, ...props } }); await flushPromises()
}
async function select(files) {
  const input = wrapper.get('input[multiple]')
  Object.defineProperty(input.element, 'files', { configurable: true, value: files })
  await input.trigger('change'); await flushPromises()
}
beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { wrapper?.unmount() })

describe('paper JHA photo import', () => {
  it('supports a phone camera and multiple selected private page attachments', async () => {
    await open()
    expect(wrapper.get('input[capture]').attributes('capture')).toBe('environment')
    apiRequest.mockResolvedValueOnce({ message: { file_url: '/private/files/one.jpg' } })
      .mockResolvedValueOnce({ message: { file_url: '/private/files/two.jpg' } })
    await select([new File(['a'], 'one.jpg', { type: 'image/jpeg' }), new File(['b'], 'two.jpg', { type: 'image/jpeg' })])
    for (const [, options] of apiRequest.mock.calls.slice(1)) {
      expect(Object.fromEntries(options.body)).toMatchObject({ is_private: '1', doctype: 'Digital Job Hazard Analysis', docname: 'JHA-1' })
    }
    await wrapper.get('[aria-label="Move page 2 earlier"]').trigger('click')
    apiRequest.mockResolvedValueOnce({ message: reading() })
    await button('Read pages with PERI').trigger('click'); await flushPromises()
    const body = apiRequest.mock.calls.at(-1)[1].body
    expect(JSON.parse(body.get('page_urls'))).toEqual(['/private/files/two.jpg', '/private/files/one.jpg'])
    expect(body.get('request_id')).toBeTruthy()
    expect(wrapper.text()).toContain('Items to clarify with the team')
    expect(wrapper.text()).toContain('replace the draft’s planned step list')
    expect(wrapper.emitted('busy').map(args => args[0])).toEqual([true, false, true, false])
  })
  it('requires human confirmation, sends corrected text and resets confirmation when it changes', async () => {
    await open(reading())
    expect(button('Use checked JHA').attributes('disabled')).toBeDefined()
    await wrapper.get('input[type=checkbox]').setValue(true)
    await wrapper.get('[aria-label="Step 1 controls 1"]').setValue('Isolate and test for zero energy')
    expect(wrapper.get('input[type=checkbox]').element.checked).toBe(false)
    await wrapper.get('input[type=checkbox]').setValue(true)
    apiRequest.mockResolvedValueOnce({ message: { reading: { ...reading(), status: 'Imported' }, jha: { ...draft, photo_import: 'READ-1' } } })
    await button('Use checked JHA').trigger('click'); await flushPromises()
    const body = apiRequest.mock.calls.at(-1)[1].body
    expect(JSON.parse(body.get('reviewed_content')).steps[0].hazards[0].controls).toBe('Isolate and test for zero energy')
    expect(body.get('confirmation')).toBe('1')
    expect(wrapper.emitted('updated')[0][0].photo_import).toBe('READ-1')
    expect(wrapper.text()).toContain('Team leader review (Supervisor or above) and sign-on are still required')
  })
  it('preserves corrections when saving fails', async () => {
    await open(reading()); await wrapper.get('[aria-label="Step 1 activity"]').setValue('Restrain and remove pump')
    await wrapper.get('input[type=checkbox]').setValue(true)
    apiRequest.mockRejectedValueOnce(Error('Connection lost'))
    await button('Use checked JHA').trigger('click'); await flushPromises()
    expect(wrapper.get('[aria-label="Step 1 activity"]').element.value).toBe('Restrain and remove pump')
    expect(wrapper.get('[role=alert]').text()).toContain('Connection lost')
    apiRequest.mockRejectedValueOnce(Error('Still offline'))
    await button('Use checked JHA').trigger('click'); await flushPromises()
    expect(apiRequest.mock.calls.at(-1)[1].body.get('import_name')).toBe('READ-1')
  })
  it('reuses a reading request after a network failure and retains uploaded pages', async () => {
    await open(); apiRequest.mockResolvedValueOnce({ message: { file_url: '/private/files/one.jpg' } })
    await select([new File(['a'], 'one.jpg', { type: 'image/jpeg' })])
    apiRequest.mockRejectedValueOnce(Error('Connection lost'))
    await button('Read pages with PERI').trigger('click'); await flushPromises()
    const first = apiRequest.mock.calls.at(-1)[1].body.get('request_id')
    apiRequest.mockResolvedValueOnce({ message: reading() })
    await button('Read pages with PERI').trigger('click'); await flushPromises()
    expect(apiRequest.mock.calls.at(-1)[1].body.get('request_id')).toBe(first)
    expect(apiRequest.mock.calls.filter(([url]) => url === '/api/method/upload_file')).toHaveLength(1)
  })
  it('blocks unsupported and excessive files before upload', async () => {
    await open(); await select([new File(['a'], 'page.heic', { type: 'image/heic' })])
    expect(apiRequest).toHaveBeenCalledTimes(1)
    expect(wrapper.get('[role=alert]').text()).toContain('JPG, PNG or WebP')
    await select(Array.from({ length: 11 }, () => new File(['a'], 'page.jpg', { type: 'image/jpeg' })))
    expect(apiRequest).toHaveBeenCalledTimes(1)
  })
  it('retains successful uploads when a later page fails', async () => {
    await open(); apiRequest.mockResolvedValueOnce({ message: { file_url: '/private/files/one.jpg' } }).mockRejectedValueOnce(Error('Upload failed'))
    await select([new File(['a'], 'one.jpg', { type: 'image/jpeg' }), new File(['b'], 'two.jpg', { type: 'image/jpeg' })])
    expect(wrapper.findAll('img')).toHaveLength(1)
    expect(wrapper.get('[role=alert]').text()).toContain('Upload failed')
    expect(button('Read pages with PERI').attributes('disabled')).toBeUndefined()
  })
  it('requires readable steps and permits correcting missing rows', async () => {
    const empty = reading(); empty.content.steps = []
    await open(empty); await wrapper.get('input[type=checkbox]').setValue(true)
    expect(button('Use checked JHA').attributes('disabled')).toBeDefined()
    await button('Add missing step').trigger('click'); await button('Add missing hazard').trigger('click')
    expect(wrapper.findAll('[data-testid="paper-step-1"]')).toHaveLength(1)
    expect(wrapper.get('[aria-label="Step 1 hazard 1"]').exists()).toBe(true)
  })
  it('keeps imported source pages read only and escapes photographed text', async () => {
    const record = reading(); record.status = 'Imported'; record.content.job_description = '<script>unsafe()</script>'
    await open(record, { jha: { ...draft, photo_import: record.name } })
    expect(button('Use checked JHA')).toBeUndefined()
    expect(wrapper.find('input[type=file]').exists()).toBe(false)
    expect(wrapper.find('script').exists()).toBe(false)
    expect(wrapper.get('textarea').element.value).toContain('<script>')
    expect(wrapper.findAll('fieldset')[1].attributes('disabled')).toBeDefined()
  })
  it.each(['Signed', 'Voice Discussion in Progress', 'Ready for Team Review'])('does not offer replacing a %s JHA', async status => {
    wrapper = mount(JhaPhotoImport, { props: { jha: { ...draft, status }, online: true } }); await flushPromises()
    expect(apiRequest).not.toHaveBeenCalled(); expect(wrapper.find('details').exists()).toBe(false)
  })
  it('disables the reading during voice actions and makes no offline request', async () => {
    await open(reading(), { busy: true })
    expect(wrapper.find('fieldset').attributes('disabled')).toBeDefined()
    wrapper.unmount(); apiRequest.mockClear()
    wrapper = mount(JhaPhotoImport, { props: { jha: draft, online: false } }); await flushPromises()
    expect(apiRequest).not.toHaveBeenCalled(); expect(wrapper.text()).toContain('Connect to the internet')
  })
  it('ignores a reading response after a different JHA opens', async () => {
    let resolve
    apiRequest.mockImplementationOnce(() => new Promise(done => { resolve = done }))
    wrapper = mount(JhaPhotoImport, { props: { jha: draft, online: true } })
    apiRequest.mockResolvedValueOnce({ message: { can_import: true, reading: null } })
    await wrapper.setProps({ jha: { ...draft, name: 'JHA-2' } }); await flushPromises()
    resolve({ message: { can_import: true, reading: reading() } }); await flushPromises()
    expect(wrapper.text()).not.toContain('Remove pump'); expect(wrapper.findAll('img')).toHaveLength(0)
  })
})
