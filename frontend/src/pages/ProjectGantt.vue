<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button } from 'frappe-ui'
import type { MobileFormOption } from '../components/MobileFormPicker.vue'
import TaskDetailsSheet from '../components/TaskDetailsSheet.vue'
import ProjectGanttTimeline from '../components/ProjectGanttTimeline.vue'
import { apiRequest } from '../lib/api'
import { hasTimelineDates, scheduleRange, scheduleTask } from '../lib/ganttSchedule'
import type { ScheduleTask, ScheduleTaskRecord } from '../lib/ganttSchedule'

type SchedulePage = {
  project_name: string
  area_name: string | null
  tasks: ScheduleTaskRecord[]
  next_start: number | null
  task_forms?: MobileFormOption[]
  ccv_forms?: MobileFormOption[]
}

const route = useRoute()
const router = useRouter()
const project = computed(() => String(route.params.project || '').trim())
const area = computed(() => typeof route.query.area === 'string' ? route.query.area.trim() : '')
const projectTitle = ref('')
const areaTitle = ref('')
const tasks = shallowRef<ScheduleTask[]>([])
const nextStart = ref<number | null>(null)
const loading = ref(false)
const error = ref('')
const view = ref<'Day' | 'Week' | 'Month' | 'List'>('Day')
const timeline = ref<InstanceType<typeof ProjectGanttTimeline> | null>(null)
const todayAvailable = ref(false)
const selectedTask = shallowRef<ScheduleTask | null>(null)
const formOptions = shallowRef({ form: [] as MobileFormOption[], ccv: [] as MobileFormOption[] })
const datedTasks = computed(() => tasks.value.filter(hasTimelineDates))
const tasksWithoutBars = computed(() => tasks.value.length - datedTasks.value.length)
const titlesByName = computed(() => new Map(tasks.value.map((task) => [task.name, task.title])))

let pending: AbortController | undefined

async function loadSchedule(start = 0) {
  pending?.abort()
  const request = new AbortController()
  pending = request
  loading.value = true
  error.value = ''

  const params = new URLSearchParams({ project: project.value, start: String(start) })
  if (area.value) params.set('area', area.value)

  try {
    const { message } = await apiRequest<{ message: SchedulePage }>(
      `/api/method/verto.api.mobile.gantt.get_schedule?${params}`,
      { cache: 'no-store', signal: request.signal },
    )
    if (request.signal.aborted) return

    const updated = new Map((start ? tasks.value : []).map((task) => [task.name, task]))
    for (const row of message.tasks) updated.set(row.name, scheduleTask(row))
    tasks.value = [...updated.values()]
    projectTitle.value = message.project_name
    areaTitle.value = message.area_name || ''
    nextStart.value = message.next_start
    if (!start) formOptions.value = { form: message.task_forms || [], ccv: message.ccv_forms || [] }
  } catch {
    if (request.signal.aborted) return
    if (!navigator.onLine) error.value = 'Connect to the internet to load the schedule.'
    else error.value = start ? 'Could not load more tasks. Try again.' : 'Could not load the schedule. Check your access and try again.'
  } finally {
    if (!request.signal.aborted) loading.value = false
  }
}

watch([project, area], () => {
  tasks.value = []
  nextStart.value = null
  projectTitle.value = ''
  areaTitle.value = ''
  selectedTask.value = null
  todayAvailable.value = false
  void loadSchedule()
}, { immediate: true })

onBeforeUnmount(() => pending?.abort())
</script>

<template>
  <section class="min-w-0 space-y-4 px-[var(--verto-page-x)] py-[var(--verto-page-y)] pb-6" :aria-busy="loading">
    <header class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <h1 class="text-xl-semibold text-ink-gray-9">{{ area ? 'Area Gantt' : 'Project Gantt' }}</h1>
        <p class="mt-1 break-words text-base-medium text-ink-gray-7">{{ projectTitle || project }}</p>
        <p v-if="areaTitle" class="mt-0.5 break-words text-sm text-ink-gray-6">{{ areaTitle }}</p>
      </div>
      <Button class="min-h-11 shrink-0" variant="subtle" @click="router.push('/')">Home</Button>
    </header>

    <p v-if="loading && !tasks.length" class="rounded-7 bg-surface-base p-4 text-sm text-ink-gray-6" role="status">
      Loading schedule…
    </p>
    <div v-else-if="error && !tasks.length" class="space-y-3 rounded-7 border border-outline-gray-1 bg-surface-base p-4">
      <p class="text-sm text-ink-gray-8" role="alert">{{ error }}</p>
      <Button class="min-h-11" variant="subtle" @click="loadSchedule()">Try again</Button>
    </div>
    <p v-else-if="!tasks.length" class="rounded-7 border border-outline-gray-1 bg-surface-base p-4 text-sm text-ink-gray-6">
      No active tasks in this {{ area ? 'area' : 'project' }}.
    </p>

    <template v-else>
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="flex flex-wrap items-center gap-2">
          <label for="project-gantt-view" class="text-sm-medium text-ink-gray-7">View</label>
          <select id="project-gantt-view" v-model="view" class="h-11 rounded-6 border border-outline-gray-2 bg-surface-base px-3 text-base text-ink-gray-9">
            <option>Day</option>
            <option>Week</option>
            <option>Month</option>
            <option value="List">Task list</option>
          </select>
          <Button
            v-if="view !== 'List' && datedTasks.length"
            class="min-h-11"
            variant="outline"
            :disabled="!todayAvailable"
            :title="todayAvailable ? undefined : 'Today is outside the displayed timeline'"
            @click="timeline?.scrollToToday()"
          >
            Today
          </Button>
        </div>
        <Button v-if="nextStart !== null" class="min-h-11" variant="outline" :disabled="loading" @click="loadSchedule(nextStart)">
          {{ loading ? 'Loading…' : 'Load more' }}
        </Button>
      </div>

      <ProjectGanttTimeline
        v-if="view !== 'List' && datedTasks.length"
        ref="timeline"
        :tasks="datedTasks"
        :scale="view"
        @select="selectedTask = $event"
        @today-available="todayAvailable = $event"
      />
      <template v-if="view !== 'List'">
        <p v-if="!datedTasks.length" class="rounded-7 border border-outline-gray-1 bg-surface-base p-4 text-sm text-ink-gray-6">
          No tasks with dates that can be shown on the timeline. View them in the task list.
        </p>
        <p v-else-if="tasksWithoutBars" class="text-sm text-ink-gray-6">
          {{ tasksWithoutBars }} {{ tasksWithoutBars === 1 ? 'task is' : 'tasks are' }} only shown in the task list.
        </p>
      </template>
      <ul v-else class="divide-y divide-outline-gray-1 rounded-7 border border-outline-gray-2 bg-surface-base">
        <li v-for="task in tasks" :key="task.name">
          <button type="button" class="flex w-full items-center justify-between gap-3 px-3 py-3 text-left hover:bg-surface-gray-1" @click="selectedTask = task">
            <span class="min-w-0">
              <span class="block break-words text-sm-semibold text-ink-gray-9">{{ task.title }}</span>
              <span class="mt-1 block text-xs text-ink-gray-6">{{ scheduleRange(task) }}</span>
            </span>
            <span class="shrink-0 text-sm-medium tabular-nums text-ink-gray-7">{{ task.progress }}%</span>
          </button>
        </li>
      </ul>

      <p class="text-sm text-ink-gray-6" role="status">{{ tasks.length }} {{ tasks.length === 1 ? 'task' : 'tasks' }} loaded</p>
      <p v-if="error" class="text-sm text-ink-red-4" role="alert">{{ error }}</p>
    </template>

    <TaskDetailsSheet
      :task="selectedTask"
      :project="project"
      :options="formOptions"
      :titles-by-name="titlesByName"
      @close="selectedTask = null"
    />
  </section>
</template>
