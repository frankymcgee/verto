<template>
  <section class="min-h-screen bg-surface-gray-1">
    <main class="space-y-3 px-3 py-3 pb-[calc(var(--mobile-bottom-tabs-height,4rem)+2rem)]">
      <!-- Loading State -->
      <Card
        v-if="loading"
        class="p-3"
      >
        <div class="space-y-3">
          <div class="h-4 w-36 rounded bg-surface-gray-3" />
          <div class="h-24 rounded-xl bg-surface-gray-2" />
          <div class="h-24 rounded-xl bg-surface-gray-2" />
          <div class="h-24 rounded-xl bg-surface-gray-2" />
        </div>
      </Card>

      <!-- Error State -->
      <Card
        v-else-if="error"
        class="border border-red-200 bg-red-50 p-3"
      >
        <div class="space-y-2">
          <p class="text-sm font-medium text-red-800">
            Could not load assigned work
          </p>

          <p class="text-sm text-red-700">
            {{ error }}
          </p>
        </div>
      </Card>

      <template v-else>
        <!-- Refresh Row -->
        <div class="flex items-center justify-end">
          <Button
            variant="subtle"
            theme="gray"
            size="sm"
            :loading="loading"
            :disabled="loading"
            @click="loadHome"
          >
            Refresh
          </Button>
        </div>

        <!-- Empty State -->
        <Card
          v-if="groupedTasks.length === 0"
          class="p-3"
        >
          <div class="rounded-xl border border-dashed border-outline-gray-2 bg-surface-gray-1 px-3 py-6 text-center">
            <p class="text-sm font-medium text-ink-gray-7">
              No tasks allocated.
            </p>

            <p class="mt-1 text-sm text-ink-gray-5">
              Assigned work will appear here when it is allocated to you.
            </p>
          </div>
        </Card>

        <!-- Scope Groups -->
        <Card
          v-for="scope in groupedTasks"
          :key="scope.scope_name"
          class="overflow-hidden border border-outline-gray-1 bg-surface-white"
        >
          <!-- Scope Header -->
          <button
            type="button"
            class="flex w-full items-center justify-between gap-3 border-b border-outline-gray-1 px-3 py-3 text-left active:scale-[0.99]"
            @click="toggleScope(scope.scope_name)"
          >
            <div class="min-w-0">
              <p class="truncate text-base font-semibold text-ink-gray-9">
                {{ scope.scope_name }}
              </p>
            </div>

            <div class="flex shrink-0 items-center gap-2">
              <Badge variant="subtle">
                {{ getScopeAverageProgress(scope) }}%
              </Badge>

              <span class="text-xl font-medium text-ink-gray-5">
                {{ openScopes[scope.scope_name] ? '−' : '+' }}
              </span>
            </div>
          </button>

          <!-- Scope Body -->
          <div
            v-if="openScopes[scope.scope_name]"
            class="space-y-3 p-2"
          >
            <!-- Parent Groups -->
            <Card
              v-for="parent in scope.parent_groups"
              :key="parent.parent_task_name"
              class="overflow-hidden border border-outline-gray-1 bg-surface-gray-1"
            >
              <button
                type="button"
                class="w-full px-3 py-3 text-left active:scale-[0.99]"
                @click="toggleParent(getParentKey(scope, parent))"
              >
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <p class="truncate text-sm font-semibold text-ink-gray-9">
                      {{ parent.parent_task_name }}
                    </p>
                  </div>

                  <span class="shrink-0 text-lg font-medium text-ink-gray-5">
                    {{ openParents[getParentKey(scope, parent)] ? '−' : '+' }}
                  </span>
                </div>

                <div class="mt-3 h-2 overflow-hidden rounded-full bg-surface-gray-3">
                  <div
                    class="h-full rounded-full bg-blue-600 transition-all"
                    :style="{ width: `${clampPercent(parent.progress || 0)}%` }"
                  />
                </div>
              </button>

              <div
                v-if="openParents[getParentKey(scope, parent)]"
                class="space-y-3 border-t border-outline-gray-1 bg-surface-white p-2"
              >
                <Button
                  as="a"
                  variant="subtle"
                  theme="gray"
                  class="w-full justify-center"
                  :href="getAreaGanttUrl(parent)"
                >
                  Area Gantt
                </Button>

                <!-- Tasks -->
                <Card
                  v-for="task in parent.tasks"
                  :key="task.name"
                  class="overflow-hidden border border-outline-gray-1 bg-surface-white"
                >
                  <div class="space-y-3 p-3">
                    <div class="flex items-start justify-between gap-3">
                      <div class="min-w-0 flex-1">
                        <h3 class="text-base font-semibold text-ink-gray-9">
                          {{ task.subject || task.name }}
                        </h3>

                        <p class="mt-1 text-xs text-ink-gray-5">
                          {{ formatDate(task.exp_start_date) }}
                          {{ formatTime(task.exp_start_time) }}
                          -
                          {{ formatDate(task.exp_end_date) }}
                          {{ formatTime(task.exp_end_time) }}
                        </p>
                      </div>

                      <Badge
                        v-if="task.status"
                        variant="subtle"
                      >
                        {{ task.status }}
                      </Badge>
                    </div>

                    <div>
                      <div
                        class="h-2 overflow-hidden rounded-full"
                        :style="{ backgroundColor: getPriorityColor(task.priority) }"
                      >
                        <div
                          class="h-full rounded-full bg-black/20 transition-all"
                          :style="{ width: `${clampPercent(task.progress || 0)}%` }"
                        />
                      </div>

                      <div class="mt-1 flex items-center justify-between text-xs text-ink-gray-5">
                        <span>{{ task.priority || 'No priority' }}</span>
                        <span>{{ clampPercent(task.progress || 0) }}%</span>
                      </div>
                    </div>

                    <div class="flex flex-wrap gap-2">
                      <Badge
                        v-if="task.responsible_contractor"
                        variant="subtle"
                      >
                        Vendor: {{ task.responsible_contractor }}
                      </Badge>

                      <Badge
                        v-if="task.work_order_number"
                        variant="subtle"
                      >
                        WO: {{ task.work_order_number }}
                      </Badge>
                    </div>

                    <div class="grid grid-cols-2 gap-2 pt-1">
                      <Button
                        variant="solid"
                        theme="gray"
                        class="w-full justify-center"
                        @click="openPicker('form', task)"
                      >
                        + Form
                      </Button>

                      <Button
                        variant="subtle"
                        theme="gray"
                        class="w-full justify-center"
                        @click="openPicker('ccv', task)"
                      >
                        + CCV
                      </Button>
                    </div>
                  </div>
                </Card>
              </div>
            </Card>

            <!-- Project Links -->
            <div class="grid grid-cols-3 gap-2">
              <Button
                as="a"
                variant="subtle"
                theme="gray"
                class="justify-center"
                :href="getProjectGanttUrl(scope)"
              >
                Gantt
              </Button>

              <Button
                as="a"
                variant="subtle"
                theme="gray"
                class="justify-center"
                :href="getProjectMapUrl(scope)"
              >
                Map
              </Button>

              <Button
                as="a"
                variant="subtle"
                theme="gray"
                class="justify-center"
                :href="getShareFolder(scope)"
                target="_blank"
                rel="noopener noreferrer"
              >
                Folder
              </Button>
            </div>

            <div class="grid grid-cols-3 gap-2">
              <Button
                as="a"
                variant="subtle"
                theme="gray"
                class="justify-center"
                :href="getHandoverUrl(scope)"
                target="_blank"
                rel="noopener noreferrer"
              >
                Handover
              </Button>

              <Button
                as="a"
                variant="subtle"
                theme="gray"
                class="justify-center"
                :href="getGameplanUrl(scope)"
                target="_blank"
                rel="noopener noreferrer"
              >
                Gameplan
              </Button>

              <Button
                as="a"
                variant="subtle"
                theme="gray"
                class="justify-center"
                :href="getRavenUrl(scope)"
                target="_blank"
                rel="noopener noreferrer"
              >
                Chat
              </Button>
            </div>
          </div>
        </Card>

        <!-- Generic Form Button -->
        <Button
          variant="solid"
          theme="gray"
          size="lg"
          class="w-full justify-center"
          @click="openPicker('generic')"
        >
          + Form
        </Button>
      </template>
    </main>

    <!-- Picker Sheet -->
    <div
      v-if="pickerOpen"
      class="fixed inset-0 z-[60] flex items-end bg-black/40 px-0"
      @click.self="closePicker"
    >
      <Card class="max-h-[75vh] w-full overflow-hidden rounded-b-none rounded-t-3xl border border-outline-gray-1 bg-surface-white">
        <div class="flex items-center justify-between border-b border-outline-gray-1 px-4 py-3">
          <div class="min-w-0">
            <h2 class="truncate text-lg font-semibold text-ink-gray-9">
              {{ pickerTitle }}
            </h2>

            <p
              v-if="pickerTask?.subject"
              class="mt-1 truncate text-sm text-ink-gray-5"
            >
              {{ pickerTask.subject }}
            </p>
          </div>

          <Button
            variant="subtle"
            theme="gray"
            @click="closePicker"
          >
            Close
          </Button>
        </div>

        <div class="max-h-[calc(75vh-72px)] space-y-2 overflow-auto p-4 pb-[calc(env(safe-area-inset-bottom)+1rem)]">
          <button
            v-for="button in pickerButtons"
            :key="button.mobile_doctype"
            type="button"
            class="w-full rounded-xl border border-outline-gray-1 bg-surface-white p-3 text-left shadow-sm transition active:scale-[0.99]"
            @click="createFromPicker(button)"
          >
            <p class="font-semibold text-ink-gray-9">
              {{ button.label }}
            </p>

            <p class="mt-1 text-xs text-ink-gray-5">
              {{ button.doctype }}
            </p>
          </button>

          <div
            v-if="pickerButtons.length === 0"
            class="rounded-xl border border-dashed border-outline-gray-2 bg-surface-gray-1 px-4 py-6 text-center"
          >
            <p class="text-sm font-medium text-ink-gray-7">
              No forms available.
            </p>

            <p class="mt-1 text-sm text-ink-gray-5">
              Check the mobile form configuration for this action.
            </p>
          </div>
        </div>
      </Card>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  Badge,
  Button,
  Card,
} from 'frappe-ui'
import { apiRequest } from '../lib/api'

type HomeButton = {
  label: string
  doctype: string
  mobile_doctype: string
}

type TaskItem = Record<string, any>

type ParentGroup = {
  parent_task_name: string
  parent_task: string
  progress: number
  project: string
  project_details: Record<string, any>
  tasks: TaskItem[]
}

type ScopeGroup = {
  scope_name: string
  project: string
  project_details: Record<string, any>
  parent_groups: ParentGroup[]
}

type HomePayload = {
  user: string
  full_name?: string
  user_full_name?: string
  user_fullname?: string
  user_name?: string
  employee_name?: string
  handover_base: string
  raven_base: string
  grouped_tasks: ScopeGroup[]
  generic_forms: HomeButton[]
  task_forms: HomeButton[]
  ccv_forms: HomeButton[]
}

type FrappeResponse<T> = {
  message: T
}

const loading = ref(true)
const error = ref('')
const home = ref<HomePayload | null>(null)

const openScopes = ref<Record<string, boolean>>({})
const openParents = ref<Record<string, boolean>>({})

const pickerOpen = ref(false)
const pickerType = ref<'generic' | 'form' | 'ccv'>('generic')
const pickerTask = ref<TaskItem | null>(null)

const groupedTasks = computed(() => {
  return home.value?.grouped_tasks || []
})

const pickerTitle = computed(() => {
  if (pickerType.value === 'ccv') {
    return 'Select CCV to Create'
  }

  return 'Select Form to Create'
})

const pickerButtons = computed(() => {
  if (!home.value) {
    return []
  }

  if (pickerType.value === 'ccv') {
    return home.value.ccv_forms || []
  }

  if (pickerType.value === 'form') {
    return home.value.task_forms || []
  }

  return home.value.generic_forms || []
})

function toggleScope(name: string) {
  openScopes.value[name] = !openScopes.value[name]
}

function toggleParent(key: string) {
  openParents.value[key] = !openParents.value[key]
}

function openPicker(type: 'generic' | 'form' | 'ccv', task?: TaskItem) {
  pickerType.value = type
  pickerTask.value = task || null
  pickerOpen.value = true
}

function closePicker() {
  pickerOpen.value = false
  pickerTask.value = null
}

function createFromPicker(button: HomeButton) {
  const query = new URLSearchParams()

  if (pickerTask.value?.name) {
    query.set('link_task', pickerTask.value.name)
  }

  if (pickerTask.value?.project) {
    query.set('project', pickerTask.value.project)
  }

  if (pickerTask.value?.project_scope_name) {
    query.set('project_scope_name', pickerTask.value.project_scope_name)
  }

  if (pickerTask.value?.parent_task_name) {
    query.set('parent_task_name', pickerTask.value.parent_task_name)
  }

  if (pickerTask.value?.work_order_number) {
    query.set('work_order_number', pickerTask.value.work_order_number)
  }

  const queryString = query.toString()

  window.location.href = `/verto-mobile/new/${button.mobile_doctype}${queryString ? `?${queryString}` : ''}`
}

function getParentKey(scope: ScopeGroup, parent: ParentGroup) {
  return `${scope.scope_name}::${parent.parent_task_name}`
}

function getScopeAverageProgress(scope: ScopeGroup) {
  const parents = scope.parent_groups || []

  if (!parents.length) {
    return 0
  }

  const totalProgress = parents.reduce((total, parent) => {
    return total + Number(parent.progress || 0)
  }, 0)

  return Math.round(totalProgress / parents.length)
}

function clampPercent(value: number) {
  if (!Number.isFinite(Number(value))) {
    return 0
  }

  return Math.max(0, Math.min(100, Math.round(Number(value))))
}

function formatDate(value?: string) {
  if (!value) {
    return ''
  }

  const date = new Date(`${value}T00:00:00`)

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleDateString('en-AU', {
    day: 'numeric',
    month: 'short',
  })
}

function formatTime(value?: string) {
  if (!value) {
    return ''
  }

  const [rawHours, rawMinutes = '00'] = value.split(':')
  let hours = Number(rawHours)

  if (!Number.isFinite(hours)) {
    return value
  }

  const ampm = hours >= 12 ? 'pm' : 'am'
  hours = hours % 12 || 12

  return `${hours}:${rawMinutes}${ampm}`
}

function getPriorityColor(priority?: string) {
  const map: Record<string, string> = {
    Low: '#dcfce7',
    Medium: '#fef9c3',
    High: '#ffedd5',
    Urgent: '#fee2e2',
  }

  return map[priority || ''] || '#f3f4f6'
}

function getProjectGanttUrl(scope: ScopeGroup) {
  return `/app/task/view/gantt?status=%5B%22not%20in%22%2C%5B%22Completed%22%2C%22Cancelled%22%5D%5D&type=%5B%22not%20in%22%2C%5B%22Task%20Step%22%2C%22Outline%22%5D%5D&project=${encodeURIComponent(scope.project || '')}`
}

function getProjectMapUrl(scope: ScopeGroup) {
  return `/app/task/view/map?status=%5B%22not%20in%22%2C%5B%22Completed%22%2C%22Cancelled%22%5D%5D&type=Work%20Summary&project=${encodeURIComponent(scope.project || '')}`
}

function getAreaGanttUrl(parent: ParentGroup) {
  return `/app/task/view/gantt?status=%5B%22not%20in%22%2C%5B%22Completed%22%2C%22Cancelled%22%5D%5D&type=%5B%22not%20in%22%2C%5B%22Task%20Step%22%2C%22Outline%22%5D%5D&name=%5B%22descendants%20of%20%28inclusive%29%22%2C%22${encodeURIComponent(parent.parent_task || '')}%22%5D&project=${encodeURIComponent(parent.project || '')}`
}

function getShareFolder(scope: ScopeGroup) {
  const firstTask = scope.parent_groups?.[0]?.tasks?.[0]

  return firstTask?.share_folder || '#'
}

function getHandoverUrl(scope: ScopeGroup) {
  return `${home.value?.handover_base || ''}/${encodeURIComponent(scope.scope_name)}`
}

function getGameplanUrl(scope: ScopeGroup) {
  const project = scope.project_details || {}
  const team = project.gameplan_team_name || ''
  const gameplanProject = project.gameplan_project || ''

  return `/g/${team}/projects/${gameplanProject}`
}

function getRavenUrl(scope: ScopeGroup) {
  const project = scope.project_details || {}
  const workspace = project.raven_workspace || ''
  const channel = project.raven_channel || ''

  return `${home.value?.raven_base || '/raven'}/${encodeURIComponent(workspace)}/${encodeURIComponent(channel)}`
}

async function loadHome() {
  loading.value = true
  error.value = ''

  try {
    const data = await apiRequest<FrappeResponse<HomePayload>>(
      '/api/method/verto.api.mobile.home.get_home_summary'
    )

    home.value = data.message

    for (const scope of data.message.grouped_tasks || []) {
      if (openScopes.value[scope.scope_name] === undefined) {
        openScopes.value[scope.scope_name] = false
      }

      for (const parent of scope.parent_groups || []) {
        const key = getParentKey(scope, parent)

        if (openParents.value[key] === undefined) {
          openParents.value[key] = false
        }
      }
    }
  } catch (err) {
    if (err instanceof Error && err.message === 'Login required') {
      return
    }

    error.value = err instanceof Error ? err.message : 'Could not load assigned tasks.'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadHome()
})
</script>