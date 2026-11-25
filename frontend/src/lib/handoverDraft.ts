import { escapeText, escapeAttribute } from 'entities'
import { toDeskUrl } from './deskRoute'

export type HandoverSource = { id: string; doctype: string; name: string; recorded_at: string; time_basis: string; url: string }
export type HandoverDraft = {
  fields: Record<string, string>
  sources: HandoverSource[]
  warnings: string[]
  scope: { project: string; period_start: string; period_end: string; coverage: string; timezone: string }
  model: string
}
export const handoverNarrativeFields = new Set([
  'incident_information', 'shift_focus', 'raised_at_meetings', 'shift_findings',
  'upcoming_shift_focus', 'ccv_snapshot', 'communication_stakeholders', 'actions',
])

export function defaultHandoverPeriod(value: string) {
  const end = String(value || '').replace(' ', 'T').slice(0, 19)
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(end)) return { start: '', end: '' }
  // Treat the wall-clock value as UTC only for arithmetic; send it back without
  // an offset. Frappe interprets both endpoints in the site's timezone.
  const start = new Date(end + (end.length === 16 ? ':00Z' : 'Z'))
  if (Number.isNaN(start.getTime())) return { start: '', end: '' }
  start.setUTCHours(start.getUTCHours() - 12)
  return { start: start.toISOString().slice(0, 19), end }
}

export function handoverDraftHtml(text: string, sources: HandoverSource[]) {
  const escaped = escapeText(text).replace(/\n/g, '<br>')
  const linked = escaped.replace(/\[S\d+\]/g, token => {
    const source = sources.find(source => `[${source.id}]` === token)
    const url = source ? toDeskUrl(source.url) : ''
    if (!/^\/desk\/[a-z0-9-]+\/[^?#]*$/.test(url)) return token
    return `<a href="${escapeAttribute(url)}" target="_blank" rel="noopener noreferrer">${token}</a>`
  })
  return `<p>${linked}</p>`
}
