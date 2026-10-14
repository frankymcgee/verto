import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import JhaActiveStep from '../src/components/JhaActiveStep.vue'
import { apiRequest } from '../src/lib/api'

vi.mock('../src/lib/api', () => ({ apiRequest: vi.fn() }))
const jha = { name: 'JHA-1', revision: 1, status: 'Signed', work_steps: [
  { name: 'STEP-1', sequence: 1, activity: 'Restrain pump' }, { name: 'STEP-2', sequence: 2, activity: 'Lift pump' },
] }
const briefing = (step = 'STEP-1', status = 'matches') => ({ jha: 'JHA-1', revision: 1, current_revision: true, can_select: true,
  active_step: step ? { name: `BRIEF-${step}`, step_row: step, sequence: step === 'STEP-1' ? 1 : 2,
    activity: step === 'STEP-1' ? 'Restrain pump' : 'Lift pump', selected_by: 'Crew lead', selected_at: '2026-10-14 10:00',
    hold_or_pause_point: true, hazards: [{ name: 'H-1', hazard_or_energy_source: 'Stored energy', critical_control: 'Mechanical restraint', control_owner: 'Supervisor' }],
    critical_controls: [{ name: 'H-1', control: 'Mechanical restraint', status: 'Pending' }] } : null,
  incident_learning: step ? { status, work_step_sequence: 1, incidents: status === 'matches' ? [{
    name: 'INC-1', source_system: 'INX', source_reference: 'INC-101', incident_date: '2025-01-02',
    incident_summary: 'Stored pressure released during maintenance.', record_url: '/app/jha-incident-learning/INC-1',
    investigation_findings: 'Restraint missing', investigation_actions: 'Install a restraint', actions_available: true,
  }] : [] } : null })
let wrapper
beforeEach(() => { vi.clearAllMocks(); apiRequest.mockResolvedValue({ message: briefing(null) }) })
afterEach(() => wrapper?.unmount())
async function open(props = {}) {
  wrapper = mount(JhaActiveStep, { props: { jha, online: true, ...props } })
  await flushPromises()
}

describe('JHA execution step picker', () => {
  it('restores the saved step and shows incident facts, controls, owners and hold point', async () => {
    apiRequest.mockResolvedValue({ message: briefing() }); await open()
    expect(wrapper.find('select').element.value).toBe('STEP-1')
    expect(wrapper.text()).toContain('Stored pressure released during maintenance.')
    expect(wrapper.text()).toContain('INC-101 · 2025-01-02')
    expect(wrapper.text()).toContain('Restraint missing')
    expect(wrapper.text()).toContain('Install a restraint')
    expect(wrapper.text()).toContain('Mechanical restraint')
    expect(wrapper.text()).toContain('Supervisor')
    expect(wrapper.text()).toContain('Field verification: Pending')
    expect(wrapper.text()).toContain('in place and effective')
    expect(apiRequest.mock.calls[0][1]).toEqual({ cache: 'no-store' })
    expect(wrapper.emitted('briefing').at(-1)[1]).toBe(false)
  })
  it('saves the exact step row before asking PERI to brief it', async () => {
    await open(); apiRequest.mockResolvedValue({ message: briefing('STEP-2') })
    await wrapper.find('select').setValue('STEP-2'); await flushPromises()
    const [url, options] = apiRequest.mock.calls.at(-1)
    expect(url).toContain('select_jha_active_step')
    expect(options.body.get('step_row')).toBe('STEP-2')
    expect(options.body.get('jha_name')).toBe('JHA-1')
    expect(options.body.get('request_id')).toBeTruthy()
    expect(wrapper.emitted('briefing').at(-1)).toEqual([briefing('STEP-2'), true])
    expect(wrapper.text()).toContain('Active: 2. Lift pump')
  })
  it('retains the saved selection and reports a rejected or superseded request', async () => {
    apiRequest.mockResolvedValue({ message: briefing() }); await open()
    apiRequest.mockRejectedValue(Error('Use the current signed revision.'))
    await wrapper.find('select').setValue('STEP-2'); await flushPromises()
    expect(wrapper.find('select').element.value).toBe('STEP-1')
    expect(wrapper.find('[role=alert]').text()).toContain('current signed revision')
    expect(wrapper.emitted('briefing').filter(([, selected]) => selected)).toHaveLength(0)
  })
  it('does not request a voice briefing after leaving while a selection is saving', async () => {
    const listener = vi.fn()
    await open({ onBriefing: listener })
    listener.mockClear()
    let finish
    apiRequest.mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
    await wrapper.find('select').setValue('STEP-1'); await flushPromises()
    wrapper.unmount()
    finish({ message: briefing() }); await flushPromises()
    expect(listener).not.toHaveBeenCalled()
  })
  it.each(['no_matches', 'unavailable'])('clearly reports %s without implying safety', async status => {
    apiRequest.mockResolvedValue({ message: briefing('STEP-1', status) }); await open()
    expect(wrapper.text()).toContain(status === 'unavailable' ? 'Incident evidence is unavailable' : 'No relevant incidents found')
    expect(wrapper.text()).toContain('Continue assessing this step')
    expect(wrapper.text()).toContain('in place and effective')
  })
  it('requires an online signed revision and blocks selection while voice work is pending', async () => {
    await open({ online: false })
    expect(apiRequest).not.toHaveBeenCalled(); expect(wrapper.find('select').element.disabled).toBe(true)
    await wrapper.setProps({ online: true }); await flushPromises()
    await wrapper.setProps({ busy: true }); expect(wrapper.find('select').element.disabled).toBe(true)
    await wrapper.setProps({ jha: { ...jha, status: 'Superseded' } }); await flushPromises()
    expect(wrapper.find('select').exists()).toBe(false)
  })
  it('ignores stale reads when the JHA revision changes and does not refetch for equal snapshots', async () => {
    let finish
    apiRequest.mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
    await open()
    apiRequest.mockResolvedValue({ message: { ...briefing(null), jha: 'JHA-2', revision: 2 } })
    await wrapper.setProps({ jha: { ...jha, name: 'JHA-2', revision: 2 } }); await flushPromises()
    finish({ message: briefing() }); await flushPromises()
    expect(wrapper.text()).not.toContain('INC-101')
    const requests = apiRequest.mock.calls.length
    await wrapper.setProps({ jha: { ...jha, name: 'JHA-2', revision: 2 } }); await flushPromises()
    expect(apiRequest).toHaveBeenCalledTimes(requests)
  })
  it('lets the crew request a discussion or change without attesting controls for them', async () => {
    apiRequest.mockResolvedValue({ message: briefing() }); await open()
    const buttons = wrapper.findAll('button')
    await buttons.find(item => item.text() === 'Ask PERI about this step').trigger('click')
    await buttons.find(item => item.text() === 'Review/change JHA').trigger('click')
    expect(wrapper.emitted('discuss')).toHaveLength(1); expect(wrapper.emitted('requestChange')).toHaveLength(1)
    expect(apiRequest).toHaveBeenCalledTimes(1)
  })
})
