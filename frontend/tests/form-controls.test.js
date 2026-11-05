import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { TabButtons, Select, DatePicker, Checkbox } from 'frappe-ui'
import NewDocument from '../src/pages/NewDocument.vue'
const mocked = vi.hoisted(() => ({ api: vi.fn(), push: vi.fn() }))
vi.mock('vue-router', () => ({
  useRoute: () => ({
    params: { mobileDoctype: 'Daily Timesheet' },
    query: {},
    fullPath: '/new/Daily%20Timesheet',
  }),
  useRouter: () => ({ push: mocked.push }),
}))
vi.mock('../src/lib/api', () => ({ apiRequest: mocked.api }))
vi.mock('../src/lib/diagnostics', () => ({ reportClientError: vi.fn() }))
vi.mock('../src/pwa/offlineQueue', () => ({
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
async function render() {
  mocked.api.mockImplementation(async (url) => {
    if (url.includes('get_form_schema'))
      return {
        message: {
          mobile_doctype: 'Daily Timesheet',
          doctype: 'Daily Timesheet',
          title: 'Daily Timesheet',
          fields,
        },
      }
    if (url.includes('get_prefill_values')) return { message: { values: {} } }
    if (url.includes('create_mobile_doc'))
      return { message: { doctype: 'Daily Timesheet', name: 'TS-1' } }
    return { message: { values: {} } }
  })
  w = mount(NewDocument, { attachTo: document.body })
  await flushPromises()
  return w
}
afterEach(() => {
  w?.unmount()
  document.body.innerHTML = ''
  localStorage.clear()
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
})
