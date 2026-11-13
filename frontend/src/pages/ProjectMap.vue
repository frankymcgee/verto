<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button } from 'frappe-ui'
import type { MobileFormOption } from '../components/MobileFormPicker.vue'
import TaskDetailsSheet from '../components/TaskDetailsSheet.vue'
import TaskLocationMap, { type ProjectMapSettings, type TaskLocation } from '../components/TaskLocationMap.vue'
import { apiRequest } from '../lib/api'
import { scheduleTask, type ScheduleTask, type ScheduleTaskRecord } from '../lib/ganttSchedule'

type ProjectLocations = {
  project_name: string
  map_settings: ProjectMapSettings
  tasks: (ScheduleTaskRecord & { location?: string | null; responsible_contractor?: string | null })[]
  task_forms: MobileFormOption[]
  ccv_forms: MobileFormOption[]
}

const route = useRoute()
const router = useRouter()
const project = computed(() => String(route.params.project || '').trim())
const data = shallowRef<ProjectLocations | null>(null)
const loading = ref(false)
const error = ref('')
const selectedTask = shallowRef<ScheduleTask | null>(null)
const locations = computed<TaskLocation[]>(() => (data.value?.tasks || []).map((row) => ({
  task: scheduleTask(row),
  contractor: row.responsible_contractor || '',
  location: row.location || null,
})))
const titlesByName = computed(() => new Map(locations.value.map(({ task }) => [task.name, task.title])))
const options = computed(() => ({ form: data.value?.task_forms || [], ccv: data.value?.ccv_forms || [] }))

let pending: AbortController | undefined

async function loadLocations() {
  pending?.abort()
  const request = new AbortController()
  pending = request
  loading.value = true
  error.value = ''
  const params = new URLSearchParams({ project: project.value })

  try {
    const { message } = await apiRequest<{ message: ProjectLocations }>(
      `/api/method/verto.api.mobile.project_map.get_locations?${params}`,
      { cache: 'no-store', signal: request.signal },
    )
    if (!request.signal.aborted) data.value = message
  } catch {
    if (request.signal.aborted) return
    error.value = navigator.onLine
      ? 'Could not load the map. Check your access and try again.'
      : 'Connect to the internet to load the map.'
  } finally {
    if (!request.signal.aborted) loading.value = false
  }
}

watch(project, () => {
  selectedTask.value = null
  data.value = null
  void loadLocations()
}, { immediate: true })

onBeforeUnmount(() => pending?.abort())
</script>

<template>
  <section class="flex min-h-full min-w-0 flex-col gap-4 px-[var(--verto-page-x)] py-[var(--verto-page-y)]" :aria-busy="loading">
    <header class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <h1 class="text-xl-semibold text-ink-gray-9">Project Map</h1>
        <p class="mt-1 break-words text-base-medium text-ink-gray-7">{{ data?.project_name || project }}</p>
      </div>
      <Button class="min-h-11 shrink-0" variant="subtle" @click="router.push('/')">Home</Button>
    </header>

    <p v-if="loading" class="rounded-7 bg-surface-base p-4 text-sm text-ink-gray-6" role="status">
      Loading task locations…
    </p>
    <div v-else-if="error" class="space-y-3 rounded-7 border border-outline-gray-1 bg-surface-base p-4">
      <p class="text-sm text-ink-gray-8" role="alert">{{ error }}</p>
      <Button class="min-h-11" variant="subtle" @click="loadLocations">Try again</Button>
    </div>
    <TaskLocationMap
      v-else-if="data && locations.length"
      :locations="locations"
      :settings="data.map_settings"
      @select="selectedTask = $event"
    />
    <p v-else class="rounded-7 border border-outline-gray-1 bg-surface-base p-4 text-sm text-ink-gray-6">
      No active Work Summaries have a location on this map.
    </p>

    <TaskDetailsSheet
      :task="selectedTask"
      :project="project"
      :options="options"
      :titles-by-name="titlesByName"
      @close="selectedTask = null"
    />
  </section>
</template>
