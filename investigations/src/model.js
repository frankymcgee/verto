export const categories = [
  'Absent or Failed Defences',
  'Individual or Team Actions',
  'Task or Environmental Conditions',
  'Organisational Factors',
]
export const methods = ['5 Whys', 'ICAM', '5 Whys + ICAM']
export const controls = [
  'Elimination',
  'Substitution',
  'Isolation',
  'Engineering',
  'Administrative',
  'PPE',
]
export const refs = (value) =>
  String(value || '')
    .split(/[,\n]/)
    .map((part) => part.trim())
    .filter(Boolean)
export const id = (prefix) => `${prefix}-${crypto.randomUUID().replaceAll('-', '').slice(0, 12)}`
export function localDatetime(value = new Date()) {
  if (typeof value === 'string') return value.replace(' ', 'T').slice(0, 16)
  const adjusted = new Date(value.getTime() - value.getTimezoneOffset() * 60000)
  return adjusted.toISOString().slice(0, 16)
}
export function draft(user) {
  return {
    title: '',
    method: '5 Whys',
    status: 'Draft',
    incident_datetime: '',
    incident_time_precision: 'Exact',
    lead_investigator: user,
    regulatory_review: 'Not assessed',
    incident_type: 'Other',
    team: [],
    evidence: [],
    timeline: [],
    five_whys: [],
    icam_factors: [],
    actions: [],
    history: [],
    category_reviews: categories.map((category) => ({ category, no_finding_reason: '' })),
    capabilities: { can_edit: true },
    readiness: [],
    closure_readiness: [],
  }
}
export function whyTree(rows) {
  const result = [],
    seen = new Set()
  function append(parent, depth) {
    for (const row of rows.filter((row) => (row.parent_id || '') === parent)) {
      if (seen.has(row.entry_id)) continue
      seen.add(row.entry_id)
      result.push({ row, depth })
      append(row.entry_id, depth + 1)
    }
  }
  append('', 0)
  for (const row of rows) if (!seen.has(row.entry_id)) result.push({ row, depth: 0 })
  return result
}
export function removeWhy(rows, entryId) {
  const row = rows.find((row) => row.entry_id === entryId)
  // Removing a node retains its descendants as branches of its preceding cause.
  return rows
    .filter((row) => row.entry_id !== entryId)
    .map((other) =>
      other.parent_id === entryId ? { ...other, parent_id: row?.parent_id || '' } : other,
    )
}
export function clearReferences(doc, entryId) {
  for (const table of ['timeline', 'five_whys', 'icam_factors', 'actions']) {
    for (const row of doc[table] || [])
      for (const field of ['evidence_refs', 'finding_refs', 'contributes_to']) {
        if (field in row)
          row[field] = refs(row[field])
            .filter((value) => value !== entryId)
            .join('\n')
      }
  }
}
export function supportedFindings(doc) {
  const whys =
    doc.method !== 'ICAM'
      ? doc.five_whys.filter((row) => row.finding_status === 'Supported' && row.is_root_cause)
      : []
  const factors =
    doc.method !== '5 Whys'
      ? doc.icam_factors.filter((row) => row.finding_status === 'Supported')
      : []
  return [...whys, ...factors].map((row) => ({
    entry_id: row.entry_id,
    title: row.description || row.entry_id,
  }))
}
