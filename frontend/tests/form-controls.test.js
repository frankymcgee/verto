import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { TabButtons, Select, DatePicker, Checkbox, FormControl } from 'frappe-ui'
import ChildTableField from '../src/components/mobile-fields/ChildTableField.vue'
import EditDocument from '../src/pages/EditDocument.vue'
import NewDocument from '../src/pages/NewDocument.vue'
const mocked = vi.hoisted(() => ({ api: vi.fn(), push: vi.fn(), back: vi.fn() }))
vi.mock('vue-router', () => ({
  useRoute: () => ({
    params: { mobileDoctype: 'Daily Timesheet', docname: 'TS-1' },
    query: {},
    fullPath: '/new/Daily%20Timesheet',
  }),
  useRouter: () => ({ push: mocked.push, back: mocked.back }),
}))
vi.mock('../src/lib/api', () => ({ apiRequest: mocked.api }))
vi.mock('../src/lib/diagnostics', () => ({ reportClientError: vi.fn() }))
vi.mock('../src/pwa/offlineQueue', () => ({
  createOfflineId: () => crypto.randomUUID(),
  attachFileToDocumentOperation: vi.fn(),
  makeOfflineAttachment: vi.fn(),
}))
let w
const fields = [
  {
    fieldname: 'date',
    fieldtype: 'Date',
    label: 'Date',
    default: '2026-09-14',
  },
  {
    fieldname: 'shift',
    fieldtype: 'Select',
    label: 'Shift',
    options: 'DS\nNS',
    default: 'DS',
  },
  { fieldname: 'notes_tab', fieldtype: 'Tab Break', label: 'Notes' },
  { fieldname: 'approved', fieldtype: 'Check', label: 'Approved', default: 0 },
  {
    fieldname: 'locked',
    fieldtype: 'Data',
    label: 'Locked',
    default: 'Fixed',
    read_only: true,
  },
]
async function render(component = NewDocument, formFields = fields, savedValues = {}) {
  const schema = {
    mobile_doctype: 'Daily Timesheet',
    doctype: 'Daily Timesheet',
    title: 'Daily Timesheet',
    fields: formFields,
  }
  mocked.api.mockImplementation(async (url, options) => {
    if (url.includes('get_form_schema'))
      return { message: schema }
    if (url.includes('get_prefill_values')) return { message: { values: {} } }
    if (url.includes('get_mobile_doc_for_edit'))
      return { message: { schema, can_write: true, values: savedValues } }
    if (url.includes('create_mobile_doc'))
      return { message: { doctype: 'Daily Timesheet', name: 'TS-1', route: '/shifts' } }
    if (url.includes('update_mobile_doc'))
      return { message: { values: { ...savedValues, ...JSON.parse(options.body.get('values')) } } }
    return { message: { values: {} } }
  })
  w = mount(component, { attachTo: document.body })
  await flushPromises()
  return w
}
afterEach(() => {
  w?.unmount()
  document.body.innerHTML = ''
  localStorage.clear()
  sessionStorage.clear()
  vi.clearAllMocks()
})
describe('Dynamic mobile forms', () => {
  it('retains date defaults and maps tab IDs using v1 TabButtons', async () => {
    await render()
    expect(w.findComponent(DatePicker).props('modelValue')).toBe('2026-09-14')
    const tabs = w.findComponent(TabButtons)
    expect(tabs.props('modelValue')).toBe('main')
    const notes = [...document.querySelectorAll('button')].find(
      (b) => b.textContent.trim() === 'Notes'
    )
    notes.click()
    await flushPromises()
    expect(tabs.props('modelValue')).toBe('notes_tab')
    const locked = w.findAll('input').find((c) => c.element.value === 'Fixed')
    expect(locked.element.disabled).toBe(true)
  })
  it('submits scalar select values and checkbox state through the existing API', async () => {
    await render()
    w.findComponent(Select).vm.$emit('update:modelValue', 'NS')
    w.findComponent(Checkbox).vm.$emit('update:modelValue', true)
    await flushPromises()
    await w.find('form').trigger('submit')
    await flushPromises()
    const request = mocked.api.mock.calls.find(([url]) =>
      url.includes('create_mobile_doc')
    )
    expect(request).toBeTruthy()
    const values = JSON.parse(request[1].body.get('values'))
    expect(values).toMatchObject({
      date: '2026-09-14',
      shift: 'NS',
      approved: true,
    })
  })

  it('ignores a second submit while the first is still saving', async () => {
    await render()
    let resolve
    mocked.api.mockImplementationOnce(() => new Promise(done => { resolve = done }))
    await w.find('form').trigger('submit')
    await w.find('form').trigger('submit')
    expect(mocked.api.mock.calls.filter(([url]) => url.includes('create_mobile_doc'))).toHaveLength(1)
    resolve({ message: { doctype: 'Daily Timesheet', name: 'TS-1', route: '/shifts' } })
    await flushPromises()
  })

  it('restores the same submission ID after a failed save and page reload', async () => {
    await render()
    mocked.api.mockRejectedValueOnce(new Error('Could not save'))
    await w.find('form').trigger('submit')
    await flushPromises()
    const first = mocked.api.mock.calls.find(([url]) => url.includes('create_mobile_doc'))[1].body.get('operation_id')
    w.unmount()
    await render()
    await w.find('form').trigger('submit')
    await flushPromises()
    const requests = mocked.api.mock.calls.filter(([url]) => url.includes('create_mobile_doc'))
    expect(requests[1][1].body.get('operation_id')).toBe(first)
    expect(first).toBeTruthy()
  })
})

describe('Mobile section dependencies', () => {
  const sectionFields = [
    { fieldname: 'mode', fieldtype: 'Select', label: 'Mode', options: 'Simple\nDetailed', default: 'Simple' },
    { fieldname: 'extra_section', fieldtype: 'Section Break', label: 'Extra details', description: 'Add details here', depends_on: "eval:doc.mode === 'Detailed'" },
    { fieldname: 'details', fieldtype: 'Data', label: 'Details', required: true },
    { fieldname: 'second_column', fieldtype: 'Column Break' },
    { fieldname: 'reference', fieldtype: 'Data', label: 'Reference' },
    { fieldname: 'reviewer', fieldtype: 'Data', label: 'Reviewer', depends_on: 'eval:doc.reference' },
    { fieldname: 'entries', fieldtype: 'Table', label: 'Entries', child_fields: [] },
    { fieldname: 'general_section', fieldtype: 'Section Break', label: 'General' },
    { fieldname: 'general_notes', fieldtype: 'Data', label: 'General notes' },
    { fieldname: 'hidden_section', fieldtype: 'Section Break', depends_on: 'eval:false' },
    { fieldname: 'another_tab', fieldtype: 'Tab Break', label: 'Another tab' },
    { fieldname: 'tab_notes', fieldtype: 'Data', label: 'Tab notes' },
  ]

  const control = (label, wrapper = w) => wrapper.findAllComponents(FormControl)
    .find(field => field.props('label') === label)

  async function setMode(mode) {
    w.findComponent(Select).vm.$emit('update:modelValue', mode)
    await flushPromises()
  }

  it.each([
    ['new', NewDocument, 'create_mobile_doc'],
    ['existing', EditDocument, 'update_mobile_doc'],
  ])('updates an entire section in the %s form', async (_, component, method) => {
    await render(component, sectionFields, { details: 'Saved detail' })
    expect(w.text()).not.toContain('Extra details')
    expect(w.text()).not.toContain('Add details here')
    expect(control('Details')).toBeUndefined()
    expect(control('Reference')).toBeUndefined()
    expect(w.findComponent(ChildTableField).exists()).toBe(false)
    expect(control('General notes')).toBeDefined()
    expect(control('Tab notes')).toBeDefined()

    await setMode('Detailed')
    expect(w.text()).toContain('Extra details')
    expect(w.text()).toContain('Add details here')
    expect(control('Details').props('required')).toBe(true)
    expect(control('Reference')).toBeDefined()
    expect(control('Reviewer')).toBeUndefined()
    expect(w.findComponent(ChildTableField).exists()).toBe(true)
    await control('Details').find('input').setValue('Draft detail')

    await setMode('Simple')
    expect(control('Details')).toBeUndefined()
    await setMode('Detailed')
    expect(control('Details').find('input').element.value).toBe('Draft detail')
    await setMode('Simple')

    await w.find('form').trigger('submit')
    await flushPromises()
    const request = mocked.api.mock.calls.find(([url]) => url.includes(method))
    const submitted = JSON.parse(request[1].body.get('values'))
    expect(submitted).toMatchObject({ mode: 'Simple', general_notes: '', tab_notes: '' })
    expect(submitted).not.toHaveProperty('details')
    expect(submitted).not.toHaveProperty('entries')
  })

  it('hides conditional row details in the drawer and summary and retains saved values offline', async () => {
    const childFields = [
      { fieldname: 'entry', fieldtype: 'Data', label: 'Entry' },
      { fieldname: 'show_note', fieldtype: 'Check', label: 'Show row note' },
      { fieldname: 'notes_section', fieldtype: 'Section Break', label: 'Row details', depends_on: 'eval:doc.show_note' },
      { fieldname: 'note', fieldtype: 'Data', label: 'Row note' },
    ]
    const outsideTable = { fieldname: 'rows', fieldtype: 'Table', label: 'Rows', child_fields: childFields }
    const [mode, ...sections] = sectionFields
    await render(EditDocument, [mode, outsideTable, ...sections], {
      details: 'Saved parent detail',
      rows: [{ entry: 'Existing entry', show_note: 0, note: 'Saved row note' }],
    })
    const table = w.findComponent(ChildTableField)
    expect(table.text()).not.toContain('Saved row note')
    await table.findAll('button').find(button => button.text().includes('Existing entry')).trigger('click')
    expect(document.body.textContent).not.toContain('Row details')
    expect(control('Row note', table)).toBeUndefined()

    const toggle = table.findComponent(Checkbox)
    toggle.vm.$emit('update:modelValue', true)
    await flushPromises()
    expect(document.body.textContent).toContain('Row details')
    expect(control('Row note', table).find('input').element.value).toBe('Saved row note')
    toggle.vm.$emit('update:modelValue', false)
    await flushPromises()

    mocked.api.mockImplementationOnce(async (_, { body }) => ({
      message: { values: JSON.parse(body.get('values')), offline_queued: true },
    }))
    const saveRow = [...document.querySelectorAll('button')].find(button => button.textContent.trim() === 'Save Row')
    saveRow.click()
    await flushPromises()
    expect(w.text()).toContain('Saved on this device and waiting to sync.')
    const request = mocked.api.mock.calls.find(([url]) => url.includes('update_mobile_doc'))
    expect(JSON.parse(request[1].body.get('values'))).not.toHaveProperty('details')
    expect(table.text()).not.toContain('Saved row note')
    expect(table.props('modelValue')[0].note).toBe('Saved row note')
    await setMode('Detailed')
    expect(control('Details').find('input').element.value).toBe('Saved parent detail')
  })
})
