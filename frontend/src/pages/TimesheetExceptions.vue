<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Button, FormControl } from 'frappe-ui'
import { apiRequest } from '../lib/api'

type Source = { doctype: string; name: string; label: string }
type Exception = {
  id: string; employee: string; employee_name: string; project: string; project_name: string
  date: string; title: string; hours: number | null; categories: string[]; severity: string
  issues: { code: string; message: string }[]; links: Source[]; internal_approved: boolean
}
type Report = {
  week_start: string; week_end: string; generated_at: string; items: Exception[]; warnings: string[]
  categories: { value: string; label: string; count: number }[]; projects: { value: string; label: string }[]
}
const route = useRoute()
const week = ref(typeof route.query.week_start === 'string' ? route.query.week_start : '')
const project = ref(typeof route.query.project === 'string' ? route.query.project : '')
const projects = ref<Report['projects']>([])
const report = ref<Report | null>(null)
const loading = ref(false)
const error = ref('')
const category = ref('')
const search = ref('')
const severity = ref('')
const page = ref(0)
const pageSize = 25
let requestId = 0
const projectOptions = computed(() => [{ value: '', label: 'All projects' }, ...projects.value])
const filtered = computed(() => {
  const term = search.value.trim().toLocaleLowerCase()
  return (report.value?.items || []).filter(item => (!category.value || item.categories.includes(category.value))
    && (!severity.value || severity.value === item.severity)
    && (!term || [item.employee_name, item.employee, item.project_name, item.project, ...item.links.map(link => link.name)].join(' ').toLocaleLowerCase().includes(term)))
})
const visible = computed(() => filtered.value.slice(page.value * pageSize, (page.value + 1) * pageSize))
const highCount = computed(() => report.value?.items.filter(item => item.severity === 'high').length || 0)
watch([category, search, severity, report], () => { page.value = 0 })

const slugs: Record<string, string> = { Timesheet: 'timesheet', 'Daily Timesheet': 'daily-timesheet',
  'Shift Assignment': 'shift-assignment', Attendance: 'attendance', 'Leave Application': 'leave-application' }
function sourceHref(link: Source) {
  return slugs[link.doctype] ? `/desk/${slugs[link.doctype]}/${encodeURIComponent(link.name)}` : '#'
}
function reviewHref(item?: Exception) {
  const params = new URLSearchParams({ week_start: report.value?.week_start || week.value })
  const projectId = item?.project || project.value
  if (projectId) params.set('project', projectId)
  const weekly = item?.links.find(link => link.doctype === 'Timesheet')
  if (weekly) params.set('timesheets', JSON.stringify([weekly.name]))
  return `/desk/internal-timesheet-approval?${params}`
}
function dateLabel(value: string) {
  const date = new Date(`${value}T12:00:00`)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}
async function load() {
  const id = ++requestId
  error.value = ''
  report.value = null
  if (week.value && (Number.isNaN(new Date(`${week.value}T12:00:00`).getTime()) || new Date(`${week.value}T12:00:00`).getDay() !== 1)) {
    loading.value = false
    error.value = 'Choose a Monday for the week beginning date.'
    return
  }
  loading.value = true
  const params = new URLSearchParams()
  if (week.value) params.set('week_start', week.value)
  if (project.value) params.set('project', project.value)
  try {
    const response = await apiRequest<{ message: Report }>(`/api/method/verto.api.timesheet_exceptions.get_timesheet_exceptions?${params}`, { cache: 'no-store' })
    if (id !== requestId) return
    report.value = response.message
    week.value = response.message.week_start
    projects.value = [...new Map([...projects.value, ...response.message.projects].map(row => [row.value, row])).values()]
  } catch (err) {
    if (id === requestId) error.value = err instanceof Error ? err.message : 'Could not check timesheets. Try again.'
  } finally {
    if (id === requestId) loading.value = false
  }
}
onMounted(load)
onBeforeUnmount(() => { requestId += 1 })
</script>

<template>
  <section class="mx-auto w-full max-w-7xl space-y-4 px-[var(--verto-page-x,0.75rem)] py-[var(--verto-page-y,0.75rem)] pb-8" :aria-busy="loading">
    <header class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 class="text-xl-semibold text-ink-gray-9">Timesheet exceptions</h1>
        <p class="mt-1 text-sm text-ink-gray-6">Check outstanding hours and resolve discrepancies before internal approval.</p>
      </div>
      <a v-if="report" :href="reviewHref()" class="rounded-5 border border-outline-gray-2 px-3 py-2 text-sm-medium text-ink-gray-9">Open internal review</a>
    </header>
    <form class="flex flex-wrap items-end gap-3 rounded-7 border border-outline-gray-1 bg-surface-base p-4" @submit.prevent="load">
      <FormControl v-model="week" type="date" label="Week beginning (Monday)" :disabled="loading" class="min-w-0 flex-1 basis-44" />
      <FormControl v-model="project" type="select" label="Project" :options="projectOptions" :disabled="loading" class="min-w-0 flex-1 basis-48" />
      <Button type="submit" variant="solid" :loading="loading" :disabled="loading">{{ report ? 'Refresh queue' : 'Check week' }}</Button>
    </form>
    <p v-if="loading" role="status" class="py-8 text-center text-sm text-ink-gray-6">Checking timesheets, allocations and attendance…</p>
    <div v-else-if="error" class="space-y-3 rounded-7 border border-outline-red-1 bg-surface-base p-4">
      <p role="alert" class="break-words text-sm text-ink-red-4">{{ error }}</p>
      <Button @click="load">Try again</Button>
    </div>
    <template v-else-if="report">
      <div class="flex flex-wrap gap-x-6 gap-y-2 text-sm text-ink-gray-7" role="status">
        <span>{{ dateLabel(report.week_start) }} – {{ dateLabel(report.week_end) }}</span>
        <strong>{{ report.items.length }} {{ report.items.length === 1 ? 'exception' : 'exceptions' }} · {{ highCount }} high priority</strong>
      </div>
      <p class="text-xs text-ink-gray-6">Checked {{ report.generated_at }} (site time). Refresh after correcting a source record or after weekly processing finishes.</p>
      <details v-if="report.warnings.length" class="rounded-7 border border-outline-gray-1 bg-surface-base p-3 text-sm text-ink-gray-6" :open="report.warnings.length > 1">
        <summary class="cursor-pointer font-medium">Check coverage{{ report.warnings.length > 1 ? ' · some checks unavailable' : '' }}</summary>
        <ul class="mt-2 list-disc space-y-1 pl-5"><li v-for="warning in report.warnings" :key="warning">{{ warning }}</li></ul>
      </details>
      <div class="flex flex-wrap gap-2" aria-label="Exception type">
        <Button :variant="category === '' ? 'solid' : 'subtle'" :aria-pressed="category === ''" @click="category = ''">All ({{ report.items.length }})</Button>
        <Button v-for="option in report.categories" :key="option.value" :variant="category === option.value ? 'solid' : 'subtle'" :aria-pressed="category === option.value" @click="category = option.value">{{ option.label }} ({{ option.count }})</Button>
      </div>
      <div class="flex flex-wrap gap-3">
        <FormControl v-model="search" type="text" label="Employee or record" placeholder="Search employee, project or source record" class="min-w-0 flex-1 basis-64" />
        <FormControl v-model="severity" type="select" label="Priority" :options="[{ label: 'All priorities', value: '' }, { label: 'High priority', value: 'high' }]" class="min-w-0 basis-40" />
      </div>
      <p v-if="!filtered.length" role="status" class="rounded-7 border border-outline-gray-1 bg-surface-base p-8 text-center text-sm text-ink-gray-7">{{ report.items.length ? 'No exceptions match these filters.' : 'No exceptions found in the records checked for this week.' }}</p>
      <ol v-else class="space-y-3" aria-label="Timesheet exceptions">
        <li v-for="item in visible" :key="item.id" class="space-y-3 rounded-7 border border-outline-gray-1 bg-surface-base p-4">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="min-w-0">
              <h2 class="break-words text-base-semibold text-ink-gray-9">{{ item.employee_name }}</h2>
              <p class="break-words text-sm text-ink-gray-6">{{ item.employee }} · {{ item.project_name }} · {{ dateLabel(item.date) }}</p>
            </div>
            <span class="shrink-0 rounded-5 px-2 py-1 text-xs-medium" :class="item.severity === 'high' ? 'bg-surface-red-1 text-ink-red-4' : 'bg-surface-gray-2 text-ink-gray-7'">{{ item.severity === 'high' ? 'High priority' : 'Review required' }}</span>
          </div>
          <p class="text-sm-medium text-ink-gray-9">{{ item.title }}<span v-if="item.hours !== null"> · {{ Number(item.hours).toFixed(2) }} hours</span><span v-if="item.internal_approved" class="ml-2 text-xs text-ink-gray-6">Internally approved</span></p>
          <ul class="list-disc space-y-1 pl-5 text-sm text-ink-gray-7"><li v-for="(issue, index) in item.issues" :key="`${issue.code}:${index}`" class="break-words">{{ issue.message }}</li></ul>
          <div class="flex flex-wrap gap-3 text-sm-medium">
            <a v-for="link in item.links" :key="`${link.doctype}:${link.name}`" :href="sourceHref(link)" target="_blank" rel="noopener" class="text-ink-blue-link underline">{{ link.label }}</a>
            <a v-if="item.links.some(link => link.doctype === 'Timesheet')" :href="reviewHref(item)" class="text-ink-blue-link underline">Review for approval</a>
          </div>
        </li>
      </ol>
      <nav v-if="filtered.length > pageSize" class="flex flex-wrap items-center justify-between gap-3" aria-label="Queue pages">
        <Button :disabled="page === 0" @click="page -= 1">Previous</Button>
        <p class="text-sm text-ink-gray-6">{{ page * pageSize + 1 }}–{{ Math.min((page + 1) * pageSize, filtered.length) }} of {{ filtered.length }}</p>
        <Button :disabled="(page + 1) * pageSize >= filtered.length" @click="page += 1">Next</Button>
      </nav>
    </template>
  </section>
</template>
