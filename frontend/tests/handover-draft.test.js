import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { Checkbox } from 'frappe-ui'
import HandoverDraftPanel from '../src/components/HandoverDraftPanel.vue'
import ChildTableField from '../src/components/mobile-fields/ChildTableField.vue'
import { defaultHandoverPeriod, handoverDraftHtml } from '../src/lib/handoverDraft'

const mocks = vi.hoisted(() => ({ api: vi.fn() }))
vi.mock('../src/lib/api', () => ({ apiRequest: mocks.api }))
const suggestion = () => ({
  fields: { shift_findings: 'Guarding needs follow-up [S1]', actions: 'Check the barrier [S1]' },
  sources: [{ id: 'S1', doctype: 'Field Interaction', name: 'FI-1', recorded_at: '2026-11-24 02:00:00', time_basis: 'submission timestamp', url: '/app/field-interaction/FI-1' }],
  warnings: ['Submission time may differ from event time.'],
  scope: { project: 'PROJ-1', period_start: '2026-11-23 18:00:00', period_end: '2026-11-24 06:00:00', timezone: 'Australia/Perth' },
})
const props = () => ({ handoverDoctype: 'Safety Handover', project: 'PROJ-1', docname: 'HANDOVER-1', rowDate: '2026-11-24 06:00:00', fieldLabels: { actions: 'Actions & Owners', shift_findings: 'Shift Findings' } })
let wrapper
async function click(text) {
  const button = [...document.querySelectorAll('button')].find(element => element.textContent.trim() === text)
  expect(button, text).toBeTruthy(); button.click(); await flushPromises()
}
beforeEach(() => { vi.clearAllMocks(); mocks.api.mockResolvedValue({ message: suggestion() }) })
afterEach(() => { wrapper?.unmount(); document.body.innerHTML = '' })

describe('PERI handover drafts', () => {
  it('prepares an overnight window and waits for an explicit apply without saving', async () => {
    wrapper = mount(HandoverDraftPanel, { props: props(), attachTo: document.body })
    await click('Prepare handover draft')
    const [url, options] = mocks.api.mock.calls[0]
    expect(url).toContain('prepare_handover_draft')
    expect(JSON.parse(options.body)).toMatchObject({ project: 'PROJ-1', docname: 'HANDOVER-1', period_start: '2026-11-23 18:00:00', period_end: '2026-11-24 06:00:00' })
    expect(wrapper.text()).toContain('Guarding needs follow-up')
    expect(wrapper.text()).toContain('Australia/Perth')
    expect(wrapper.get('a').attributes('href')).toBe('/app/field-interaction/FI-1')
    expect(wrapper.emitted('apply')).toBeUndefined()
    await click('Use draft in row')
    expect(wrapper.emitted('apply')[0]).toEqual([suggestion(), false])
    wrapper.findComponent(Checkbox).vm.$emit('update:modelValue', true)
    await flushPromises(); await click('Use draft in row')
    expect(wrapper.emitted('apply')[1][1]).toBe(true)
    expect(mocks.api).toHaveBeenCalledOnce()
  })

  it('blocks repeated generation and discards a result when the project changes', async () => {
    let complete
    mocks.api.mockImplementation(() => new Promise(resolve => { complete = resolve }))
    wrapper = mount(HandoverDraftPanel, { props: props(), attachTo: document.body })
    await click('Prepare handover draft')
    await click('Prepare handover draft')
    expect(mocks.api).toHaveBeenCalledOnce()
    await wrapper.setProps({ project: 'OTHER' })
    complete({ message: suggestion() }); await flushPromises()
    expect(wrapper.text()).not.toContain('Guarding needs follow-up')
    expect(wrapper.emitted('apply')).toBeUndefined()
    expect(wrapper.emitted('busy').at(-1)).toEqual([false])
  })

  it('shows provider failures and empty source coverage without offering apply', async () => {
    mocks.api.mockRejectedValueOnce(new Error('PERI is unavailable'))
    wrapper = mount(HandoverDraftPanel, { props: props(), attachTo: document.body })
    await click('Prepare handover draft')
    expect(wrapper.get('[role="alert"]').text()).toBe('PERI is unavailable')
    mocks.api.mockResolvedValueOnce({ message: { ...suggestion(), fields: {}, sources: [], warnings: ['No accessible source records.'] } })
    await click('Prepare handover draft')
    expect(wrapper.text()).toContain('No accessible source records.')
    expect(wrapper.text()).not.toContain('Use draft in row')
  })

  it('keeps existing row text unless replacement is selected and never applies signoff or incident counts', async () => {
    wrapper = mount(ChildTableField, { props: {
      parentDoctype: 'Safety Handover', parentName: 'HANDOVER-1', project: 'PROJ-1',
      modelValue: [{ date: '2026-11-24 06:00:00', shift_findings: 'Advisor notes', actions: '', incidents: 2, signoff: '' }],
      field: { fieldname: 'table_hhdr', label: 'Handover', options: 'Handover Information', child_fields: [
        { fieldname: 'date', fieldtype: 'Datetime', label: 'Date' },
        { fieldname: 'shift_findings', fieldtype: 'Small Text', label: 'Shift Findings' },
        { fieldname: 'actions', fieldtype: 'Small Text', label: 'Actions & Owners' },
        { fieldname: 'incidents', fieldtype: 'Int', label: 'Incidents' },
        { fieldname: 'signoff', fieldtype: 'Signature', label: 'Sign-off' },
      ] },
    }, attachTo: document.body })
    wrapper.findAll('button').find(button => button.text().includes('Edit')).element.click()
    await flushPromises()
    const panel = wrapper.findComponent(HandoverDraftPanel)
    expect(panel.exists()).toBe(true)
    panel.vm.$emit('apply', { ...suggestion(), fields: { ...suggestion().fields, incidents: 99, signoff: 'forged' } }, false)
    await flushPromises(); await click('Save Row')
    const row = wrapper.emitted('update:modelValue').at(-1)[0][0]
    expect(row).toMatchObject({ shift_findings: 'Advisor notes', actions: 'Check the barrier [S1]', incidents: 2, signoff: '' })
  })

  it('encodes generated text and only links citations to known local source records', () => {
    const html = handoverDraftHtml('<img src=x onerror=alert(1)> [S1] [S2]', [...suggestion().sources,
      { id: 'S2', url: 'javascript:alert(1)' }])
    const container = document.createElement('div'); container.innerHTML = html
    expect(container.querySelector('img')).toBeNull()
    expect(container.textContent).toContain('<img src=x onerror=alert(1)>')
    expect(container.querySelectorAll('a')).toHaveLength(1)
    expect(container.querySelector('a').getAttribute('href')).toBe('/app/field-interaction/FI-1')
    expect(defaultHandoverPeriod('2026-11-24 06:00:00')).toEqual({ start: '2026-11-23T18:00:00', end: '2026-11-24T06:00:00' })
  })
})
