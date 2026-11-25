import { evaluateMandatoryDependsOn, evaluateReadOnlyDependsOn, getVisibleFormFields } from './dependencies'

export type ChecklistField = {
  fieldname: string
  fieldtype: string
  label?: string
  required?: boolean
  read_only?: boolean
  mandatory_depends_on?: string
  read_only_depends_on?: string
  depends_on?: string
  child_fields?: ChecklistField[]
}

export type SubmissionIssue = {
  id: string
  fieldname: string
  label: string
  location: string
  message: string
  tabId: string
  rowIndex?: number
  childFieldname?: string
}

export class IncompleteSubmissionError extends Error {
  constructor() {
    super('Other form items need attention. Keep this row in the form, then complete the submission checklist.')
  }
}

const layoutTypes = new Set(['Section Break', 'Column Break', 'Tab Break', 'HTML', 'Button', 'Image'])
const issueId = (fieldname: string, rowIndex?: number, childFieldname?: string) => JSON.stringify([fieldname, rowIndex ?? null, childFieldname ?? null])
const editable = (field: ChecklistField, values: Record<string, any>) => !field.read_only && !evaluateReadOnlyDependsOn(field.read_only_depends_on, values)

export function isMissingRequiredValue(field: ChecklistField, value: any) {
  if (field.fieldtype === 'Table') return !Array.isArray(value) || value.length === 0
  if (field.fieldtype === 'Check') return ![true, 1, '1'].includes(value)
  if (field.fieldtype === 'Rating') return !(Number(value) > 0)
  if (value === undefined || value === null) return true
  if (field.fieldtype === 'Text Editor') {
    // Parse in an inert template: empty editor markup and non-breaking spaces
    // are not an answer. An embedded image can be meaningful content.
    const template = document.createElement('template')
    template.innerHTML = String(value)
    return !template.content.textContent?.replace(/\u200b/g, '').trim() && !template.content.querySelector('img[src], video[src], audio[src]')
  }
  return typeof value === 'string' ? !value.trim() : Array.isArray(value) && !value.length
}

export function collectSubmissionIssues(fields: ChecklistField[], values: Record<string, any>): SubmissionIssue[] {
  const visible = new Set(getVisibleFormFields(fields, values))
  const issues: SubmissionIssue[] = []
  let tabId = 'main'
  let tabLabel = 'Details'
  let section = ''
  for (const field of fields) {
    if (field.fieldtype === 'Tab Break') {
      tabId = field.fieldname
      tabLabel = field.label || 'Details'
      section = ''
      continue
    }
    if (field.fieldtype === 'Section Break') section = visible.has(field) ? field.label || '' : ''
    if (layoutTypes.has(field.fieldtype) || !visible.has(field) || !editable(field, values)) continue
    const location = [tabLabel, section].filter(Boolean).join(' · ')
    if ((field.required || evaluateMandatoryDependsOn(field.mandatory_depends_on, values)) && isMissingRequiredValue(field, values[field.fieldname])) {
      issues.push({ id: issueId(field.fieldname), fieldname: field.fieldname, label: field.label || field.fieldname, tabId, location,
        message: field.fieldtype === 'Table' ? 'Add at least one row.' : field.fieldtype === 'Signature' ? 'Add your signature.' : field.fieldtype === 'Check' ? 'Tick this checkbox.' : 'Complete this field.' })
    }
    if (field.fieldtype !== 'Table' || !Array.isArray(values[field.fieldname])) continue
    values[field.fieldname].forEach((row: Record<string, any>, rowIndex: number) => {
      for (const child of collectSubmissionIssues(field.child_fields || [], row || {})) {
        issues.push({ ...child, id: issueId(field.fieldname, rowIndex, child.fieldname), fieldname: field.fieldname, childFieldname: child.fieldname, rowIndex, tabId,
          location: [location, field.label || field.fieldname, `Row ${rowIndex + 1}`, child.location === 'Details' ? '' : child.location.replace(/^Details · /, '')].filter(Boolean).join(' · ') })
      }
    })
  }
  return issues
}

export function findSubmissionField(root: HTMLElement | null, fieldname: string) {
  return Array.from(root?.querySelectorAll<HTMLElement>('[data-form-field]') || []).find(element => element.dataset.formField === fieldname)
}

export function focusSubmissionField(element?: HTMLElement) {
  if (!element) return
  element.scrollIntoView({ block: 'center', behavior: 'instant' })
  // A signature needs its canvas in view, rather than focus on the Clear button.
  const control = element.querySelector<HTMLElement>('canvas') ? element : element.querySelector<HTMLElement>('input:not([type="hidden"]):not(:disabled), textarea:not(:disabled), [contenteditable="true"], [role="radio"], button:not(:disabled)') || element
  control.focus({ preventScroll: true })
}

export function collectControlIssues(root: HTMLElement | null, fields: ChecklistField[], values: Record<string, any>): SubmissionIssue[] {
  const issues: SubmissionIssue[] = []
  const visible = new Set(getVisibleFormFields(fields, values))
  let tabId = 'main'
  let tabLabel = 'Details'
  for (const field of fields) {
    if (field.fieldtype === 'Tab Break') { tabId = field.fieldname; tabLabel = field.label || 'Details' }
    if (!visible.has(field) || !editable(field, values) || layoutTypes.has(field.fieldtype)) continue
    const element = findSubmissionField(root, field.fieldname)
    const invalid = Array.from(element?.querySelectorAll<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>('input, select, textarea') || [])
      .find(control => control.willValidate && !control.validity.valid)
    if (invalid) issues.push({ id: issueId(field.fieldname), fieldname: field.fieldname, label: field.label || field.fieldname, location: tabLabel, tabId,
      message: invalid.validationMessage || 'Check this value.' })
  }
  return issues
}
