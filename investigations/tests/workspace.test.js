import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import App from '../src/App.vue'
import { call } from '../src/api'
import { draft } from '../src/model'

vi.mock('../src/api', () => ({ call: vi.fn(), uploadFile: vi.fn() }))
const Button = defineComponent({
  props: ['disabled'],
  emits: ['click'],
  template:
    '<button type="button" :disabled="disabled" @click="$emit(\'click\', $event)"><slot /></button>',
})
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
  return wrapper.findAll('button').find((item) => item.text() === text)
}
function field(text) {
  return wrapper
    .findAll('label.field')
    .find((item) => item.find('span').text() === text)
    .find('input,textarea,select')
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
  wrapper = mount(App, { global: { components: { Button } } })
  await flushPromises()
}
beforeEach(() => {
  call.mockReset()
  vi.spyOn(window, 'confirm').mockReturnValue(false)
  vi.spyOn(window, 'print').mockImplementation(() => {})
  Element.prototype.scrollIntoView = vi.fn()
})
afterEach(() => {
  wrapper?.unmount()
  vi.restoreAllMocks()
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
    await button('← Investigations').trigger('click')
    await flushPromises()
    expect(window.confirm).toHaveBeenCalledOnce()
    expect(field('Investigation title *').element.value).toBe('Unsaved finding')
    expect(window.location.hash).toContain('INV-00001')
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
    expect(field('Time precision').element.value).toBe('Date only')
    expect(field('Incident date and time *').element.value).toBe('2026-10-17T00:00')
  })
  it('does not offer editing or self-review on a submitted investigation', async () => {
    await open(
      'INV-00001',
      record({ status: 'In Review', capabilities: { can_edit: false, can_review: false } }),
    )
    expect(button('Save investigation')).toBeUndefined()
    expect(field('Investigation title *').element.closest('fieldset').disabled).toBe(true)
    expect(wrapper.text()).toContain('Submitted for independent review')
    await wrapper
      .findAll('nav button')
      .find((item) => item.text().includes('Review & close-out'))
      .trigger('click')
    expect(button('Approve findings and actions')).toBeUndefined()
  })
  it('shows 5 Whys and ICAM together when both methods are selected', async () => {
    await open('INV-00001', record({ method: '5 Whys + ICAM' }))
    expect(
      wrapper
        .findAll('nav button')
        .map((item) => item.text())
        .join(' '),
    ).toContain('5 Whys')
    expect(
      wrapper
        .findAll('nav button')
        .map((item) => item.text())
        .join(' '),
    ).toContain('ICAM analysis')
    await wrapper
      .findAll('nav button')
      .find((item) => item.text().includes('5 Whys'))
      .trigger('click')
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
    await wrapper
      .findAll('nav button')
      .find((item) => item.text().includes('Review & close-out'))
      .trigger('click')
    await button('Withdraw for revision').trigger('click')
    await wrapper
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
    await wrapper
      .findAll('nav button')
      .find((item) => item.text().includes('Corrective actions'))
      .trigger('click')
    await button('Reassign responsibilities').trigger('click')
    const selects = wrapper.findAll('.decision-panel select')
    expect(selects[0].element.disabled).toBe(true)
    await selects[1].setValue('replacement@example.test')
    await wrapper.get('.decision-panel textarea').setValue('Replacement verifier appointed.')
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
