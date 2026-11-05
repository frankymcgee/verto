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

// Frappe datetimes are site-local values. Compare their components without
// converting them through the browser's timezone or depending on T/space style.
export function eventTimeKey(value) {
  const parts = String(value || '')
    .trim()
    .match(/^(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,6}))?)?)?$/)
  if (!parts) return ''
  const [, date, hours = '00', minutes = '00', seconds = '00', fraction = ''] = parts
  const base = `${date}T${hours}:${minutes}:${seconds}`
  const parsed = new Date(`${base}Z`)
  if (!Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0, 19) !== base)
    return ''
  return `${date} ${hours}:${minutes}:${seconds}.${fraction.padEnd(6, '0')}`
}

export function compareEvents(a, b) {
  const first = eventTimeKey(a.event_datetime),
    second = eventTimeKey(b.event_datetime)
  if (!first || !second) return first ? -1 : second ? 1 : 0
  return first.localeCompare(second)
}

export const orderedTimeline = (rows = []) => [...rows].sort(compareEvents)

export function eventTimeLabel(value, dateOnly = false) {
  const key = eventTimeKey(value)
  if (!key) return 'Time not set'
  const day = new Intl.DateTimeFormat('en-AU', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(`${key.slice(0, 10)}T00:00:00Z`))
  const fraction = key.slice(20).replace(/0+$/, '')
  const clock =
    key.slice(17, 19) !== '00' || fraction
      ? key.slice(11, 19) + (fraction ? `.${fraction}` : '')
      : key.slice(11, 16)
  return `${day} · ${dateOnly ? 'Date only' : clock}`
}

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

function whyLayout(rows) {
  const byId = new Map(rows.map((row) => [row.entry_id, row])),
    children = new Map(),
    visited = new Set(),
    positions = new Map()
  for (const row of rows) {
    if (!children.has(row.parent_id)) children.set(row.parent_id, [])
    children.get(row.parent_id).push(row)
  }
  const visit = (row) => {
    if (visited.has(row.entry_id)) return null
    visited.add(row.entry_id)
    const branches = (children.get(row.entry_id) || []).map(visit).filter(Boolean)
    return { row, branches, span: Math.max(1, branches.reduce((n, branch) => n + branch.span, 0)) }
  }
  // Keep entry order between siblings, but reserve a contiguous span for each
  // entire subtree. IDs and interleaved rows never decide a descendant's column.
  const roots = rows.filter((row) => !byId.has(row.parent_id)).map(visit).filter(Boolean)
  // Invalid, unsaved cycles still need selectable bubbles; saving validates them.
  for (const row of rows) if (!visited.has(row.entry_id)) roots.push(visit(row))
  const place = (branch, left, depth) => {
    positions.set(branch.row.entry_id, { column: left + (branch.span - 1) / 2, depth })
    for (const child of branch.branches) {
      place(child, left, depth + 1)
      left += child.span
    }
  }
  let columns = 0
  for (const root of roots) {
    place(root, columns, 1)
    columns += root.span
  }
  return { positions, columns: Math.max(1, columns) }
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
    const node = {
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
    }
    nodes.push(node)
    return node
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
    incident(3)
    for (const row of doc.timeline || []) {
      const type = eventType(row, doc)
      add(row, eventTypes.indexOf(type), type, type, 'timeline')
      for (const target of refs(row.next_events))
        edges.push({ from: row.entry_id, to: target, label: 'Linked event' })
      for (const source of refs(row.previous_events))
        edges.push({ from: source, to: row.entry_id, label: 'Linked event' })
    }
    // Timeline position always follows chronology, including when old saved
    // coordinates or explicit causal links exist. Analysis maps remain movable.
    nodes.sort((a, b) => compareEvents(a.row, b.row))
    nodes.forEach((node, index) => {
      node.lane = index
      node.x = 20 + index * (nodeWidth + 80)
      node.y = 32
      node.dateOnly = node.id === 'incident' && doc.incident_time_precision === 'Date only'
      node.timeLabel = eventTimeLabel(node.row.event_datetime, node.dateOnly)
    })
    lanes = nodes.map((node) => node.timeLabel)
    // Dashed chronological connectors do not assert a causal relationship.
    // Explicit links replace suggestions, but never change the date order.
    const sequence = nodes.filter(
      (node) => eventTimeKey(node.row.event_datetime) && !node.dateOnly,
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
    const rows = doc.five_whys || [],
      layout = whyLayout(rows),
      start = incident(0)
    lanes = []
    start.column = (layout.columns - 1) / 2
    start.depth = 0
    start.x = 28 + start.column * (nodeWidth + 80)
    start.y = 48
    for (const row of rows) {
      const { column, depth } = layout.positions.get(row.entry_id)
      const kind = row.is_root_cause
        ? 'Root cause'
        : depth === 1
          ? 'Direct factor'
          : 'Contributing factor'
      const node = add(
        row,
        depth,
        kind,
        `Why ${depth}${row.is_root_cause ? ' · Root cause' : ''}`,
        'five_whys',
      )
      node.column = column
      node.depth = depth
      node.x = Number(row.graph_x) > 0 ? Number(row.graph_x) : 28 + column * (nodeWidth + 80)
      node.y = Number(row.graph_y) > 0 ? Number(row.graph_y) : 48 + depth * (nodeHeight + 72)
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
