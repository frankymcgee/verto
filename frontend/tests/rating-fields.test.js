import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { Rating } from 'frappe-ui'
import RatingField from '../src/components/mobile-fields/RatingField.vue'
import ChildTableField from '../src/components/mobile-fields/ChildTableField.vue'
import NewDocument from '../src/pages/NewDocument.vue'
import EditDocument from '../src/pages/EditDocument.vue'

const mocks = vi.hoisted(() => ({ api: vi.fn(), back: vi.fn(), push: vi.fn() }))
vi.mock('vue-router', () => ({
  useRoute: () => ({
    params: { mobileDoctype: 'field-interaction', docname: 'FORM-1' },
    query: {},
    fullPath: '/forms/field-interaction',
  }),
  useRouter: () => ({ back: mocks.back, push: mocks.push }),
}))
vi.mock('../src/lib/api', () => ({ apiRequest: mocks.api }))
vi.mock('../src/lib/diagnostics', () => ({ reportClientError: vi.fn() }))
vi.mock('../src/pwa/offlineQueue', () => ({ createOfflineId: () => crypto.randomUUID() }))

let wrapper
let writable
let fields

const requests = method => mocks.api.mock.calls.filter(([url]) => url.includes(method))
const rating = label => wrapper.findAllComponents(RatingField).find(field => field.props('label') === label)
const choose = async (field, index) => {
  await field.find(`[data-slot="star"][data-index="${index}"]`).trigger('click')
  await flushPromises()
}

async function click(label) {
  const button = [...document.querySelectorAll('button')].find(node => node.textContent.trim() === label)
  expect(button, label).toBeTruthy()
  button.click()
  await flushPromises()
}

async function render(component) {
  wrapper = mount(component, { attachTo: document.body })
  await flushPromises()
}

beforeEach(() => {
  vi.clearAllMocks()
  writable = true
  fields = [
    { fieldname: 'mood', label: 'Mood', fieldtype: 'Rating', description: 'How was your day?', required: true },
    { fieldname: 'locked', label: 'Locked mood', fieldtype: 'Rating', read_only: true, default: '0.4' },
    { fieldname: 'rows', label: 'Entries', fieldtype: 'Table', child_fields: [
      { fieldname: 'note', label: 'Note', fieldtype: 'Data' },
      { fieldname: 'mood', label: 'Row mood', fieldtype: 'Rating', required: true },
    ] },
  ]
  const schema = () => ({ mobile_doctype: 'field-interaction', doctype: 'Field Interaction', title: 'Field interaction', fields })
  mocks.api.mockImplementation(async (url, options) => {
    if (url.includes('get_form_schema')) return { message: schema() }
    if (url.includes('get_prefill_values')) return { message: { values: {} } }
    if (url.includes('get_mobile_doc_for_edit')) return { message: {
      schema: schema(), can_write: writable,
      values: { mood: 0.6, locked: 0.4, rows: [{ note: 'Existing entry', mood: 0.4 }] },
    } }
    if (url.includes('update_mobile_doc')) return { message: { name: 'FORM-1', values: JSON.parse(options.body.get('values')) } }
    if (url.includes('create_mobile_doc')) return { message: { name: 'FORM-NEW', route: '/forms' } }
    return { message: { values: {} } }
  })
})

afterEach(() => {
  wrapper?.unmount()
  document.body.innerHTML = ''
  localStorage.clear()
  sessionStorage.clear()
})

describe('Frappe mood Rating field', () => {
  it.each([
    [undefined, 0], [null, 0], ['', 0], [0, 0], [0.2, 1], ['0.6', 3], [1, 5],
  ])('loads Frappe fraction %j as mood %i without changing the saved value', async (value, mood) => {
    wrapper = mount(RatingField, { props: { modelValue: value } })
    expect(wrapper.findComponent(Rating).props('modelValue')).toBe(mood)
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })

  it('renders the five faces in order and previews the hovered mood', async () => {
    wrapper = mount(RatingField, { props: { modelValue: 0.6, label: 'Mood' } })
    const faces = wrapper.findAll('[data-slot="star"]')
    expect(faces).toHaveLength(5)
    expect(faces.map(face => face.find('span span').text())).toEqual(['😞', '🙁', '😐', '🙂', '😊'])
    expect(faces[2].find('.scale-110').exists()).toBe(true)
    await faces[4].trigger('pointermove')
    expect(faces[4].find('.scale-110').exists()).toBe(true)
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    await wrapper.find('[role="radiogroup"]').trigger('mouseleave')
    expect(faces[2].find('.scale-110').exists()).toBe(true)
  })

  it('retains labels, descriptions, required status and disabled interaction', async () => {
    wrapper = mount(RatingField, { props: {
      modelValue: 0.6, label: 'Mood', description: 'How was your day?', required: true, disabled: true,
    } })
    expect(wrapper.text()).toContain('Mood')
    expect(wrapper.text()).toContain('How was your day?')
    expect(wrapper.find('[role="radiogroup"]').attributes()).toMatchObject({ 'aria-disabled': 'true', 'aria-required': 'true' })
    await choose(wrapper, 5)
    await wrapper.find('[role="radiogroup"]').trigger('keydown', { key: '1' })
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })
})

describe('Mood ratings in mobile documents and rows', () => {
  it('starts blank and submits the selected new-document mood as a Frappe fraction', async () => {
    await render(NewDocument)
    expect(rating('Mood').findComponent(Rating).props('modelValue')).toBe(0)
    expect(rating('Locked mood').findComponent(Rating).props('modelValue')).toBe(2)
    expect(rating('Locked mood').props('disabled')).toBe(true)
    await choose(rating('Mood'), 5)
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(JSON.parse(requests('create_mobile_doc')[0][1].body.get('values')).mood).toBe(1)
  })

  it('shows the existing mood and round-trips an edited mood through Save Changes', async () => {
    await render(EditDocument)
    expect(rating('Mood').find('[aria-checked="true"]').attributes('data-index')).toBe('3')
    await choose(rating('Mood'), 1)
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(JSON.parse(requests('update_mobile_doc')[0][1].body.get('values')).mood).toBe(0.2)
    expect(rating('Mood').find('[aria-checked="true"]').attributes('data-index')).toBe('1')
  })

  it('clears the selected mood and supports keyboard selection', async () => {
    await render(EditDocument)
    await choose(rating('Mood'), 3)
    expect(rating('Mood').props('modelValue')).toBe(0)
    expect(rating('Mood').find('[aria-checked="true"]').exists()).toBe(false)
    await rating('Mood').find('[role="radiogroup"]').trigger('keydown', { key: '4' })
    expect(rating('Mood').props('modelValue')).toBe(0.8)
  })

  it('sends fractions to dependent-field processing', async () => {
    await render(NewDocument)
    await choose(rating('Mood'), 4)
    await new Promise(resolve => setTimeout(resolve, 350))
    expect(requests('process_field_change')).toHaveLength(1)
    const body = requests('process_field_change')[0][1].body
    expect(body.get('changed_fieldname')).toBe('mood')
    expect(JSON.parse(body.get('values')).mood).toBe(0.8)
  })

  it('keeps field and document permissions on the rating controls', async () => {
    writable = false
    await render(EditDocument)
    expect(rating('Locked mood').props('disabled')).toBe(true)
    expect(rating('Mood').props('disabled')).toBe(true)
    await choose(rating('Mood'), 5)
    expect(rating('Mood').props('modelValue')).toBe(0.6)
    expect(requests('update_mobile_doc')).toHaveLength(0)
  })

  it('saves and reopens an existing child-row mood with one Save Row action', async () => {
    await render(EditDocument)
    const table = wrapper.findComponent(ChildTableField)
    await table.findAll('button').find(button => button.text().includes('Existing entry')).trigger('click')
    await flushPromises()
    const rowMood = table.findComponent(RatingField)
    expect(rowMood.findComponent(Rating).props('modelValue')).toBe(2)
    await choose(rowMood, 4)
    await click('Save Row')
    expect(requests('update_mobile_doc')).toHaveLength(1)
    const values = JSON.parse(requests('update_mobile_doc')[0][1].body.get('values'))
    expect(values.rows).toEqual([{ note: 'Existing entry', mood: 0.8 }])
    await table.findAll('button').find(button => button.text().includes('Existing entry')).trigger('click')
    await flushPromises()
    expect(table.findComponent(Rating).props('modelValue')).toBe(4)
  })

  it('keeps a new child-row mood in the draft and submits it with the new document', async () => {
    await render(NewDocument)
    await click('+ Add')
    const rowMood = wrapper.findComponent(ChildTableField).findComponent(RatingField)
    expect(rowMood.findComponent(Rating).props('modelValue')).toBe(0)
    await choose(rowMood, 5)
    await click('Save Row')
    expect(requests('create_mobile_doc')).toHaveLength(0)
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(JSON.parse(requests('create_mobile_doc')[0][1].body.get('values')).rows[0].mood).toBe(1)
  })

  it('disables child-row mood changes in a read-only document', async () => {
    writable = false
    await render(EditDocument)
    const table = wrapper.findComponent(ChildTableField)
    await table.findAll('button').find(button => button.text().includes('Existing entry')).trigger('click')
    await flushPromises()
    const rowMood = table.findComponent(RatingField)
    expect(rowMood.props('disabled')).toBe(true)
    await choose(rowMood, 5)
    expect(rowMood.props('modelValue')).toBe(0.4)
  })
})
