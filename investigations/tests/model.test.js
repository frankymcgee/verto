import { describe, expect, it } from 'vitest'
import { categories, clearReferences, draft, removeWhy, supportedFindings, whyTree } from '../src/model'

describe('investigation analysis', () => {
  it('preserves causal branches when an intermediate why is removed', () => {
    const rows = [{ entry_id: 'W-root', parent_id: '' }, { entry_id: 'W-middle', parent_id: 'W-root' }, { entry_id: 'W-leaf', parent_id: 'W-middle' }, { entry_id: 'W-branch', parent_id: 'W-root' }]
    const remaining = removeWhy(rows, 'W-middle')
    expect(remaining.find(row => row.entry_id === 'W-leaf').parent_id).toBe('W-root')
    expect(whyTree(remaining).map(({ row, depth }) => [row.entry_id, depth])).toEqual([['W-root', 0], ['W-leaf', 1], ['W-branch', 1]])
  })
  it('removes dangling evidence and finding references across the workspace', () => {
    const doc = { timeline: [{ evidence_refs: 'E-old\nE-retained' }], five_whys: [{ evidence_refs: 'E-old' }], icam_factors: [{ evidence_refs: 'E-old', contributes_to: 'F-old' }], actions: [{ finding_refs: 'F-old' }] }
    clearReferences(doc, 'E-old'); clearReferences(doc, 'F-old')
    expect(doc.timeline[0].evidence_refs).toBe('E-retained')
    expect(doc.five_whys[0].evidence_refs).toBe('')
    expect(doc.icam_factors[0].contributes_to).toBe('')
    expect(doc.actions[0].finding_refs).toBe('')
  })
  it('offers supported root causes and active-method factors for action mapping', () => {
    const doc = { method: '5 Whys + ICAM', five_whys: [{ entry_id: 'W-root', finding_status: 'Supported', is_root_cause: 1 }, { entry_id: 'W-other', finding_status: 'Supported' }, { entry_id: 'W-hypothesis', finding_status: 'Hypothesis', is_root_cause: 1 }], icam_factors: [{ entry_id: 'F-factor', finding_status: 'Supported' }] }
    expect(supportedFindings(doc).map(row => row.entry_id)).toEqual(['W-root', 'F-factor'])
    doc.method = 'ICAM'
    expect(supportedFindings(doc).map(row => row.entry_id)).toEqual(['F-factor'])
  })
  it('starts a confidential draft without inventing the event time or conclusions', () => {
    const doc = draft('lead@example.test')
    expect(doc.incident_datetime).toBe('')
    expect(doc.lead_investigator).toBe('lead@example.test')
    expect(doc.five_whys).toEqual([])
    expect(doc.category_reviews.map(row => row.category)).toEqual(categories)
  })
})
