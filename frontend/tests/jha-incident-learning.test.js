import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import JhaIncidentLearning from '../src/components/JhaIncidentLearning.vue'

const search = (incidents = []) => ({ work_step_sequence: 2, status: incidents.length ? 'matches' : 'no_matches', signals: { mechanisms: ['Pinch Points'] }, incidents })
const incident = {
  name: 'source-1', source_system: 'INX InControl', source_reference: 'TEST-101',
  incident_date: '2021-02-03', record_url: '/app/jha-incident-learning/source-1',
  title: 'Test fixture', incident_summary: 'Finger caught between flanges',
  investigation_findings: 'Hands used for alignment', actions_available: true,
  actions: [{ action_description: 'Provide an alignment tool', action_status: 'Open' }],
  recommended_controls: 'Review alignment tooling',
}

describe('Voice JHA incident evidence', () => {
  it('shows source facts and action status without implying acceptance', () => {
    const wrapper = mount(JhaIncidentLearning, { props: { searches: [search([incident])] } })
    expect(wrapper.text()).toContain('INX InControl · TEST-101')
    expect(wrapper.text()).toContain('2021-02-03')
    expect(wrapper.text()).toContain('Provide an alignment tool')
    expect(wrapper.text()).toContain('Open')
    expect(wrapper.text()).toContain('Controls recorded in the investigation')
    expect(wrapper.find('a').attributes('href')).toBe(incident.record_url)
    expect(wrapper.findAll('button')).toHaveLength(0)
  })
  it('reports missing actions and changed records', () => {
    const wrapper = mount(JhaIncidentLearning, { props: { searches: [search([{ ...incident, actions: [], actions_available: false, source_changed: true, evidence_excerpt: true }])] } })
    expect(wrapper.text()).toContain('Investigation actions were not recorded')
    expect(wrapper.text()).toContain('has changed since this lookup')
    expect(wrapper.text()).toContain('Evidence excerpts are shown')
  })
  it('distinguishes unavailable evidence from an empty search', () => {
    const wrapper = mount(JhaIncidentLearning, { props: { searches: [{ ...search(), status: 'unavailable' }] } })
    expect(wrapper.text()).toContain('Incident evidence is unavailable')
    expect(wrapper.text()).not.toContain('No relevant incident was found')
  })
  it('shows search limits and potential exposures', () => {
    const wrapper = mount(JhaIncidentLearning, { props: { searches: [{ ...search(), preview: true, search_limited: true }] } })
    expect(wrapper.text()).toContain('Potential exposure')
    expect(wrapper.text()).toContain('limited set of matching records')
    expect(wrapper.text()).toContain('Continue assessing the exposure')
  })
  it('renders imported text literally', () => {
    const wrapper = mount(JhaIncidentLearning, { props: { searches: [search([{ ...incident, incident_summary: '<img src=x onerror=alert(1)>' }])] } })
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.text()).toContain('<img src=x onerror=alert(1)>')
  })
  it('keeps an immediate response and closed incident separate from investigation actions', () => {
    const wrapper = mount(JhaIncidentLearning, { props: { searches: [search([{
      ...incident, actions: [], actions_available: false, investigation_findings: '',
      recommended_controls: '', immediate_actions: 'Stopped the task and secured the area', source_event_status: 'Closed',
    }])] } })
    expect(wrapper.text()).toContain('Immediate response recorded')
    expect(wrapper.text()).toContain('Stopped the task and secured the area')
    expect(wrapper.text()).toContain('Source incident status: Closed')
    expect(wrapper.text()).toContain('does not verify action completion or control effectiveness')
    expect(wrapper.text()).toContain('Investigation actions were not recorded in this dataset')
    expect(wrapper.text()).not.toContain('Controls recorded in the investigation')
  })
})
