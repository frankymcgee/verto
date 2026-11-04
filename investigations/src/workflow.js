import { categories, refs } from './model'

export const eventTypes = [
  'Event information',
  'Contributing factor',
  'Direct factor',
  'Actual event',
  'Post event',
]
export const nodeWidth = 248
export const nodeHeight = 164

export function eventType(row, doc) {
  if (eventTypes.includes(row.event_type)) return row.event_type
  if (doc.incident_time_precision === 'Date only') return eventTypes[0]
  const time = String(row.event_datetime || '').replace('T', ' ')
  const incident = String(doc.incident_datetime || '').replace('T', ' ')
  if (!time || !incident) return eventTypes[0]
  return time.slice(0, 16) > incident.slice(0, 16)
    ? 'Post event'
    : time.slice(0, 16) === incident.slice(0, 16)
      ? 'Actual event'
      : eventTypes[0]
}

// The graph is a view of the investigation rows. Moving or linking a bubble
// edits those rows, so there is no second copy of the findings to get out of sync.
export function investigationGraph(doc, mode) {
  const nodes = [],
    edges = [],
    counts = new Map()
  const add = (row, lane, kind, title, table) => {
    const index = counts.get(lane) || 0
    counts.set(lane, index + 1)
    nodes.push({
      id: row.entry_id,
      row,
      table,
      lane,
      kind,
      title,
      description: row.description || '',
      status: row.finding_status || '',
      evidence: refs(row.evidence_refs),
      x: Number(row.graph_x) > 0 ? Number(row.graph_x) : 28 + lane * 310,
      y: Number(row.graph_y) > 0 ? Number(row.graph_y) : 64 + index * 204,
    })
  }
  const incident = (lane) =>
    add(
      {
        entry_id: 'incident',
        description: doc.description || doc.title || 'Describe the actual event',
        event_datetime: doc.incident_datetime,
      },
      lane,
      'Actual event',
      'Actual event',
      '',
    )
  let lanes
  if (mode === 'timeline') {
    lanes = eventTypes
    incident(3)
    for (const row of doc.timeline || []) {
      const type = eventType(row, doc)
      add(row, eventTypes.indexOf(type), type, type, 'timeline')
      for (const target of refs(row.next_events))
        edges.push({ from: row.entry_id, to: target, label: 'Linked event' })
      for (const source of refs(row.previous_events))
        edges.push({ from: source, to: row.entry_id, label: 'Linked event' })
    }
    // Chronology is distinct from a causal relationship. Explicit links replace
    // the suggested sequence for that source node.
    const sequence = nodes
      .filter(
        (node) =>
          node.row.event_datetime &&
          !['Contributing factor', 'Direct factor'].includes(node.kind) &&
          !(node.id === 'incident' && doc.incident_time_precision === 'Date only'),
      )
      .sort((a, b) =>
        String(a.row.event_datetime)
          .replace('T', ' ')
          .localeCompare(String(b.row.event_datetime).replace('T', ' ')),
      )
    sequence.slice(0, -1).forEach((node, index) => {
      if (
        !(doc.timeline || []).some(
          (row) => refs(row.next_events).length || refs(row.previous_events).length,
        )
      )
        edges.push({
          from: node.id,
          to: sequence[index + 1].id,
          label: 'Time sequence',
          suggested: true,
        })
    })
  } else if (mode === 'whys') {
    lanes = ['Actual event', 'Direct factors', 'Contributing factors']
    incident(0)
    const rows = doc.five_whys || [],
      byId = new Map(rows.map((row) => [row.entry_id, row]))
    for (const row of rows) {
      let depth = 1,
        parent = byId.get(row.parent_id),
        seen = new Set([row.entry_id])
      while (parent && !seen.has(parent.entry_id)) {
        seen.add(parent.entry_id)
        depth++
        parent = byId.get(parent.parent_id)
      }
      while (lanes.length <= depth) lanes.push(`Why ${lanes.length}`)
      const kind = row.is_root_cause
        ? 'Root cause'
        : depth === 1
          ? 'Direct factor'
          : 'Contributing factor'
      add(
        row,
        depth,
        kind,
        `Why ${depth}${row.is_root_cause ? ' · Root cause' : ''}`,
        'five_whys',
      )
      edges.push({
        from: row.parent_id || 'incident',
        to: row.entry_id,
        label: 'Why?',
        suggested: row.finding_status !== 'Supported',
      })
    }
  } else {
    lanes = [...categories].reverse().concat('Actual event')
    incident(4)
    for (const row of doc.icam_factors || []) {
      const lane = lanes.indexOf(row.category)
      add(
        row,
        Math.max(0, lane),
        row.category === categories[0] ? 'Direct factor' : 'Contributing factor',
        row.factor_type || row.category,
        'icam_factors',
      )
      const targets = refs(row.contributes_to)
      for (const target of targets)
        edges.push({
          from: row.entry_id,
          to: target,
          label: 'Contributes to',
          suggested: row.finding_status !== 'Supported',
        })
      if (!targets.length && row.category === categories[0])
        edges.push({
          from: row.entry_id,
          to: 'incident',
          label: 'Defence',
          suggested: row.finding_status !== 'Supported',
        })
    }
  }
  const ids = new Set(nodes.map((node) => node.id))
  const seen = new Set()
  return {
    nodes,
    edges: edges.filter((edge) => {
      const key = `${edge.from}:${edge.to}`
      if (!ids.has(edge.from) || !ids.has(edge.to) || seen.has(key)) return false
      seen.add(key)
      return true
    }),
    lanes,
  }
}

export function whyParents(rows, entryId) {
  const excluded = new Set([entryId])
  let changed = true
  while (changed) {
    changed = false
    for (const row of rows)
      if (excluded.has(row.parent_id) && !excluded.has(row.entry_id)) {
        excluded.add(row.entry_id)
        changed = true
      }
  }
  return rows.filter((row) => !excluded.has(row.entry_id))
}
