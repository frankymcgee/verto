<!-- VERTO_HOME_APP_BROWSER_DRAWER_2026_06_11 -->
<!-- VERTO_HOME_HANDOVER_TYPE_FROM_BASE_FIX_2026_06_11 -->
<template>
  <section class="h-full min-h-0 bg-surface-gray-1">
    <main class="space-y-3 px-[var(--verto-page-x,0.75rem)] py-[var(--verto-page-y,0.75rem)]">
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
          class="overflow-hidden border border-outline-gray-1 bg-surface-white !py-1 !px-1 !mt-1"
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

              <p class="mt-1 truncate text-xs text-ink-gray-5">
                {{ getProjectCustomer(scope) }}
              </p>
            </div>

            <div class="flex shrink-0 items-center gap-2">
              <div
                class="flex h-10 w-10 items-center justify-center overflow-hidden rounded-full border border-outline-gray-1 bg-surface-gray-2"
              >
                <img
                  v-if="getCustomerImage(scope)"
                  :src="getCustomerImage(scope)"
                  :alt="getProjectCustomer(scope) || 'Customer'"
                  class="h-full w-full object-cover"
                  @error="hideBrokenImage"
                >

                <span
                  v-else
                  class="text-sm font-semibold text-ink-gray-6"
                >
                  {{ getCustomerInitials(scope) }}
                </span>
              </div>

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
              class="overflow-hidden border border-outline-gray-1 bg-surface-gray-1 !py-1 !px-1 !mt-1"
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
                    <p class="mt-1 text-xs text-ink-gray-5">
                      Area Location
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
                  variant="subtle"
                  theme="gray"
                  class="w-full justify-center"
                  @click.stop="openInternalUrl(getAreaGanttUrl(parent), 'Area Gantt')"
                >
                  Area Gantt
                </Button>

                <!-- Tasks -->
                <Card
                  v-for="task in parent.tasks"
                  :key="task.name"
                  class="overflow-hidden border border-outline-gray-1 bg-surface-white !py-1 !px-1 !mt-1"
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
                variant="subtle"
                theme="gray"
                class="justify-center"
                @click="openInternalUrl(getProjectGanttUrl(scope), 'Gantt')"
              >
                Gantt
              </Button>

              <Button
                variant="subtle"
                theme="gray"
                class="justify-center"
                @click="openInternalUrl(getProjectMapUrl(scope), 'Map')"
              >
                Map
              </Button>

              <Button
                variant="subtle"
                theme="gray"
                class="justify-center"
                @click="openExternalUrl(getShareFolder(scope), 'Folder')"
              >
                Folder
              </Button>
            </div>

            <div class="grid grid-cols-2 gap-2">
              <Button
                variant="subtle"
                theme="gray"
                class="justify-center"
                @click="openProjectHandover(scope)"
              >
                Handover
              </Button>

              <Button
                variant="subtle"
                theme="gray"
                class="justify-center"
                @click="openPersonnelDrawer(scope)"
              >
                Personnel
              </Button>

              <Button
                variant="subtle"
                theme="gray"
                class="justify-center"
                @click="openExternalUrl(getGameplanUrl(scope), 'Gameplan')"
              >
                Gameplan
              </Button>

              <Button
                variant="subtle"
                theme="gray"
                class="justify-center"
                @click="openProjectChat(scope)"
              >
                Chat
              </Button>
            </div>

            <Button
              variant="solid"
              theme="gray"
              class="w-full justify-center"
              @click="analyseProjectWithPeri(scope)"
            >
              Analyse with PERI
            </Button>
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
    <Transition name="drawer-fade-slide">
      <div
        v-if="pickerOpen"
        class="fixed inset-0 z-[60] flex items-end bg-black/40 px-0"
        @click.self="closePicker"
      >
        <Card class="drawer-panel max-h-[75vh] w-full overflow-hidden rounded-b-none rounded-t-3xl border border-outline-gray-1 bg-surface-white">
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
    </Transition>

    <!-- Personnel Sheet -->
    <Transition name="drawer-fade-slide">
      <div
        v-if="personnelOpen"
        class="fixed inset-0 z-[60] flex items-end bg-black/40 px-0"
        @click.self="closePersonnelDrawer"
      >
        <Card class="drawer-panel max-h-[80vh] w-full overflow-hidden rounded-b-none rounded-t-3xl border border-outline-gray-1 bg-surface-white">
          <div class="sticky top-0 z-10 flex items-center justify-between border-b border-outline-gray-1 bg-surface-white px-4 py-3">
            <div class="min-w-0">
              <h2 class="truncate text-lg font-semibold text-ink-gray-9">
                Project Personnel
              </h2>

              <p
                v-if="personnelProjectTitle"
                class="mt-1 truncate text-sm text-ink-gray-5"
              >
                {{ personnelProjectTitle }}
              </p>
            </div>

            <Button
              variant="subtle"
              theme="gray"
              @click="closePersonnelDrawer"
            >
              Close
            </Button>
          </div>

          <div class="max-h-[calc(80vh-72px)] space-y-3 overflow-auto p-4 pb-[calc(env(safe-area-inset-bottom)+6rem)]">
            <div
              v-if="personnelLoading"
              class="space-y-2"
            >
              <div class="h-20 rounded-xl bg-surface-gray-2" />
              <div class="h-20 rounded-xl bg-surface-gray-2" />
              <div class="h-20 rounded-xl bg-surface-gray-2" />
            </div>

            <div
              v-else-if="personnelError"
              class="rounded-xl border border-red-200 bg-red-50 px-4 py-3"
            >
              <p class="text-sm font-medium text-red-800">
                Could not load project personnel.
              </p>

              <p class="mt-1 text-sm text-red-700">
                {{ personnelError }}
              </p>
            </div>

            <div
              v-else-if="personnelRows.length === 0"
              class="rounded-xl border border-dashed border-outline-gray-2 bg-surface-gray-1 px-4 py-6 text-center"
            >
              <p class="text-sm font-medium text-ink-gray-7">
                No personnel found.
              </p>

              <p class="mt-1 text-sm text-ink-gray-5">
                No submitted shift allocations were found for this project.
              </p>
            </div>

            <div
              v-else
              class="space-y-2"
            >
              <div
                v-for="person in personnelRows"
                :key="person.employee || person.employee_name || person.user_id"
                class="rounded-xl border border-outline-gray-1 bg-surface-white p-3 shadow-sm"
              >
                <div class="flex items-start gap-3">
                  <div class="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-full bg-surface-gray-2">
                    <img
                      v-if="person.image"
                      :src="person.image"
                      :alt="person.employee_name || 'Personnel'"
                      class="h-full w-full object-cover"
                      @error="hideBrokenImage"
                    >

                    <span
                      v-else
                      class="text-sm font-semibold text-ink-gray-7"
                    >
                      {{ getPersonnelInitials(person) }}
                    </span>
                  </div>

                  <div class="min-w-0 flex-1">
                    <div class="flex items-start justify-between gap-2">
                      <div class="min-w-0">
                        <p class="truncate text-sm font-semibold text-ink-gray-9">
                          {{ person.employee_name || person.employee || 'Unknown personnel' }}
                        </p>

                        <p
                          v-if="getPersonnelSubtitle(person)"
                          class="mt-0.5 truncate text-xs text-ink-gray-5"
                        >
                          {{ getPersonnelSubtitle(person) }}
                        </p>
                      </div>

                      <span
                        v-if="getPersonnelShiftLabel(person)"
                        :class="getPersonnelShiftBadgeClass(person)"
                      >
                        {{ getPersonnelShiftLabel(person) }}
                      </span>
                    </div>

                    <p
                      v-if="formatPersonnelDateRange(person)"
                      class="mt-2 text-xs text-ink-gray-5"
                    >
                      {{ formatPersonnelDateRange(person) }}
                    </p>

                    <div
                      v-if="person.contact_number || person.email"
                      class="mt-3 grid grid-cols-1 gap-2"
                    >
                      <a
                        v-if="person.contact_number"
                        :href="`tel:${normaliseTel(person.contact_number)}`"
                        class="block rounded-lg border border-outline-gray-1 bg-surface-gray-1 px-3 py-2 text-sm font-medium text-ink-gray-8"
                      >
                        Call {{ person.contact_number }}
                      </a>

                      <a
                        v-if="person.email"
                        :href="`mailto:${person.email}`"
                        class="block rounded-lg border border-outline-gray-1 bg-surface-gray-1 px-3 py-2 text-sm font-medium text-ink-gray-8"
                      >
                        {{ person.email }}
                      </a>
                    </div>

                    <p
                      v-else
                      class="mt-3 text-xs text-ink-gray-5"
                    >
                      No contact details available.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div
              class="h-24 shrink-0"
              aria-hidden="true"
            />
          </div>
        </Card>
      </div>
    </Transition>
  </section>
</template>

<script setup lang="ts">
// VERTO_HOME_ACTION_BUTTONS_V1
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Badge,
  Button,
  Card,
} from 'frappe-ui'
import { apiRequest } from '../lib/api'
import { openAppBrowser } from '../lib/appBrowser'

type HomeButton = {
  label: string
  doctype: string
  mobile_doctype: string
}

type TaskItem = Record<string, any>

type ProjectDetails = {
  name?: string
  project_name?: string
  title?: string
  status?: string
  gameplan_team_name?: string
  gameplan_project?: string
  raven_channel?: string
  raven_channel_id?: string
  channel_id?: string
  raven_workspace?: string
  roster_or_shutdown?: string
  customer?: string
  customer_name?: string
  client?: string
  client_name?: string
  customer_image?: string
  image?: string
  [key: string]: any
}

type ParentGroup = {
  parent_task_name: string
  parent_task: string
  progress: number
  project: string
  project_details: ProjectDetails
  tasks: TaskItem[]
}

type ScopeGroup = {
  scope_name: string
  project: string
  project_details: ProjectDetails
  parent_groups: ParentGroup[]
  customer?: string
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

type PeriChannelResponse = {
  channel?: string | Record<string, any>
  name?: string
  channel_id?: string
  channel_name?: string
  message?: string | Record<string, any>
}

type ProjectHandoverResponse = {
  doctype: string
  mobile_doctype: string
  name: string
  route?: string
  created?: boolean
  requested_doctype?: string
  handover_base?: string
}

type ProjectPersonnelItem = {
  employee?: string
  employee_name?: string
  user_id?: string
  email?: string
  contact_number?: string
  image?: string
  designation?: string
  department?: string
  shift_type?: string
  shift_label?: string
  shift_kind?: 'day' | 'night' | 'mixed' | ''
  start_date?: string
  end_date?: string
}

type ProjectPersonnelResponse = {
  personnel: ProjectPersonnelItem[]
  project?: string
  project_name?: string
  matched_shift_count?: number
}

const router = useRouter()

const loading = ref(true)
const error = ref('')
const home = ref<HomePayload | null>(null)

const openScopes = ref<Record<string, boolean>>({})
const openParents = ref<Record<string, boolean>>({})

const pickerOpen = ref(false)
const pickerType = ref<'generic' | 'form' | 'ccv'>('generic')
const pickerTask = ref<TaskItem | null>(null)

const personnelOpen = ref(false)
const personnelLoading = ref(false)
const personnelError = ref('')
const personnelProjectTitle = ref('')
const personnelRows = ref<ProjectPersonnelItem[]>([])

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

function slugifyRavenChannelName(value?: string) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/&/g, ' and ')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function getProjectDisplayName(scope: ScopeGroup) {
  const project = scope.project_details || {}

  return (
    project.project_name ||
    project.title ||
    project.name ||
    scope.project ||
    scope.scope_name ||
    ''
  )
}

function getProjectCustomer(scope: ScopeGroup) {
  const project = scope.project_details || {}

  return (
    project.customer ||
    project.customer_name ||
    project.client ||
    project.client_name ||
    scope.customer ||
    ''
  )
}

function getCustomerImage(scope: ScopeGroup) {
  const project = scope.project_details || {}

  return (
    project.customer_image ||
    project.image ||
    ''
  )
}

function getCustomerInitials(scope: ScopeGroup) {
  const customer = getProjectCustomer(scope) || getProjectDisplayName(scope)

  const words = String(customer)
    .trim()
    .split(/\s+/)
    .filter(Boolean)

  if (!words.length) {
    return '?'
  }

  if (words.length === 1) {
    return words[0].slice(0, 2).toUpperCase()
  }

  return `${words[0][0]}${words[1][0]}`.toUpperCase()
}

function hideBrokenImage(event: Event) {
  const image = event.target as HTMLImageElement
  image.style.display = 'none'
}


function isUsableUrl(url?: string) {
  const value = String(url || '').trim()

  return Boolean(value) && value !== '#'
}

function openInternalUrl(url?: string, label = 'link') {
  const value = String(url || '').trim()

  if (!isUsableUrl(value)) {
    error.value = `Could not open ${label}. The URL is not configured for this project.`
    return
  }

  openAppBrowser({
    url: value,
    title: label,
  })
}

function openExternalUrl(url?: string, label = 'link') {
  const value = String(url || '').trim()

  if (!isUsableUrl(value)) {
    error.value = `Could not open ${label}. The URL is not configured for this project.`
    return
  }

  openAppBrowser({
    url: value,
    title: label,
  })
}

function getProjectChatChannel(scope: ScopeGroup) {
  const project = scope.project_details || {}

  return (
    project.raven_channel ||
    project.raven_channel_id ||
    project.channel_id ||
    slugifyRavenChannelName(getProjectDisplayName(scope))
  )
}

async function openProjectChat(scope: ScopeGroup) {
  const channel = getProjectChatChannel(scope)

  if (!channel) {
    error.value = 'Could not determine the Raven channel for this project.'
    return
  }

  await router.push({
    path: '/chat',
    query: {
      channel,
    },
  })
}

function getPeriChannelIdFromResponse(value: any) {
  const channel = value?.channel || value?.message || value

  if (typeof channel === 'string') {
    return channel
  }

  return (
    channel?.name ||
    channel?.channel_id ||
    value?.name ||
    value?.channel_id ||
    ''
  )
}

async function getOrCreatePeriChannelId() {
  const data = await apiRequest<FrappeResponse<PeriChannelResponse>>(
    '/api/method/verto.api.mobile.raven.get_or_create_peri_channel'
  )

  const channelId = getPeriChannelIdFromResponse(data.message)

  if (!channelId) {
    throw new Error('Could not determine the Ask PERI channel.')
  }

  return channelId
}

// Analyse with PERI: resolve the dedicated user <-> PERI DM channel before routing.
async function analyseProjectWithPeri(scope: ScopeGroup) {
  const projectName =
    scope.scope_name ||
    scope.project_details?.project_name ||
    scope.project_details?.title ||
    scope.project_details?.project_title ||
    scope.project_details?.subject ||
    scope.project ||
    ''

  if (!projectName) {
    error.value = 'Could not determine the project name for PERI analysis.'
    return
  }

  try {
    const channel = await getOrCreatePeriChannelId()

    sessionStorage.setItem(
      'verto_peri_autosend_message',
      `Analyse the dashboard for ${projectName}`
    )

    sessionStorage.setItem('verto_peri_source_project', projectName)

    await router.push({
      path: '/chat/peri',
      query: {
        channel,
        mode: 'ai',
        auto: 'analyse',
      },
    })
  } catch (err) {
    error.value = err instanceof Error
      ? err.message
      : 'Could not open Ask PERI.'
  }
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

function getConfiguredHandoverBase() {
  return String(home.value?.handover_base || '').trim()
}

function inferHandoverDoctypeFromBase(base?: string) {
  const value = String(base || '').trim().toLowerCase()

  if (!value) {
    return ''
  }

  if (value.includes('lead-safety-handover') || value.includes('lead_safety_handover')) {
    return 'Lead Safety Handover'
  }

  if (value.includes('safety-handover') || value.includes('safety_handover')) {
    return 'Safety Handover'
  }

  if (value.includes('project-handover') || value.includes('project_handover')) {
    return 'Project Handover'
  }

  if (value.includes('handover')) {
    return 'Handover'
  }

  return ''
}

function getProjectIdForHandover(scope: ScopeGroup) {
  const project = scope.project_details || {}

  return (
    scope.project ||
    project.name ||
    project.project ||
    project.project_name ||
    scope.scope_name ||
    ''
  )
}

async function openProjectHandover(scope: ScopeGroup) {
  const project = getProjectIdForHandover(scope)
  const projectName = getProjectDisplayName(scope) || scope.scope_name || project
  const handoverBase = getConfiguredHandoverBase()
  const handoverDoctype = inferHandoverDoctypeFromBase(handoverBase)

  if (!project && !projectName) {
    error.value = 'Could not determine the project for this handover.'
    return
  }

  try {
    const payload = new FormData()

    if (project) {
      payload.append('project', project)
    }

    if (projectName) {
      payload.append('project_name', projectName)
    }

    if (scope.scope_name) {
      payload.append('scope_name', scope.scope_name)
    }

    if (handoverBase) {
      payload.append('handover_base', handoverBase)
    }

    if (handoverDoctype) {
      payload.append('handover_doctype', handoverDoctype)
    }

    const data = await apiRequest<FrappeResponse<ProjectHandoverResponse>>(
      '/api/method/verto.api.mobile.handover.get_or_create_project_handover',
      {
        method: 'POST',
        body: payload,
      }
    )

    const handover = data.message

    if (!handover?.mobile_doctype || !handover?.name) {
      throw new Error('Could not resolve the project handover record.')
    }

    if (handover.route) {
      await router.push(handover.route)
      return
    }

    await router.push({
      path: `/edit/${encodeURIComponent(handover.mobile_doctype)}/${encodeURIComponent(handover.name)}`,
    })
  } catch (err) {
    if (err instanceof Error && err.message === 'Login required') {
      return
    }

    error.value = err instanceof Error
      ? err.message
      : 'Could not open the project handover.'
  }
}

function getProjectIdForPersonnel(scope: ScopeGroup) {
  const project = scope.project_details || {}

  return (
    scope.project ||
    project.name ||
    project.project ||
    project.project_name ||
    scope.scope_name ||
    ''
  )
}

function closePersonnelDrawer() {
  personnelOpen.value = false
  personnelRows.value = []
  personnelError.value = ''
  personnelProjectTitle.value = ''
}

async function openPersonnelDrawer(scope: ScopeGroup) {
  const project = getProjectIdForPersonnel(scope)
  const projectName = getProjectDisplayName(scope) || scope.scope_name || project

  if (!project && !projectName) {
    error.value = 'Could not determine the project for personnel.'
    return
  }

  personnelOpen.value = true
  personnelLoading.value = true
  personnelError.value = ''
  personnelRows.value = []
  personnelProjectTitle.value = projectName || 'Project'

  try {
    const payload = new FormData()

    if (project) {
      payload.append('project', project)
    }

    if (projectName) {
      payload.append('project_name', projectName)
    }

    if (scope.scope_name) {
      payload.append('scope_name', scope.scope_name)
    }

    const data = await apiRequest<FrappeResponse<ProjectPersonnelResponse>>(
      '/api/method/verto.api.mobile.project_personnel.get_project_personnel',
      {
        method: 'POST',
        body: payload,
      }
    )

    personnelRows.value = data.message?.personnel || []
  } catch (err) {
    if (err instanceof Error && err.message === 'Login required') {
      return
    }

    personnelError.value = err instanceof Error
      ? err.message
      : 'Could not load project personnel.'
  } finally {
    personnelLoading.value = false
  }
}

function getPersonnelInitials(person: ProjectPersonnelItem) {
  const value = person.employee_name || person.employee || person.email || '?'

  const words = String(value)
    .trim()
    .split(/\s+/)
    .filter(Boolean)

  if (!words.length) {
    return '?'
  }

  if (words.length === 1) {
    return words[0].slice(0, 2).toUpperCase()
  }

  return `${words[0][0]}${words[1][0]}`.toUpperCase()
}

function getPersonnelShiftLabel(person: ProjectPersonnelItem) {
  return person.shift_label || normalisePersonnelShiftLabel(person.shift_type)
}

function normalisePersonnelShiftLabel(value?: string) {
  const cleaned = String(value || '').trim()

  if (!cleaned) {
    return ''
  }

  const normalised = cleaned
    .toUpperCase()
    .replace(/^(FG|RH)[\s_-]*/i, '')
    .replace(/[^A-Z0-9]+/g, ' ')
    .trim()

  const tokens = normalised.split(/\s+/).filter(Boolean)

  if (
    tokens.includes('DS') ||
    tokens.includes('D') ||
    normalised.includes('DAY')
  ) {
    return 'Day Shift'
  }

  if (
    tokens.includes('NS') ||
    tokens.includes('N') ||
    normalised.includes('NIGHT')
  ) {
    return 'Night Shift'
  }

  return cleaned
}

function getPersonnelShiftKind(person: ProjectPersonnelItem) {
  if (person.shift_kind) {
    return person.shift_kind
  }

  const label = getPersonnelShiftLabel(person).toLowerCase()

  if (label.includes('day')) {
    return 'day'
  }

  if (label.includes('night')) {
    return 'night'
  }

  return ''
}

function getPersonnelShiftBadgeClass(person: ProjectPersonnelItem) {
  const shiftKind = getPersonnelShiftKind(person)

  const baseClass = 'shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold'

  if (shiftKind === 'day') {
    return `${baseClass} bg-green-100 text-green-800`
  }

  if (shiftKind === 'night') {
    return `${baseClass} bg-blue-100 text-blue-800`
  }

  if (shiftKind === 'mixed') {
    return `${baseClass} bg-purple-100 text-purple-800`
  }

  return `${baseClass} bg-surface-gray-2 text-ink-gray-7`
}

function getPersonnelSubtitle(person: ProjectPersonnelItem) {
  return [
    person.designation,
    person.department,
  ]
    .filter(Boolean)
    .join(' · ')
}

function formatPersonnelDateRange(person: ProjectPersonnelItem) {
  const startDate = formatDate(person.start_date)
  const endDate = formatDate(person.end_date)

  if (startDate && endDate) {
    return `${startDate} - ${endDate}`
  }

  return startDate || endDate || ''
}

function normaliseTel(value?: string) {
  return String(value || '').replace(/[^+0-9]/g, '')
}

function getGameplanUrl(scope: ScopeGroup) {
  const project = scope.project_details || {}
  const team = project.gameplan_team_name || ''
  const gameplanProject = project.gameplan_project || ''

  return `/g/${team}/projects/${gameplanProject}`
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

<style scoped>
.drawer-fade-slide-enter-active,
.drawer-fade-slide-leave-active {
  transition: opacity 0.18s ease;
}

.drawer-fade-slide-enter-active :deep(.drawer-panel),
.drawer-fade-slide-leave-active :deep(.drawer-panel) {
  transition: transform 0.24s ease, opacity 0.24s ease;
}

.drawer-fade-slide-enter-from,
.drawer-fade-slide-leave-to {
  opacity: 0;
}

.drawer-fade-slide-enter-from :deep(.drawer-panel),
.drawer-fade-slide-leave-to :deep(.drawer-panel) {
  opacity: 0;
  transform: translateY(100%);
}

.drawer-fade-slide-enter-to :deep(.drawer-panel),
.drawer-fade-slide-leave-from :deep(.drawer-panel) {
  opacity: 1;
  transform: translateY(0);
}

@media (prefers-reduced-motion: reduce) {
  .drawer-fade-slide-enter-active,
  .drawer-fade-slide-leave-active,
  .drawer-fade-slide-enter-active :deep(.drawer-panel),
  .drawer-fade-slide-leave-active :deep(.drawer-panel) {
    transition: none;
  }
}
</style>
