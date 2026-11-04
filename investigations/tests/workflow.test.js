import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { categories, clearReferences, draft } from '../src/model'
import {
  eventTimeKey,
  eventType,
  investigationGraph,
  orderedTimeline,
  whyParents,
} from '../src/workflow'
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
      'Event information',
      'Actual event',
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
  it('lays every event out horizontally by time, including different types and saved positions', () => {
    const doc = record()
    doc.timeline = [
      {
        entry_id: 'T-late',
        event_type: 'Direct factor',
        event_datetime: '2026-11-04 11:00:00',
        graph_x: 1,
        graph_y: 500,
      },
      {
        entry_id: 'T-equal-a',
        event_type: 'Event information',
        event_datetime: '2026-11-04T09:00',
      },
      { entry_id: 'T-undated', event_type: 'Post event', event_datetime: '' },
      {
        entry_id: 'T-first',
        event_type: 'Contributing factor',
        event_datetime: '2026-11-03 14:00:00',
      },
      {
        entry_id: 'T-equal-b',
        event_type: 'Actual event',
        event_datetime: '2026-11-04 09:00:00.000000',
      },
    ]
    const original = doc.timeline.map((row) => row.entry_id)
    const graph = investigationGraph(doc, 'timeline')
    expect(graph.nodes.map((node) => node.id)).toEqual([
      'T-first',
      'T-equal-a',
      'T-equal-b',
      'incident',
      'T-late',
      'T-undated',
    ])
    expect(new Set(graph.nodes.map((node) => node.y)).size).toBe(1)
    graph.nodes
      .slice(1)
      .forEach((node, index) => expect(node.x - graph.nodes[index].x).toBe(328))
    expect(graph.nodes.find((node) => node.id === 'T-undated').timeLabel).toBe('Time not set')
    expect(doc.timeline.map((row) => row.entry_id)).toEqual(original)
    expect(doc.timeline[0].graph_y).toBe(500)
    doc.timeline[0].event_datetime = '2026-11-03 08:00'
    expect(investigationGraph(doc, 'timeline').nodes[0].id).toBe('T-late')
    expect(orderedTimeline(doc.timeline)[0].entry_id).toBe('T-late')
  })
  it('normalises timestamp formats and seconds without applying the browser timezone', () => {
    expect(eventTimeKey('2026-11-04T09:30')).toBe(eventTimeKey('2026-11-04 09:30:00.000000'))
    expect(eventTimeKey('2026-11-04 09:30:00.1')).toBe('2026-11-04 09:30:00.100000')
    expect(eventTimeKey('2026-02-30 09:30')).toBe('')
    const doc = record()
    doc.incident_time_precision = 'Date only'
    const incident = investigationGraph(doc, 'timeline').nodes.find(
      (node) => node.id === 'incident',
    )
    expect(incident.timeLabel).toContain('Date only')
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
    const doc = record()
    doc.five_whys = [
      { entry_id: 'W-first', description: 'First cause', finding_status: 'Hypothesis' },
    ]
    const graph = investigationGraph(doc, 'whys')
    const wrapper = mount(WorkflowCanvas, {
      props: { graph, label: '5 Whys', mode: 'whys', editable: true },
    })
    const node = wrapper.findAll('.workflow-node')[1]
    await node.trigger('click')
    expect(wrapper.emitted('select')[0]).toEqual(['W-first'])
    const before = graph.nodes[1]
    const capture = vi.spyOn(node.element, 'setPointerCapture')
    const viewportCapture = vi.spyOn(
      wrapper.get('.workflow-viewport').element,
      'setPointerCapture',
    )
    await node.trigger('pointerdown', { button: 0, pointerId: 1, clientX: 100, clientY: 100 })
    expect(capture).toHaveBeenCalledWith(1)
    expect(viewportCapture).not.toHaveBeenCalled()
    await wrapper
      .get('.workflow-viewport')
      .trigger('pointermove', { pointerId: 1, clientX: 140, clientY: 125 })
    await wrapper.get('.workflow-viewport').trigger('pointerup', { pointerId: 1 })
    expect(wrapper.emitted('move')[0]).toEqual([
      { id: 'W-first', x: before.x + 40, y: before.y + 25 },
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
  it('keeps timeline bubbles selectable while their positions remain controlled by time', async () => {
    const graph = investigationGraph(record(), 'timeline')
    const wrapper = mount(WorkflowCanvas, {
      props: { graph, label: 'Timeline', mode: 'timeline', editable: true },
    })
    expect(wrapper.text()).not.toContain('Auto arrange')
    const node = wrapper.get('[data-node-id="T-after"]')
    const capture = vi.spyOn(node.element, 'setPointerCapture')
    await node.trigger('pointerdown', { button: 0, pointerId: 1, clientX: 100, clientY: 100 })
    await node.trigger('pointerup', { pointerId: 1 })
    await node.trigger('click')
    expect(wrapper.emitted('select').at(-1)).toEqual(['T-after'])
    expect(capture).not.toHaveBeenCalled()
    expect(wrapper.emitted('move')).toBeUndefined()
    await wrapper
      .get('.workflow-sheet')
      .trigger('pointerdown', { button: 0, pointerId: 2, clientX: 10, clientY: 240 })
    await wrapper.get('.workflow-sheet').trigger('pointerup', { pointerId: 2 })
    await node.trigger('click')
    expect(wrapper.emitted('select').at(-1)).toEqual(['T-after'])
    expect(wrapper.findAll('.workflow-node-time')).toHaveLength(graph.nodes.length)
    wrapper.unmount()
  })
  it('reveals the selected event after a time edit moves it across the timeline', async () => {
    const doc = record()
    const wrapper = mount(WorkflowCanvas, {
      props: {
        graph: investigationGraph(doc, 'timeline'),
        label: 'Timeline',
        mode: 'timeline',
        editable: true,
        selectedId: 'T-after',
      },
    })
    const viewport = wrapper.get('.workflow-viewport').element
    Object.defineProperty(viewport, 'clientWidth', { value: 400 })
    await flushPromises()
    viewport.scrollLeft = 500
    doc.timeline[1].event_datetime = '2026-11-03 06:00:00'
    await wrapper.setProps({ graph: investigationGraph(doc, 'timeline') })
    await flushPromises()
    expect(viewport.scrollLeft).toBe(0)
    expect(wrapper.get('[data-node-id="T-after"]').attributes('aria-pressed')).toBe('true')
    wrapper.unmount()
  })
})
