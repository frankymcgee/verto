import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Combobox, FormControl, Select, SidebarItem } from 'frappe-ui'
import { DOMWrapper, flushPromises, mount } from '@vue/test-utils'
import App from '../src/App.vue'
import { call } from '../src/api'
import { categories, draft } from '../src/model'

const factorGroups = [
  {
    category: categories[0],
    group: categories[0],
    options: ['DF1 - Detection Systems', 'DF4 - Guards or Barriers', 'DF16 - Other'],
  },
  {
    category: categories[1],
    group: categories[1],
    options: ['IT1 - Supervisory error or violation', 'IT14 - Other'],
  },
  {
    category: categories[2],
    group: 'Task / Environmental Conditions (TE)',
    options: ['TE1 - Task Planning / Preparation / Manning', 'TE26 - Purchasing'],
  },
  {
    category: categories[2],
    group: 'Human Factors (HF)',
    options: ['HF4 - Fatigue', 'HF26 - Other human factor'],
  },
  {
    category: categories[3],
    group: categories[3],
    options: ['MC - Management of Change', 'VM - Vehicle Management'],
  },
]

vi.mock('../src/api', () => ({ call: vi.fn(), uploadFile: vi.fn() }))
let wrapper
const clone = (value) => JSON.parse(JSON.stringify(value))
function record(extra = {}) {
  return {
    ...draft('lead@example.test'),
    name: 'INV-00001',
    title: 'Coupling movement during alignment',
    incident_datetime: '2026-10-18 08:00:00',
    modified: '2026-10-18 09:00:00.000001',
    ...extra,
  }
}
function button(text) {
  return new DOMWrapper(document.body).findAll('button').find((item) => item.text() === text)
}
function control(text) {
  return wrapper
    .findAllComponents(FormControl)
    .find((item) => item.props('label') === text.replace(' *', ''))
}
function field(text) {
  return control(text).find('input,textarea')
}
function section(text) {
  return wrapper
    .findAllComponents(SidebarItem)
    .find((item) => item.props('label') === text)
    .find('button')
}
async function open(hash = '', value = record()) {
  window.history.replaceState(null, '', '/#/' + hash)
  call.mockImplementation(async (method, params) => {
    if (method === 'get_bootstrap')
      return {
        user: 'lead@example.test',
        full_name: 'Lead Investigator',
        apps: [],
        statuses: ['Draft', 'In Review', 'Closed'],
        icam_factor_groups: factorGroups,
      }
    if (method === 'list_investigations') return { items: [], counts: {}, today: '2026-10-18' }
    if (method === 'get_investigation') return clone(value)
    if (method === 'search_options') return []
    if (method === 'save_investigation')
      return {
        ...clone(params.data),
        name: 'INV-00001',
        modified: '2026-10-18 09:01:00.000001',
        readiness: ['Record evidence.'],
      }
    return clone(value)
  })
  wrapper = mount(App, { attachTo: document.body })
  await flushPromises()
}
beforeEach(() => {
  call.mockReset()
  window.innerWidth = 1280
  vi.spyOn(window, 'print').mockImplementation(() => {})
  Element.prototype.scrollIntoView = vi.fn()
})
afterEach(() => {
  wrapper?.unmount()
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

describe('investigations workspace', () => {
  it('opens a dedicated dashboard and starts a new investigation', async () => {
    await open()
    expect(wrapper.text()).toContain('Start with the facts')
    await button('New investigation').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Unsaved draft')
    expect(wrapper.text()).toContain('Incident overview')
    expect(field('Investigation title *').element.value).toBe('')
  })
  it('saves a draft through the authenticated API with the current revision', async () => {
    await open('INV-00001')
    await field('Investigation title *').setValue('Updated factual title')
    await button('Save investigation').trigger('click')
    await flushPromises()
    expect(call).toHaveBeenCalledWith(
      'save_investigation',
      expect.objectContaining({
        expected_modified: '2026-10-18 09:00:00.000001',
        data: expect.objectContaining({ title: 'Updated factual title' }),
      }),
    )
    expect(wrapper.text()).not.toContain('Unsaved changes')
  })
  it('retains unsaved changes when navigation is declined', async () => {
    await open('INV-00001')
    await field('Investigation title *').setValue('Unsaved finding')
    await button('Investigations').trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('Discard unsaved changes?')
    await button('Keep editing').trigger('click')
    await flushPromises()
    expect(field('Investigation title *').element.value).toBe('Unsaved finding')
    expect(window.location.hash).toContain('INV-00001')
  })
  it('discards unsaved changes only after confirmation and returns to the dashboard', async () => {
    await open('INV-00001')
    await field('Investigation title *').setValue('Unsaved finding')
    await button('Investigations').trigger('click')
    await flushPromises()
    expect(window.location.hash).toContain('INV-00001')
    await button('Discard changes').trigger('click')
    await flushPromises()
    expect(window.location.hash).toBe('#/')
    expect(wrapper.text()).toContain('Start with the facts')
    expect(wrapper.find('.record-content').exists()).toBe(false)
  })
  it('preserves date-only precision when copying a shutdown incident', async () => {
    await open(
      'INV-00001',
      record({
        incident_datetime: '',
        source_doctype: 'Shutdown Incident Tracker',
        source_name: 'INC-001',
      }),
    )
    call.mockImplementation(async (method) =>
      method === 'get_source_details'
        ? { incident_datetime: '2026-10-17 00:00:00', incident_time_precision: 'Date only' }
        : [],
    )
    await button('Use incident details in empty fields').trigger('click')
    await flushPromises()
    expect(control('Time precision').vm.$attrs.modelValue).toBe('Date only')
    expect(field('Incident date and time *').element.value).toBe('2026-10-17 00:00')
  })
  it('does not offer editing or self-review on a submitted investigation', async () => {
    await open(
      'INV-00001',
      record({ status: 'In Review', capabilities: { can_edit: false, can_review: false } }),
    )
    expect(button('Save investigation')).toBeUndefined()
    expect(field('Investigation title *').element.closest('fieldset').disabled).toBe(true)
    expect(control('Analysis method').getComponent(Select).props('disabled')).toBe(true)
    expect(wrapper.text()).toContain('Submitted for independent review')
    await section('Review & close-out').trigger('click')
    expect(button('Approve findings and actions')).toBeUndefined()
  })
  it('shows 5 Whys and ICAM together when both methods are selected', async () => {
    await open('INV-00001', record({ method: '5 Whys + ICAM' }))
    expect(
      wrapper
        .findAllComponents(SidebarItem)
        .map((item) => item.text())
        .join(' '),
    ).toContain('5 Whys')
    expect(
      wrapper
        .findAllComponents(SidebarItem)
        .map((item) => item.text())
        .join(' '),
    ).toContain('ICAM analysis')
    await section('5 Whys').trigger('click')
    await button('Add causal branch').trigger('click')
    expect(wrapper.text()).toContain('Why 1')
    expect(wrapper.text()).toContain('Supporting evidence')
  })
  it('retains the local draft and explains a stale save failure', async () => {
    await open('INV-00001')
    call.mockImplementation(async (method) => {
      if (method === 'save_investigation')
        throw new Error('This investigation changed. Reload it before saving your changes.')
      return {}
    })
    await field('Investigation title *').setValue('My local draft')
    await button('Save investigation').trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('Reload it')
    expect(field('Investigation title *').element.value).toBe('My local draft')
    expect(wrapper.text()).toContain('Unsaved changes')
  })
  it('filters ICAM dropdowns by category and saves a selected code without inventing a finding', async () => {
    await open('INV-00001', record({ method: 'ICAM' }))
    await section('ICAM analysis').trigger('click')
    const sections = wrapper.findAll('.icam-category')
    await sections[0].get('button').trigger('click')
    await sections[2].get('button').trigger('click')
    const defence = sections[0].getComponent(Combobox)
    expect(defence.props('placeholder')).toBe('Select factor from list')
    expect(defence.props('options').flatMap((group) => group.options)).toEqual(
      factorGroups[0].options,
    )
    await defence.get('[data-slot="trigger"]').trigger('click')
    await flushPromises()
    const body = new DOMWrapper(document.body)
    await body
      .findAll('[role="option"]')
      .find((option) => option.text() === 'DF1 - Detection Systems')
      .trigger('click')
    await flushPromises()
    const conditions = sections[2].getComponent(Combobox)
    await conditions.get('[data-slot="trigger"]').trigger('click')
    await flushPromises()
    expect(body.text()).toContain('Task / Environmental Conditions (TE)')
    expect(body.text()).toContain('Human Factors (HF)')
    await body.get('[data-slot="search"] input').setValue('fatigue')
    await flushPromises()
    expect(body.findAll('[role="option"]').map((option) => option.text())).toEqual([
      'HF4 - Fatigue',
    ])
    await body.get('[role="option"]').trigger('click')
    await button('Save investigation').trigger('click')
    await flushPromises()
    const saved = call.mock.calls.find(([method]) => method === 'save_investigation')[1].data
      .icam_factors
    expect(saved.map((row) => row.factor_type)).toEqual([
      'DF1 - Detection Systems',
      'HF4 - Fatigue',
    ])
    expect(
      saved.every((row) => row.description === '' && row.finding_status === 'Hypothesis'),
    ).toBe(true)
    expect(wrapper.get('.investigation-report').text()).toContain('DF1 - Detection Systems')
    expect(wrapper.get('.investigation-report').text()).toContain('HF4 - Fatigue')
  })
  it('retains coded factors in the locked form, causal map and print report', async () => {
    const factor = {
      entry_id: 'F-000000000001',
      category: categories[0],
      factor_type: 'DF4 - Guards or Barriers',
      description: 'No movement barrier was specified.',
      finding_status: 'Supported',
    }
    await open(
      'INV-00001',
      record({
        method: 'ICAM',
        status: 'Closed',
        capabilities: { can_edit: false },
        icam_factors: [factor],
      }),
    )
    await section('ICAM analysis').trigger('click')
    const box = wrapper
      .findAllComponents(Combobox)
      .find((item) => item.props('label') === 'ICAM factor')
    expect(box.props('disabled')).toBe(true)
    expect(box.props('modelValue')).toBe(factor.factor_type)
    expect(wrapper.get('.icam-map').text()).toContain(factor.factor_type)
    expect(wrapper.get('.icam-map').text()).toContain(factor.description)
    expect(wrapper.get('.investigation-report').text()).toContain(factor.factor_type)
    await button('Print / PDF').trigger('click')
    await flushPromises()
    expect(window.print).toHaveBeenCalledOnce()
  })
  it('prints the saved investigation and renders narratives as text', async () => {
    await open(
      'INV-00001',
      record({ description: '<img src=x onerror="alert(1)">', capabilities: { can_edit: false } }),
    )
    expect(wrapper.find('.investigation-report').text()).toContain('<img src=x')
    expect(wrapper.find('.investigation-report img').exists()).toBe(false)
    await button('Print / PDF').trigger('click')
    await flushPromises()
    expect(window.print).toHaveBeenCalledOnce()
    expect(call.mock.calls.filter(([method]) => method === 'save_investigation')).toHaveLength(0)
  })
  it('records a reason when withdrawing a submitted investigation for revision', async () => {
    await open(
      'INV-00001',
      record({ status: 'In Review', capabilities: { can_edit: false, can_withdraw: true } }),
    )
    await section('Review & close-out').trigger('click')
    await button('Withdraw for revision').trigger('click')
    await flushPromises()
    await new DOMWrapper(document.body)
      .get('.decision-panel textarea')
      .setValue('The appointed reviewer has left the business.')
    await button('Record decision').trigger('click')
    await flushPromises()
    expect(call).toHaveBeenCalledWith(
      'transition',
      expect.objectContaining({
        action: 'withdraw_review',
        notes: 'The appointed reviewer has left the business.',
      }),
    )
  })
  it('reassigns a completed action verifier while preserving its owner', async () => {
    const value = record({
      status: 'Actions in Progress',
      capabilities: { can_edit: false },
      reviewer: 'reviewer@example.test',
      team: [{ user: 'replacement@example.test', team_role: 'Investigator' }],
      actions: [
        {
          entry_id: 'A-000000000001',
          title: 'Update the controlled work pack',
          action_status: 'Completed',
          assigned_to_user: 'lead@example.test',
          verifier: 'reviewer@example.test',
          completed_by: 'lead@example.test',
          can_reassign: true,
        },
      ],
    })
    await open('INV-00001', value)
    await section('Corrective actions').trigger('click')
    await button('Reassign responsibilities').trigger('click')
    await flushPromises()
    const selects = wrapper
      .findAllComponents(Select)
      .filter((item) => item.element.closest('.decision-panel'))
    expect(selects[0].props('disabled')).toBe(true)
    selects[1].vm.$emit('update:modelValue', 'replacement@example.test')
    await flushPromises()
    await new DOMWrapper(document.body)
      .get('.decision-panel textarea')
      .setValue('Replacement verifier appointed.')
    await button('Record decision').trigger('click')
    await flushPromises()
    expect(call).toHaveBeenCalledWith(
      'update_action',
      expect.objectContaining({
        action: 'reassign',
        assigned_to_user: 'lead@example.test',
        verifier: 'replacement@example.test',
        notes: 'Replacement verifier appointed.',
      }),
    )
  })
})
