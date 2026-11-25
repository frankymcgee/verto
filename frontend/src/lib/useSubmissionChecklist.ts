import { computed, nextTick, onBeforeUnmount, ref, watch, type Ref } from 'vue'
import { collectControlIssues, collectSubmissionIssues, findSubmissionField, focusSubmissionField, type ChecklistField, type SubmissionIssue } from './submissionChecklist'

export function useSubmissionChecklist(fields: Ref<ChecklistField[]>, values: Ref<Record<string, any>>, activeTab?: Ref<string>) {
  const root = ref<HTMLElement | null>(null)
  const panel = ref<{ reveal: () => Promise<void> } | null>(null)
  const controlIssues = ref<SubmissionIssue[]>([])
  const tables = new Map<string, { revealIssue: (issue: SubmissionIssue) => Promise<void> }>()
  let checked = false
  let active = true
  onBeforeUnmount(() => { active = false })
  const issues = computed(() => {
    const required = collectSubmissionIssues(fields.value, values.value)
    const ids = new Set(required.map(issue => issue.id))
    return [...required, ...controlIssues.value.filter(issue => !ids.has(issue.id))]
  })
  function refreshControls() { controlIssues.value = collectControlIssues(root.value, fields.value, values.value) }
  function check(candidate = values.value) {
    const required = collectSubmissionIssues(fields.value, candidate)
    const ids = new Set(required.map(issue => issue.id))
    return [...required, ...collectControlIssues(root.value, fields.value, candidate).filter(issue => !ids.has(issue.id))]
  }
  watch([fields, values], () => { if (checked) refreshControls() }, { deep: true, flush: 'post' })
  async function validate() {
    checked = true
    await nextTick()
    if (!active) return false
    refreshControls()
    if (!issues.value.length) return true
    await panel.value?.reveal()
    return false
  }
  async function navigate(issue: SubmissionIssue) {
    if (!issues.value.some(current => current.id === issue.id)) return
    if (activeTab) activeTab.value = issue.tabId
    await nextTick()
    if (!active) return
    const table = tables.get(issue.fieldname)
    if (table) await table.revealIssue(issue)
    else focusSubmissionField(findSubmissionField(root.value, issue.fieldname))
  }
  function registerTable(fieldname: string, table: any) {
    if (table) tables.set(fieldname, table)
    else tables.delete(fieldname)
  }
  function reset() { checked = false; controlIssues.value = [] }
  return { root, panel, issues, validate, check, navigate, registerTable, reset }
}
