import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { TabButtons, Select, DatePicker, TimePicker, Checkbox, FormControl } from 'frappe-ui'
import ChildTableField from '../src/components/mobile-fields/ChildTableField.vue'
import DateTimeField from '../src/components/mobile-fields/DateTimeField.vue'
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

describe('Mobile date and time pickers', () => {
  const timesheetFields = [
    fields[0],
    { fieldname: 'start_time', fieldtype: 'Time', label: 'Start Time', default: '18:07:00' },
    { fieldname: 'end_time', fieldtype: 'Time', label: 'End Time', read_only: true, default: '06:29:00' },
    { fieldname: 'review_at', fieldtype: 'Datetime', label: 'Review at' },
  ]

  async function choose(picker, selector) {
    const input = picker.find('input')
    expect(input.element.readOnly).toBe(true)
    await input.trigger('click')
    const option = document.querySelector(selector)
    expect(option, selector).toBeTruthy()
    option.click()
    await flushPromises()
    return input.element.value
  }

  it.each([
    ['new', NewDocument, 'create_mobile_doc'],
    ['existing', EditDocument, 'update_mobile_doc'],
  ])('opens Frappe pickers from the value in the %s timesheet and saves the selected time', async (_, component, method) => {
    await render(component, timesheetFields, {
      date: '2026-09-14', start_time: '18:07:00', end_time: '06:29:00', review_at: '2026-09-14 13:37:00',
    })
    const startTime = w.findAllComponents(TimePicker).find(picker => picker.props('label') === 'Start Time')
    const endTime = w.findAllComponents(TimePicker).find(picker => picker.props('label') === 'End Time')
    expect(startTime.find('input').element.value).toBe('18:07')
    expect(endTime.find('input').element.disabled).toBe(true)
    expect(await choose(startTime, '[role="option"][data-value="18:15"]')).toBe('18:15')
    expect(await choose(w.findComponent(DatePicker), '[role="gridcell"][data-value="2026-09-15"]')).toBe('2026-09-15')

    await w.find('form').trigger('submit')
    await flushPromises()
    const request = mocked.api.mock.calls.find(([url]) => url.includes(method))
    expect(JSON.parse(request[1].body.get('values'))).toMatchObject({
      date: '2026-09-15', start_time: '18:15:00', end_time: '06:29:00',
    })
  })

  it('lists quarter-hour options and preserves an existing off-interval time', async () => {
    w = mount(DateTimeField, {
      attachTo: document.body,
      props: { fieldtype: 'Time', label: 'Start Time', modelValue: '18:07' },
    })
    const input = w.findComponent(TimePicker).find('input')
    expect(input.element.readOnly).toBe(true)
    await input.trigger('click')
    await flushPromises()
    const options = [...document.querySelectorAll('[role="listbox"] [role="option"]')]
      .map(option => option.dataset.value)
    expect(options).toHaveLength(96)
    expect(options.slice(0, 4)).toEqual(['00:00', '00:15', '00:30', '00:45'])
    expect(options.at(-1)).toBe('23:45')
    expect(options.every(time => /:(00|15|30|45)$/.test(time))).toBe(true)
    await input.trigger('blur')
    expect(input.element.value).toBe('18:07')
    expect(w.emitted('update:modelValue')).toBeUndefined()
  })

  it('commits a tapped time when the trigger blurs before the option click', async () => {
    w = mount(DateTimeField, {
      attachTo: document.body,
      props: { fieldtype: 'Time', label: 'Start Time' },
    })
    const input = w.findComponent(TimePicker).find('input')
    input.element.focus()
    await input.trigger('click')
    input.element.blur()
    await flushPromises()

    const option = document.querySelector('[role="option"][data-value="06:15"]')
    expect(option).toBeTruthy()
    option.click()
    await flushPromises()
    expect(input.element.value).toBe('06:15')
    expect(w.emitted('update:modelValue')).toEqual([['06:15']])
    expect(document.querySelector('[role="listbox"]')).toBeNull()
  })

  it('commits a touch selection without a mouse click and leaves swipes alone', async () => {
    await render(NewDocument, [
      fields[0],
      { fieldname: 'start_time', fieldtype: 'Time', label: 'Start Time' },
    ])
    const input = w.findComponent(TimePicker).find('input')
    await input.trigger('click')
    const option = document.querySelector('[role="option"][data-value="06:15"]')
    expect(option).toBeTruthy()

    function touch(type, clientY) {
      const point = { identifier: 1, target: option, clientX: 12, clientY }
      const event = new TouchEvent(type, {
        bubbles: true,
        cancelable: true,
        touches: type === 'touchend' ? [] : [point],
        changedTouches: [point],
      })
      option.dispatchEvent(event)
      return event
    }

    touch('touchstart', 25)
    touch('touchmove', 60)
    expect(touch('touchend', 60).defaultPrevented).toBe(false)
    expect(input.element.value).toBe('')

    touch('touchstart', 25)
    expect(touch('touchend', 27).defaultPrevented).toBe(true)
    await flushPromises()
    expect(input.element.value).toBe('06:15')
    expect(document.querySelector('[role="listbox"]')).toBeNull()

    await w.find('form').trigger('submit')
    await flushPromises()
    const request = mocked.api.mock.calls.find(([url]) => url.includes('create_mobile_doc'))
    expect(JSON.parse(request[1].body.get('values')).start_time).toBe('06:15:00')
  })

  it('dismisses the time picker when focus moves to another control', async () => {
    w = mount(DateTimeField, {
      attachTo: document.body,
      props: { fieldtype: 'Time', label: 'Start Time', modelValue: '18:07' },
    })
    const input = w.findComponent(TimePicker).find('input')
    const outside = document.createElement('button')
    document.body.append(outside)
    input.element.focus()
    await input.trigger('click')
    expect(document.querySelector('[role="listbox"]')).toBeTruthy()
    outside.focus()
    await flushPromises()

    expect(document.querySelector('[role="listbox"]')).toBeNull()
    expect(input.element.value).toBe('18:07')
    expect(w.emitted('update:modelValue')).toBeUndefined()
  })

  it('preserves local date and minute values and clears an optional datetime', async () => {
    w = mount(DateTimeField, {
      attachTo: document.body,
      props: { fieldtype: 'Datetime', label: 'Review at', modelValue: '2026-09-14 13:37:00' },
    })
    const date = w.findComponent(DatePicker)
    const time = w.findComponent(TimePicker)
    expect(date.find('input').element.value).toBe('2026-09-14')
    expect(time.find('input').element.value).toBe('13:37')

    await choose(date, '[role="gridcell"][data-value="2026-09-15"]')
    expect(w.emitted('update:modelValue').at(-1)).toEqual(['2026-09-15T13:37'])
    await w.setProps({ modelValue: '2026-09-15T13:37' })
    await choose(time, '[role="option"][data-value="13:45"]')
    expect(w.emitted('update:modelValue').at(-1)).toEqual(['2026-09-15T13:45'])
    await w.find('button[aria-label="Clear Review at"]').trigger('click')
    expect(w.emitted('update:modelValue').at(-1)).toEqual([''])
  })

  it('keeps required validation for a picker-only input', async () => {
    w = mount(DateTimeField, { props: { fieldtype: 'Time', label: 'Start Time', required: true } })
    const validation = w.find('select[required]').element
    expect(validation.validity.valueMissing).toBe(true)
    expect(w.findComponent(TimePicker).find('input').element.readOnly).toBe(true)
    await w.setProps({ modelValue: '00:00' })
    expect(validation.checkValidity()).toBe(true)
    await w.setProps({ modelValue: '', disabled: true })
    expect(validation.checkValidity()).toBe(true)
  })

  it('waits for an explicit time before saving a newly selected datetime', async () => {
    w = mount(DateTimeField, { attachTo: document.body, props: { fieldtype: 'Datetime', label: 'Review at' } })
    await w.findComponent(DatePicker).find('input').trigger('click')
    const today = [...document.querySelectorAll('button')].find(button => button.textContent.trim() === 'Today')
    today.click()
    await flushPromises()
    const date = w.findComponent(DatePicker).find('input').element.value
    expect(date).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    expect(w.emitted('update:modelValue')).toBeUndefined()
    expect(w.find('select[required]').element.validity.valueMissing).toBe(true)
    await choose(w.findComponent(TimePicker), '[role="option"][data-value="00:15"]')
    expect(w.emitted('update:modelValue').at(-1)).toEqual([`${date}T00:15`])
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
