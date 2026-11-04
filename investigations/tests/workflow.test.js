import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { categories, clearReferences, draft } from '../src/model'
import { eventType, investigationGraph, whyParents } from '../src/workflow'
import WorkflowCanvas from '../src/components/WorkflowCanvas.vue'

function record() {
  return {
    ...draft('lead'),
    description: 'Actual incident',
    incident_datetime: '2026-11-04 10:00:00',
    timeline: [
      { entry_id: 'T-before', event_datetime: '2026-11-04 09:00:00', description: 'Before' },
      { entry_id: 'T-after', event_datetime: '2026-11-04 10:15:00', description: 'After' },
    ],
  }
}
describe('investigation workflow', () => {
  it('keeps legacy events and distinguishes chronology from explicit links', () => {
    const doc = record(),
      graph = investigationGraph(doc, 'timeline')
    expect(graph.nodes.map((node) => node.kind)).toEqual([
      'Actual event',
      'Event information',
      'Post event',
    ])
    expect(graph.edges.map((edge) => [edge.from, edge.to, edge.suggested])).toEqual([
      ['T-before', 'incident', true],
      ['incident', 'T-after', true],
    ])
    doc.timeline[0].next_events = 'T-after\nincident'
    expect(investigationGraph(doc, 'timeline').edges).toHaveLength(2)
    expect(investigationGraph(doc, 'timeline').edges.every((edge) => !edge.suggested)).toBe(
      true,
    )
    doc.incident_time_precision = 'Date only'
    expect(eventType(doc.timeline[1], doc)).toBe('Event information')
  })
  it('draws multiple why branches and prevents choosing a descendant as parent', () => {
    const doc = record()
    doc.five_whys = [
      { entry_id: 'W-a', description: 'First direct cause', finding_status: 'Supported' },
      {
        entry_id: 'W-b',
        parent_id: 'W-a',
        description: 'System cause',
        is_root_cause: 1,
        finding_status: 'Supported',
      },
      { entry_id: 'W-c', description: 'Alternative hypothesis', finding_status: 'Hypothesis' },
    ]
    const graph = investigationGraph(doc, 'whys')
    expect(graph.edges.map((edge) => [edge.from, edge.to])).toEqual([
      ['incident', 'W-a'],
      ['W-a', 'W-b'],
      ['incident', 'W-c'],
    ])
    expect(graph.nodes.find((node) => node.id === 'W-b').kind).toBe('Root cause')
    expect(whyParents(doc.five_whys, 'W-a').map((row) => row.entry_id)).toEqual(['W-c'])
  })
  it('renders explicit ICAM links and preserves unconfirmed factor status', () => {
    const doc = record()
    doc.icam_factors = [
      {
        entry_id: 'F-a',
        category: categories[0],
        finding_status: 'Supported',
        description: 'Missing barrier',
      },
      {
        entry_id: 'F-b',
        category: categories[3],
        finding_status: 'Hypothesis',
        contributes_to: 'F-a',
      },
    ]
    const graph = investigationGraph(doc, 'icam')
    expect(graph.edges).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ from: 'F-a', to: 'incident', suggested: false }),
        expect.objectContaining({ from: 'F-b', to: 'F-a', suggested: true }),
      ]),
    )
  })
  it('removes event links when a connected event is deleted', () => {
    const doc = record()
    doc.timeline[0].next_events = 'T-after\nincident'
    clearReferences(doc, 'T-after')
    expect(doc.timeline[0].next_events).toBe('incident')
  })
  it('selects bubbles, saves a drag and leaves locked diagrams read only', async () => {
    const doc = record(),
      graph = investigationGraph(doc, 'timeline')
    const wrapper = mount(WorkflowCanvas, {
      props: { graph, label: 'Timeline', mode: 'timeline', editable: true },
    })
    const node = wrapper.findAll('.workflow-node')[1]
    await node.trigger('click')
    expect(wrapper.emitted('select')[0]).toEqual(['T-before'])
    const before = graph.nodes[1]
    await node.trigger('pointerdown', { button: 0, pointerId: 1, clientX: 100, clientY: 100 })
    await wrapper
      .get('.workflow-viewport')
      .trigger('pointermove', { pointerId: 1, clientX: 140, clientY: 125 })
    await wrapper.get('.workflow-viewport').trigger('pointerup', { pointerId: 1 })
    expect(wrapper.emitted('move')[0]).toEqual([
      { id: 'T-before', x: before.x + 40, y: before.y + 25 },
    ])
    await wrapper.setProps({ editable: false })
    expect(wrapper.text()).not.toContain('Auto arrange')
    await node.trigger('pointerdown', { button: 0, pointerId: 2, clientX: 100, clientY: 100 })
    await wrapper
      .get('.workflow-viewport')
      .trigger('pointermove', { pointerId: 2, clientX: 200, clientY: 100 })
    await wrapper.get('.workflow-viewport').trigger('pointerup', { pointerId: 2 })
    expect(wrapper.emitted('move')).toHaveLength(1)
    wrapper.unmount()
  })
})
