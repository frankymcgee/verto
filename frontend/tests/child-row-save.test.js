import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { FormControl, BottomSheet, TimePicker } from 'frappe-ui'
import EditDocument from '../src/pages/EditDocument.vue'
import NewDocument from '../src/pages/NewDocument.vue'
import ChildTableField from '../src/components/mobile-fields/ChildTableField.vue'

const mocks = vi.hoisted(() => ({ api: vi.fn(), back: vi.fn(), push: vi.fn(), nextId: 0 }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { mobileDoctype: 'field-interaction', docname: 'FORM-1' }, query: {}, fullPath: '/forms/edit/FORM-1' }),
  useRouter: () => ({ back: mocks.back, push: mocks.push }),
}))
vi.mock('../src/lib/api', () => ({ apiRequest: mocks.api }))
vi.mock('../src/lib/diagnostics', () => ({ reportClientError: vi.fn() }))
vi.mock('../src/pwa/offlineQueue', () => ({ createOfflineId: () => `document-${++mocks.nextId}` }))

let wrapper
let doctype
let writable
const initialValues = () => ({ notes: 'Original notes', rows: [{ entry: 'Original entry', at: '06:00:00' }], duration: 3600 })
function schema() {
  return { mobile_doctype: 'field-interaction', doctype, title: 'Field interaction', fields: [
    { fieldname: 'notes', label: 'Notes', fieldtype: 'Data' },
    { fieldname: 'duration', label: 'Duration', fieldtype: 'Float' },
    { fieldname: 'rows', label: 'Entries', fieldtype: 'Table', child_fields: [
      { fieldname: 'entry', label: 'Entry', fieldtype: 'Data', required: true },
      { fieldname: 'at', label: 'At', fieldtype: 'Time' },
    ] },
  ] }
}
function savedResponse(body, extra = {}) {
  const values = JSON.parse(body.get('values'))
  values.rows = values.rows.map(row => ({ ...row, entry: row.entry.trim() }))
  return { message: { doctype, name: 'FORM-1', docstatus: 0, values, files: [], ...extra } }
}
const updates = () => mocks.api.mock.calls.filter(([url]) => url.includes('update_mobile_doc'))
async function render(component = EditDocument) {
  wrapper = mount(component, { attachTo: document.body })
  await flushPromises()
}
function table() { return wrapper.findComponent(ChildTableField) }
async function click(text) {
  const button = [...document.querySelectorAll('button')].find(el => el.textContent.trim() === text)
  expect(button, text).toBeTruthy()
  button.click()
  await flushPromises()
  return button
}
async function setEntry(value) {
  const input = table().findAllComponents(FormControl).find(field => field.props('label') === 'Entry')
  input.vm.$emit('update:modelValue', value)
  await flushPromises()
}
async function addRow(entry) {
  await click('+ Add')
  await setEntry(entry)
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.nextId = 0
  doctype = 'Field Interaction'
  writable = true
  mocks.api.mockImplementation(async (url, options) => {
    if (url.includes('get_mobile_doc_for_edit')) return { message: { schema: schema(), doctype, name: 'FORM-1', can_write: writable, values: initialValues(), files: [] } }
    if (url.includes('get_form_schema')) return { message: schema() }
    if (url.includes('get_prefill_values')) return { message: { values: {} } }
    if (url.includes('update_mobile_doc')) return savedResponse(options.body)
    if (url.includes('create_mobile_doc')) return { message: { name: 'FORM-NEW', route: '/forms' } }
    return { message: { values: {} } }
  })
  vi.spyOn(window, 'confirm').mockReturnValue(true)
})
afterEach(() => {
  wrapper?.unmount()
  document.body.innerHTML = ''
  localStorage.clear()
  sessionStorage.clear()
  vi.restoreAllMocks()
})

describe('Save Row persists the existing form', () => {
  it('saves a row, parent edits and selected attachments together, then stays on the form', async () => {
    await render()
    const notes = wrapper.findAllComponents(FormControl).find(field => field.props('label') === 'Notes')
    notes.vm.$emit('update:modelValue', 'Updated notes')
    const file = new File(['photo'], 'photo.jpg', { type: 'image/jpeg' })
    const picker = wrapper.find('input[type="file"]')
    Object.defineProperty(picker.element, 'files', { configurable: true, value: [file] })
    await picker.trigger('change')
    await addRow(' New entry ')
    const time = table().findComponent(TimePicker).find('input')
    expect(time.element.readOnly).toBe(true)
    await time.trigger('click')
    const option = document.querySelector('[role="option"][data-value="07:15"]')
    expect(option).toBeTruthy()
    option.click()
    await flushPromises()
    await click('Save Row')

    expect(updates()).toHaveLength(1)
    const payload = updates()[0][1].body
    expect(payload.get('docname')).toBe('FORM-1')
    expect(JSON.parse(payload.get('values'))).toMatchObject({ notes: 'Updated notes', rows: [
      { entry: 'Original entry' }, { entry: ' New entry ', at: '07:15:00' },
    ] })
    expect(payload.getAll('attachments')).toHaveLength(1)
    expect(table().props('modelValue')[1].entry).toBe('New entry')
    expect(table().findComponent(BottomSheet).props('open')).toBe(false)
    expect(wrapper.text()).toContain('Saved successfully.')
    await new Promise(resolve => setTimeout(resolve, 550))
    expect(mocks.back).not.toHaveBeenCalled()
  })

  it('blocks repeated taps and keeps the row drawer open while the save is pending', async () => {
    await render()
    await addRow('Pending entry')
    let finish
    mocks.api.mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
    const button = await click('Save Row')
    expect(button.disabled).toBe(true)
    expect(table().findComponent(BottomSheet).props('dismissible')).toBe(false)
    expect(table().findComponent(BottomSheet).props('open')).toBe(true)
    button.click()
    await flushPromises()
    expect(updates()).toHaveLength(1)
    finish(savedResponse(updates()[0][1].body))
    await flushPromises()
    expect(table().findComponent(BottomSheet).props('open')).toBe(false)
  })

  it('retains an unsuccessful row draft and retries it without adding a duplicate row', async () => {
    await render()
    await addRow('Invalid entry')
    mocks.api.mockRejectedValueOnce(new Error(JSON.stringify([JSON.stringify({ message: 'Entry requires review.' })])))
    await click('Save Row')
    expect(table().findComponent(BottomSheet).props('open')).toBe(true)
    expect(document.querySelector('[role="alert"]').textContent).toContain('Entry requires review.')
    expect(table().props('modelValue')).toHaveLength(1)
    expect(table().findAllComponents(FormControl).find(field => field.props('label') === 'Entry').find('input').element.value).toBe('Invalid entry')
    await setEntry('Corrected entry')
    await click('Save Row')
    expect(table().props('modelValue')).toHaveLength(2)
    expect(table().props('modelValue')[1].entry).toBe('Corrected entry')
    expect(updates()[0][1].body.get('operation_id')).toBe(updates()[1][1].body.get('operation_id'))
  })

  it('saves edited and additional rows with distinct operation IDs after each success', async () => {
    await render()
    const existing = table().findAll('button').find(button => button.text().includes('Original entry'))
    await existing.trigger('click')
    await setEntry('Edited entry')
    await click('Save Row')
    expect(table().props('modelValue')).toHaveLength(1)
    await addRow('Second entry')
    await click('Save Row')
    expect(updates()).toHaveLength(2)
    expect(table().props('modelValue').map(row => row.entry)).toEqual(['Edited entry', 'Second entry'])
    expect(updates()[1][1].body.get('operation_id')).not.toBe(updates()[0][1].body.get('operation_id'))
    expect(updates()[1][1].body.getAll('attachments')).toHaveLength(0)
  })

  it('accepts the offline queue acknowledgement and allows the next row to be saved', async () => {
    await render()
    await addRow('Offline entry')
    mocks.api.mockImplementationOnce(async (url, options) => savedResponse(options.body, { offline_queued: true, offline_operation_id: options.body.get('operation_id') }))
    await click('Save Row')
    expect(wrapper.text()).toContain('Saved on this device and waiting to sync.')
    expect(table().findComponent(BottomSheet).props('open')).toBe(false)
    await addRow('Next entry')
    await click('Save Row')
    expect(table().props('modelValue')).toHaveLength(3)
    expect(updates()[1][1].body.get('operation_id')).not.toBe(updates()[0][1].body.get('operation_id'))
  })

  it('preserves timesheet confirmation and keeps a cancelled row open', async () => {
    doctype = 'Daily Timesheet'
    await render()
    await addRow('Timesheet entry')
    window.confirm.mockReturnValueOnce(false)
    await click('Save Row')
    expect(window.confirm).toHaveBeenCalled()
    expect(updates()).toHaveLength(0)
    expect(table().findComponent(BottomSheet).props('open')).toBe(true)
    await click('Save Row')
    expect(updates()).toHaveLength(1)
  })

  it('keeps read-only forms read-only', async () => {
    writable = false
    await render()
    expect(table().props('disabled')).toBe(true)
    expect(table().findAll('button').some(button => button.text() === '+ Add')).toBe(false)
    await table().find('button').trigger('click')
    expect([...document.querySelectorAll('button')].some(button => button.textContent.trim() === 'Save Row')).toBe(false)
    expect(updates()).toHaveLength(0)
  })

  it('still saves later parent field changes through Save Changes', async () => {
    await render()
    await addRow('Saved entry')
    await click('Save Row')
    const notes = wrapper.findAllComponents(FormControl).find(field => field.props('label') === 'Notes')
    notes.vm.$emit('update:modelValue', 'Later edit')
    await flushPromises()
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(updates()).toHaveLength(2)
    expect(JSON.parse(updates()[1][1].body.get('values')).notes).toBe('Later edit')
  })

  it('allows a later row deletion to be committed with Save Changes', async () => {
    await render()
    await addRow('Saved entry')
    await click('Save Row')
    const existing = table().findAll('button').find(button => button.text().includes('Original entry'))
    await existing.trigger('click')
    await click('Delete')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(updates()).toHaveLength(2)
    expect(JSON.parse(updates()[1][1].body.get('values')).rows.map(row => row.entry)).toEqual(['Saved entry'])
  })

  it('ignores a dependent-field response that arrives after the row and parent were saved', async () => {
    await render()
    let finishDependency
    const api = mocks.api.getMockImplementation()
    mocks.api.mockImplementation((url, options) => url.includes('process_field_change')
      ? new Promise(resolve => { finishDependency = resolve }) : api(url, options))
    const notes = wrapper.findAllComponents(FormControl).find(field => field.props('label') === 'Notes')
    notes.vm.$emit('update:modelValue', 'Current notes')
    await new Promise(resolve => setTimeout(resolve, 350))
    expect(finishDependency).toBeTypeOf('function')
    await addRow('Current row')
    await click('Save Row')
    finishDependency({ message: { values: { notes: 'Stale notes', rows: initialValues().rows } } })
    await flushPromises()
    expect(table().props('modelValue').map(row => row.entry)).toEqual(['Original entry', 'Current row'])
    expect(wrapper.findAllComponents(FormControl).find(field => field.props('label') === 'Notes').find('input').element.value).toBe('Current notes')
  })

  it('keeps rows in a new form until the user submits the complete form', async () => {
    await render(NewDocument)
    await addRow('Draft entry')
    await click('Save Row')
    expect(mocks.api.mock.calls.some(([url]) => url.includes('create_mobile_doc'))).toBe(false)
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    const create = mocks.api.mock.calls.find(([url]) => url.includes('create_mobile_doc'))
    expect(JSON.parse(create[1].body.get('values')).rows[0].entry).toBe('Draft entry')
  })
})
