import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { DatePicker, FormControl, TabButtons, TimePicker } from 'frappe-ui'
import NewDocument from '../src/pages/NewDocument.vue'
import EditDocument from '../src/pages/EditDocument.vue'
import ChildTableField from '../src/components/mobile-fields/ChildTableField.vue'
import SignatureField from '../src/components/mobile-fields/SignatureField.vue'
import SubmissionChecklist from '../src/components/SubmissionChecklist.vue'
import { collectSubmissionIssues } from '../src/lib/submissionChecklist'

const mocks = vi.hoisted(() => ({ api: vi.fn(), push: vi.fn(), back: vi.fn() }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { mobileDoctype: 'field-interaction', docname: 'FORM-1' }, query: {}, fullPath: '/new/field-interaction' }),
  useRouter: () => ({ push: mocks.push, back: mocks.back }),
}))
vi.mock('../src/lib/api', () => ({ apiRequest: mocks.api }))
vi.mock('../src/lib/diagnostics', () => ({ reportClientError: vi.fn() }))
vi.mock('../src/pwa/offlineQueue', () => ({ createOfflineId: () => crypto.randomUUID() }))

const required = (fieldname, fieldtype = 'Data', extra = {}) => ({ fieldname, fieldtype, label: fieldname, required: true, ...extra })
const fields = [
  { fieldname: 'notes', label: 'Notes', fieldtype: 'Data' },
  required('quantity', 'Int'),
  { fieldname: 'review_tab', fieldtype: 'Tab Break', label: 'Review' },
  required('signature', 'Signature', { label: 'Supervisor signature' }),
  required('rows', 'Table', { label: 'Observations', child_fields: [required('detail', 'Data', { label: 'Observation detail' })] }),
]
let wrapper
let formFields
let formValues
let writable
const writes = () => mocks.api.mock.calls.filter(([url]) => /(?:create|update)_mobile_doc/.test(url))
const panel = () => wrapper.findComponent(SubmissionChecklist)
const table = () => wrapper.findComponent(ChildTableField)
async function render(component = NewDocument) {
  wrapper = mount(component, { attachTo: document.body })
  await flushPromises()
}
async function click(text, scope = document) {
  const button = [...scope.querySelectorAll('button')].find(el => el.textContent.trim() === text)
  expect(button, text).toBeTruthy()
  button.click()
  await flushPromises()
}
async function setField(label, value, scope = wrapper) {
  const control = scope.findAllComponents(FormControl).find(field => field.props('label') === label)
  expect(control, label).toBeTruthy()
  control.vm.$emit('update:modelValue', value)
  await flushPromises()
}
async function submit() { await wrapper.get('form').trigger('submit'); await flushPromises() }

beforeEach(() => {
  vi.clearAllMocks()
  formFields = fields
  formValues = { notes: 'Keep my notes', quantity: 0, rows: [{ detail: 'First row' }, { detail: '' }] }
  writable = true
  mocks.api.mockImplementation(async (url, options) => {
    const schema = { mobile_doctype: 'field-interaction', doctype: 'Field Interaction', title: 'Field Interaction', fields: formFields }
    if (url.includes('get_form_schema')) return { message: schema }
    if (url.includes('get_prefill_values')) return { message: { values: formValues } }
    if (url.includes('get_mobile_doc_for_edit')) return { message: { schema, values: formValues, can_write: writable, files: [] } }
    if (url.includes('create_mobile_doc')) return { message: { name: 'FORM-1', route: '/forms' } }
    if (url.includes('update_mobile_doc')) return { message: { values: JSON.parse(options.body.get('values')), files: [], offline_queued: true, offline_operation_id: options.body.get('operation_id') } }
    return { message: { values: {} } }
  })
})
afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  document.body.innerHTML = ''
  sessionStorage.clear()
  localStorage.clear()
  vi.restoreAllMocks()
})

describe('Submission requirements', () => {
  it('uses section visibility, conditional mandatory and read-only rules instead of flagging every schema field', () => {
    const schema = [
      required('zero', 'Float'),
      required('calculated', 'Data', { read_only: true }),
      required('automatic', 'Data', { read_only_depends_on: 'eval:doc.locked' }),
      { fieldname: 'hidden_section', fieldtype: 'Section Break', depends_on: 'eval:doc.show_hidden' },
      required('hidden_answer'),
      { fieldname: 'next_tab', fieldtype: 'Tab Break', label: 'Signoff' },
      { fieldname: 'reason', label: 'Reason', fieldtype: 'Data', mandatory_depends_on: 'eval:doc.needs_reason' },
    ]
    expect(collectSubmissionIssues(schema, { zero: 0, locked: true, needs_reason: true }).map(issue => [issue.fieldname, issue.tabId])).toEqual([['reason', 'next_tab']])
    expect(collectSubmissionIssues(schema, { zero: 0, locked: true, needs_reason: false })).toEqual([])
  })

  it('distinguishes numeric zero, unchecked required acknowledgements, empty ratings and empty editor markup', () => {
    const schema = [required('count', 'Int'), required('accepted', 'Check'), required('mood', 'Rating'), required('body', 'Text Editor')]
    expect(collectSubmissionIssues(schema, { count: 0, accepted: false, mood: 0, body: '<p>&nbsp;<br></p>' }).map(issue => issue.fieldname)).toEqual(['accepted', 'mood', 'body'])
    expect(collectSubmissionIssues(schema, { count: 0, accepted: true, mood: 0.6, body: '<p>Safe to proceed</p>' })).toEqual([])
    expect(collectSubmissionIssues([required('body', 'Text Editor')], { body: '<p><img src="/files/site.png"></p>' })).toEqual([])
  })

  it('checks existing rows in optional tables with each row’s own visibility and requirement conditions', () => {
    const schema = [{ fieldname: 'entries', label: 'Entries', fieldtype: 'Table', child_fields: [
      { fieldname: 'reason', label: 'Reason', fieldtype: 'Data', mandatory_depends_on: 'eval:doc.flagged' },
      required('extra', 'Data', { depends_on: 'eval:doc.show_extra' }),
    ] }]
    const issues = collectSubmissionIssues(schema, { entries: [{ flagged: false }, { flagged: true, show_extra: false }] })
    expect(issues).toHaveLength(1)
    expect(issues[0]).toMatchObject({ fieldname: 'entries', childFieldname: 'reason', rowIndex: 1, location: 'Details · Entries · Row 2' })
    expect(collectSubmissionIssues(schema, { entries: [] })).toEqual([])
  })
})

describe('Submission checklist navigation and safe saves', () => {
  it.each([['new', NewDocument], ['edit', EditDocument]])('blocks incomplete %s forms without losing notes or photos, then links across tabs to the precise row', async (_, component) => {
    await render(component)
    const picker = wrapper.get('input[type="file"]')
    Object.defineProperty(picker.element, 'files', { value: [new File(['photo'], 'site.jpg', { type: 'image/jpeg' })] })
    await picker.trigger('change')
    await submit()
    expect(writes()).toHaveLength(0)
    expect(panel().text()).toContain('2 items need attention')
    expect(panel().text()).toContain('Review · Observations · Row 2')
    expect(wrapper.text()).toContain('site.jpg')
    expect(wrapper.findAllComponents(FormControl).find(field => field.props('label') === 'Notes').get('input').element.value).toBe('Keep my notes')
    const signature = panel().findAll('button').find(button => button.text().includes('Supervisor signature'))
    await signature.trigger('click')
    await flushPromises()
    expect(wrapper.findComponent(TabButtons).props('modelValue')).toBe('review_tab')
    expect(document.activeElement.dataset.formField).toBe('signature')
    const row = panel().findAll('button').find(button => button.text().includes('Observation detail'))
    await row.trigger('click')
    await flushPromises()
    expect(document.querySelector('[role="dialog"]')).toBeTruthy()
    expect(document.activeElement.closest('[data-form-field]').dataset.formField).toBe('detail')
    await click('Save Row')
    expect(writes()).toHaveLength(0)
    expect(document.querySelector('[aria-label="Submission checklist"] ul')).toBeTruthy()
  })

  it('opens an empty required table’s Add row editor and refuses an incomplete row before changing the parent', async () => {
    formValues.rows = []
    await render()
    await submit()
    const issue = panel().findAll('button').find(button => button.text().includes('Observations'))
    await issue.trigger('click')
    await flushPromises()
    expect(document.querySelector('[role="dialog"]').textContent).toContain('Add row')
    await click('Save Row')
    expect(table().props('modelValue')).toEqual([])
    expect(writes()).toHaveLength(0)
    await setField('Observation detail', 'Completed entry', table())
    await click('Save Row')
    expect(table().props('modelValue')).toEqual([{ detail: 'Completed entry' }])
    expect(panel().text()).toContain('1 item needs attention')
  })

  it('keeps the latest row and photos locally when another parent requirement blocks an automatic row save', async () => {
    formValues.rows = []
    await render(EditDocument)
    const picker = wrapper.get('input[type="file"]')
    Object.defineProperty(picker.element, 'files', { value: [new File(['photo'], 'retained.jpg')] })
    await picker.trigger('change')
    await click('Review') // switch to the Review tab
    await click('+ Add')
    await setField('Observation detail', 'First draft', table())
    await click('Save Row')
    expect(writes()).toHaveLength(0)
    expect(document.querySelector('[role="dialog"]').textContent).toContain('Other form items need attention')
    await setField('Observation detail', 'Latest row text', table())
    await click('Keep row and review form')
    expect(document.querySelector('[role="dialog"]')).toBeNull()
    expect(table().props('modelValue')).toEqual([{ detail: 'Latest row text' }])
    expect(panel().text()).toContain('Supervisor signature')
    expect(wrapper.text()).toContain('retained.jpg')
    wrapper.findComponent(SignatureField).vm.$emit('update:modelValue', 'data:image/png;base64,c2lnbmF0dXJl')
    await flushPromises()
    await submit()
    expect(writes()).toHaveLength(1)
    expect(JSON.parse(writes()[0][1].body.get('values'))).toMatchObject({ notes: 'Keep my notes', quantity: 0, rows: [{ detail: 'Latest row text' }] })
    expect(writes()[0][1].body.getAll('attachments')).toHaveLength(1)
  })

  it('updates the checklist as conditional requirements appear and disappear', async () => {
    formFields = [{ fieldname: 'flag', label: 'Flag', fieldtype: 'Data' },
      { fieldname: 'conditional', label: 'Explain', fieldtype: 'Data', mandatory_depends_on: 'eval:doc.flag == "yes"' }]
    formValues = {}
    await render()
    expect(panel().text()).toContain('No missing required items')
    await setField('Flag', 'yes')
    expect(panel().text()).toContain('1 item needs attention')
    await submit()
    expect(writes()).toHaveLength(0)
    await setField('Flag', 'no')
    expect(panel().text()).toContain('No missing required items')
    await submit()
    expect(writes()).toHaveLength(1)
  })

  it('preserves browser email validation in the checklist when native single-field popups are disabled', async () => {
    formFields = [{ fieldname: 'email', label: 'Email', fieldtype: 'Email' }]
    formValues = { email: 'invalid-email' }
    await render()
    expect(wrapper.get('form').attributes()).toHaveProperty('novalidate')
    await submit()
    expect(writes()).toHaveLength(0)
    expect(panel().text()).toContain('Email')
    await wrapper.get('input[type="email"]').setValue('crew@example.test')
    await flushPromises()
    expect(panel().text()).toContain('No missing required items')
    await submit()
    expect(writes()).toHaveLength(1)
  })

  it('keeps checklists and save controls out of read-only documents', async () => {
    writable = false
    await render(EditDocument)
    expect(wrapper.findComponent(SubmissionChecklist).exists()).toBe(false)
    expect(wrapper.text()).toContain('Read only')
    expect(writes()).toHaveLength(0)
  })

  it('requires completion of a half-selected optional datetime instead of silently dropping it', async () => {
    formFields = [{ fieldname: 'review_at', label: 'Review at', fieldtype: 'Datetime' }]
    formValues = {}
    await render()
    wrapper.findComponent(DatePicker).vm.$emit('update:modelValue', '2026-11-25')
    await flushPromises()
    await submit()
    expect(writes()).toHaveLength(0)
    expect(panel().text()).toContain('Review at')
    wrapper.findComponent(TimePicker).vm.$emit('update:modelValue', '10:15')
    await flushPromises()
    expect(panel().text()).toContain('No missing required items')
    await submit()
    expect(JSON.parse(writes()[0][1].body.get('values')).review_at).toBe('2026-11-25T10:15')
  })

  it('does not start a save if navigation unmounts the form while its checklist is being checked', async () => {
    formFields = [{ fieldname: 'notes', label: 'Notes', fieldtype: 'Data' }]
    await render()
    const pending = wrapper.get('form').trigger('submit')
    wrapper.unmount()
    wrapper = null
    await pending
    await flushPromises()
    expect(writes()).toHaveLength(0)
  })
})
