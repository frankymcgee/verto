<template>
  <Teleport to="body">
    <div
      v-if="isOpen"
      class="fixed inset-0 z-[2147483000] bg-black/50"
      @click.self="closeDialog"
    />

    <div
      v-if="isOpen"
      class="fixed inset-0 z-[2147483001] flex items-start justify-center overflow-y-auto px-4 py-10"
      @click.self="closeDialog"
    >
      <div
        class="w-full max-w-4xl overflow-hidden rounded-lg bg-white shadow-2xl"
        role="dialog"
        aria-modal="true"
        :aria-label="dialogTitle"
        @click.stop
      >
        <div class="flex items-center justify-between border-b border-gray-200 px-6 py-4">
          <h2 class="text-xl font-semibold text-gray-900">{{ dialogTitle }}</h2>
          <button
            type="button"
            class="rounded-md p-1 text-gray-500 transition hover:bg-gray-100 hover:text-gray-900"
            aria-label="Close"
            @click="closeDialog"
          >
            ✕
          </button>
        </div>

        <div class="max-h-[calc(100vh-13rem)] overflow-y-auto px-6 py-5">
          <div class="space-y-6">
            <div
              v-if="projectDetails.loading"
              class="rounded-lg border border-gray-200 bg-gray-50 px-4 py-6 text-sm text-gray-600"
            >
              Loading project details...
            </div>

            <template v-else>
              <div class="grid grid-cols-2 gap-4">
                <FormControl type="text" label="Project" v-model="form.project_name" :disabled="true" />
                <FormControl type="text" label="Project ID" v-model="form.project" :disabled="true" />

                <FormControl type="text" label="Customer" v-model="form.customer" :disabled="true" />
                <FormControl type="text" label="Location" v-model="form.custom_project_location" :disabled="true" />

                <FormControl
                  v-if="isPoCheckField"
                  type="checkbox"
                  label="PO Entered"
                  v-model="form.po_entered"
                  :disabled="!form.can_update_po"
                />
                <FormControl
                  v-else
                  type="text"
                  label="PO Number"
                  placeholder="Enter PO number"
                  v-model="form.po_number"
                  :disabled="!form.can_update_po"
                />

                <FormControl
                  type="checkbox"
                  label="Active"
                  v-model="form.is_active"
                  :disabled="!form.can_update_is_active"
                />

                <FormControl
                  type="number"
                  label="DS Personnel Required"
                  v-model="form.ds_requested"
                  :disabled="!form.can_update_ds"
                />
                <FormControl
                  type="number"
                  label="NS Personnel Required"
                  v-model="form.ns_requested"
                  :disabled="!form.can_update_ns"
                />

                <template v-if="showProjectDateFields">
                  <div
                    class="col-span-2 rounded-lg border px-3 py-2 text-xs"
                    :class="projectDateHelpClass"
                  >
                    {{ projectDateHelpMessage }}
                  </div>

                  <FormControl
                    type="date"
                    label="Project Start Date"
                    v-model="form.project_start_date"
                    :disabled="!form.can_update_project_dates"
                  />
                  <FormControl
                    type="date"
                    label="Project End Date"
                    v-model="form.project_end_date"
                    :disabled="!form.can_update_project_dates"
                  />
                </template>

                <div class="col-span-2">
                  <label class="mb-1.5 block text-sm text-gray-700">
                    Project Notes
                  </label>
                  <textarea
                    v-model="form.project_notes"
                    rows="5"
                    class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 shadow-sm transition focus:border-gray-500 focus:outline-none disabled:bg-gray-50 disabled:text-gray-500"
                    placeholder="Add project notes..."
                    :disabled="!form.can_update_notes"
                  />
                  <p v-if="!form.can_update_notes" class="mt-1 text-xs text-gray-500">
                    Project notes cannot be edited because the matching Project notes field was not found.
                  </p>
                </div>
              </div>

              <div
                v-if="missingEditableFieldMessage"
                class="rounded-lg border border-yellow-200 bg-yellow-50 px-3 py-2 text-xs text-yellow-800"
              >
                {{ missingEditableFieldMessage }}
              </div>

              <div class="rounded-lg border border-gray-200 bg-white">
                <div class="border-b border-gray-100 px-4 py-3">
                  <div class="flex items-start justify-between gap-3">
                    <div>
                      <div class="text-sm font-semibold text-gray-800">Generic Task Structure</div>
                      <div class="mt-0.5 text-xs text-gray-500">
                        {{ genericTaskStatusMessage }}
                      </div>
                    </div>
                    <div
                      class="shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold"
                      :class="form.has_tasks ? 'bg-green-50 text-green-700' : 'bg-yellow-50 text-yellow-700'"
                    >
                      {{ form.has_tasks ? `${form.task_count} task(s)` : 'Gantt missing' }}
                    </div>
                  </div>
                </div>

                <div v-if="!form.has_tasks" class="space-y-4 p-4">
                  <div class="rounded-md border border-blue-100 bg-blue-50 px-3 py-2 text-xs text-blue-800">
                    <div class="font-semibold">{{ form.project_name || form.project }}</div>
                    <div
                      v-for="(location, index) in form.generic_locations"
                      :key="`generic-preview-${location.key}`"
                      :class="index === 0 ? 'mt-1' : 'mt-1.5'"
                    >
                      <div class="pl-3">└─ {{ location.subject || `Location ${index + 1}` }}</div>
                      <div class="pl-6">└─ {{ form.generic_work_summary_subject || 'Execution Works' }}</div>
                    </div>
                  </div>

                  <div class="rounded-md border border-gray-200">
                    <div class="flex items-center justify-between gap-3 border-b border-gray-100 px-3 py-2">
                      <div>
                        <div class="text-xs font-semibold uppercase tracking-wide text-gray-600">Locations</div>
                        <div class="text-xs text-gray-500">Each location receives its own linked Work Summary task.</div>
                      </div>
                      <button
                        type="button"
                        class="rounded-md border border-gray-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-gray-700 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                        :disabled="!canAddGenericLocation"
                        @click="addGenericLocation"
                      >
                        + Add Location
                      </button>
                    </div>

                    <div class="space-y-3 p-3">
                      <div
                        v-for="(location, index) in form.generic_locations"
                        :key="location.key"
                        class="flex items-end gap-2"
                      >
                        <div class="min-w-0 flex-1">
                          <FormControl
                            type="text"
                            :label="`Location ${index + 1}`"
                            :placeholder="index === 0 ? 'General' : `Enter location ${index + 1}`"
                            v-model="location.subject"
                            :disabled="!form.can_create_generic_tasks || createGenericTasks.loading"
                          />
                        </div>
                        <button
                          type="button"
                          class="mb-0.5 rounded-md border border-red-200 bg-white px-2.5 py-2 text-xs font-semibold text-red-600 transition hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-40"
                          :disabled="form.generic_locations.length <= 1 || createGenericTasks.loading"
                          :aria-label="`Remove location ${index + 1}`"
                          @click="removeGenericLocation(index)"
                        >
                          Remove
                        </button>
                      </div>

                      <p v-if="!genericLocationNamesAreUnique" class="text-xs font-medium text-red-600">
                        Each location task must have a unique name.
                      </p>
                    </div>
                  </div>

                  <div class="grid grid-cols-2 gap-4">
                    <FormControl
                      type="text"
                      label="Work Summary Task (each location)"
                      placeholder="Execution Works"
                      v-model="form.generic_work_summary_subject"
                      :disabled="!form.can_create_generic_tasks || createGenericTasks.loading"
                    />
                    <FormControl
                      type="time"
                      label="Expected Start Time"
                      v-model="form.generic_start_time"
                      :disabled="!form.can_create_generic_tasks || createGenericTasks.loading"
                    />
                    <FormControl
                      type="time"
                      label="Expected End Time"
                      v-model="form.generic_end_time"
                      :disabled="!form.can_create_generic_tasks || createGenericTasks.loading"
                    />
                  </div>

                  <div class="flex items-center justify-between gap-3">
                    <p class="text-xs text-gray-500">
                      The project name becomes the top-level Outline task. Existing tasks are never changed.
                    </p>
                    <Button
                      size="sm"
                      variant="solid"
                      class="shrink-0"
                      :disabled="!canSubmitGenericTasks || updateProject.loading"
                      :loading="createGenericTasks.loading"
                      @click="confirmCreateGenericTasks"
                    >
                      Create {{ genericTaskTotalCount }} Generic Tasks
                    </Button>
                  </div>
                </div>
              </div>

              <div class="rounded-lg border border-gray-200 bg-white">
                <div class="border-b border-gray-100 px-4 py-3">
                  <div class="text-sm font-semibold text-gray-800">Personnel Assigned</div>
                  <div class="mt-0.5 text-xs text-gray-500">
                    Current annual view assignments split by DS and NS shift types.
                  </div>
                </div>

                <div class="grid grid-cols-2 divide-x divide-gray-100">
                  <div class="p-4">
                    <div class="mb-2 flex items-center justify-between gap-2">
                      <div class="text-xs font-semibold uppercase tracking-wide text-gray-500">DS</div>
                      <div class="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-semibold text-gray-600">
                        {{ dsPersonnel.length }}
                      </div>
                    </div>

                    <div v-if="dsPersonnel.length" class="space-y-1.5">
                      <div
                        v-for="person in dsPersonnel"
                        :key="`ds-${person}`"
                        class="rounded-md bg-gray-50 px-2.5 py-1.5 text-sm text-gray-700"
                      >
                        {{ person }}
                      </div>
                    </div>
                    <div v-else class="rounded-md bg-gray-50 px-2.5 py-4 text-center text-sm text-gray-500">
                      No DS personnel assigned
                    </div>
                  </div>

                  <div class="p-4">
                    <div class="mb-2 flex items-center justify-between gap-2">
                      <div class="text-xs font-semibold uppercase tracking-wide text-gray-500">NS</div>
                      <div class="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-semibold text-gray-600">
                        {{ nsPersonnel.length }}
                      </div>
                    </div>

                    <div v-if="nsPersonnel.length" class="space-y-1.5">
                      <div
                        v-for="person in nsPersonnel"
                        :key="`ns-${person}`"
                        class="rounded-md bg-gray-50 px-2.5 py-1.5 text-sm text-gray-700"
                      >
                        {{ person }}
                      </div>
                    </div>
                    <div v-else class="rounded-md bg-gray-50 px-2.5 py-4 text-center text-sm text-gray-500">
                      No NS personnel assigned
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </div>
        </div>

        <div class="border-t border-gray-200 bg-gray-50 px-6 py-4">
          <div class="flex justify-end gap-3">
            <Button size="md" label="Cancel" class="w-28" @click="closeDialog" />
            <Button
              size="md"
              variant="solid"
              class="w-28"
              :disabled="projectDetails.loading || updateProject.loading || createGenericTasks.loading || !form.project"
              :loading="updateProject.loading"
              @click="updateProject.submit()"
            >
              Update
            </Button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { Button, FormControl, createResource } from 'frappe-ui'
import { raiseToast } from '../utils'

type ProjectDialogRow = {
  project: string
  project_name?: string
  customer?: string | null
  customer_name?: string | null
  custom_project_location?: string | null
  status?: string | null
  ds_personnel?: string[]
  ns_personnel?: string[]
}

type ProjectDetails = {
  project: string
  project_name?: string
  customer?: string | null
  custom_project_location?: string | null
  status?: string | null
  po_field?: string | null
  po_fieldtype?: string | null
  po_number?: string | null
  po_entered?: boolean | number | string | null
  ds_requested?: number | string | null
  ns_requested?: number | string | null
  is_active?: boolean | number | string | null
  project_start_date?: string | null
  project_end_date?: string | null
  notes_field?: string | null
  notes?: string | null
  task_count?: number | string | null
  has_tasks?: boolean | number | string | null
  can_create_generic_tasks?: boolean
  generic_tasks_unavailable_reason?: string | null
  can_update_po?: boolean
  can_update_ds?: boolean
  can_update_ns?: boolean
  can_update_is_active?: boolean
  can_update_project_dates?: boolean
  can_update_notes?: boolean
}

type GenericTaskResponse = {
  project?: string
  created_tasks?: Array<{
    name: string
    subject?: string
    type?: string | null
    parent_task?: string | null
  }>
  project_details?: ProjectDetails
}

const props = defineProps<{
  modelValue?: boolean
  isDialogOpen: boolean
  project?: ProjectDialogRow | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'fetchEvents'): void
}>()

const isOpen = computed({
  get: () => props.modelValue ?? props.isDialogOpen,
  set: (value: boolean) => emit('update:modelValue', value),
})

type GenericLocationRow = {
  key: number
  subject: string
}

const GENERIC_LOCATION_LIMIT = 100
let nextGenericLocationKey = 1

function newGenericLocation(subject = ''): GenericLocationRow {
  return {
    key: nextGenericLocationKey++,
    subject,
  }
}

const form = reactive({
  project: '',
  project_name: '',
  customer: '',
  custom_project_location: '',
  status: '',
  po_fieldtype: '',
  po_number: '',
  po_entered: false,
  ds_requested: 0,
  ns_requested: 0,
  is_active: true,
  project_start_date: '',
  project_end_date: '',
  project_notes: '',
  task_count: 0,
  has_tasks: false,
  can_create_generic_tasks: false,
  generic_tasks_unavailable_reason: '',
  generic_locations: [newGenericLocation('General')],
  generic_work_summary_subject: 'Execution Works',
  generic_start_time: '08:00',
  generic_end_time: '20:00',
  can_update_po: false,
  can_update_ds: false,
  can_update_ns: false,
  can_update_is_active: false,
  can_update_project_dates: false,
  can_update_notes: false,
})

const dialogTitle = computed(() => {
  const name = form.project_name || props.project?.project_name || props.project?.project || 'Project'
  return `Project Details - ${name}`
})

const isPoCheckField = computed(() => form.po_fieldtype === 'Check')
const showProjectDateFields = computed(() => form.can_update_project_dates || form.has_tasks || Boolean(form.project_start_date || form.project_end_date))
const projectDateHelpClass = computed(() => (form.can_update_project_dates ? 'border-blue-200 bg-blue-50 text-blue-800' : 'border-gray-200 bg-gray-50 text-gray-600'))
const projectDateHelpMessage = computed(() => {
  if (form.can_update_project_dates) {
    return 'Gantt is missing for this project, so the Project Start Date and Project End Date can be adjusted here.'
  }

  if (form.has_tasks) {
    return `Project dates are locked because this project already has ${form.task_count} task(s) assigned in the Gantt.`
  }

  return 'Project dates are not editable because the matching Project date fields were not found.'
})

const genericTaskStatusMessage = computed(() => {
  if (form.has_tasks) {
    return `This project already has ${form.task_count} task(s). The generic task option is no longer required.`
  }

  if (form.generic_tasks_unavailable_reason) return form.generic_tasks_unavailable_reason

  return 'Creates one Outline plus a Location and Work Summary pair for every location entered below.'
})

const genericLocationNames = computed(() => form.generic_locations.map((location) => String(location.subject || '').trim()))
const genericLocationNamesAreUnique = computed(() => {
  const names = genericLocationNames.value.filter(Boolean).map((name) => name.toLowerCase())
  return new Set(names).size === names.length
})
const genericTaskTotalCount = computed(() => 1 + (form.generic_locations.length * 2))
const canAddGenericLocation = computed(() => (
  form.can_create_generic_tasks
  && !createGenericTasks.loading
  && form.generic_locations.length < GENERIC_LOCATION_LIMIT
))

const canSubmitGenericTasks = computed(() => (
  form.can_create_generic_tasks
  && Boolean(form.project)
  && form.generic_locations.length > 0
  && genericLocationNames.value.every(Boolean)
  && genericLocationNamesAreUnique.value
  && Boolean(String(form.generic_work_summary_subject || '').trim())
  && Boolean(form.generic_start_time)
  && Boolean(form.generic_end_time)
))

const dsPersonnel = computed(() => normalisePersonnel(props.project?.ds_personnel))
const nsPersonnel = computed(() => normalisePersonnel(props.project?.ns_personnel))

const missingEditableFieldMessage = computed(() => {
  const missing: string[] = []
  if (!form.can_update_po) missing.push('PO Number')
  if (!form.can_update_ds) missing.push('DS Personnel Required')
  if (!form.can_update_ns) missing.push('NS Personnel Required')
  if (!form.can_update_is_active) missing.push('Active')
  if (!form.can_update_notes) missing.push('Project Notes')

  if (!missing.length) return ''
  return `Some fields cannot be edited because the matching Project fields were not found: ${missing.join(', ')}.`
})

function normalisePersonnel(value?: string[] | null) {
  return Array.isArray(value) ? value.filter(Boolean).sort() : []
}

function addGenericLocation() {
  if (!canAddGenericLocation.value) return
  form.generic_locations.push(newGenericLocation())
}

function removeGenericLocation(index: number) {
  if (form.generic_locations.length <= 1 || createGenericTasks.loading) return
  form.generic_locations.splice(index, 1)
}

function boolValue(value: unknown, fallback = false) {
  if (value === undefined || value === null || value === '') return fallback
  if (typeof value === 'boolean') return value
  if (typeof value === 'number') return value !== 0
  const normalised = String(value).trim().toLowerCase()
  return !['0', 'no', 'false', 'missing', 'not entered', 'none'].includes(normalised)
}

function intValue(value: unknown) {
  const parsed = Number.parseInt(String(value ?? 0), 10)
  return Number.isFinite(parsed) ? parsed : 0
}

function resetForm() {
  form.project = ''
  form.project_name = ''
  form.customer = ''
  form.custom_project_location = ''
  form.status = ''
  form.po_fieldtype = ''
  form.po_number = ''
  form.po_entered = false
  form.ds_requested = 0
  form.ns_requested = 0
  form.is_active = true
  form.project_start_date = ''
  form.project_end_date = ''
  form.project_notes = ''
  form.task_count = 0
  form.has_tasks = false
  form.can_create_generic_tasks = false
  form.generic_tasks_unavailable_reason = ''
  form.generic_locations.splice(0, form.generic_locations.length, newGenericLocation('General'))
  form.generic_work_summary_subject = 'Execution Works'
  form.generic_start_time = '08:00'
  form.generic_end_time = '20:00'
  form.can_update_po = false
  form.can_update_ds = false
  form.can_update_ns = false
  form.can_update_is_active = false
  form.can_update_project_dates = false
  form.can_update_notes = false
}

function applyDetails(data: ProjectDetails | undefined) {
  if (!data) return

  form.project = data.project || ''
  form.project_name = data.project_name || data.project || ''
  form.customer = data.customer || props.project?.customer_name || props.project?.customer || ''
  form.custom_project_location = data.custom_project_location || ''
  form.status = data.status || ''
  form.po_fieldtype = data.po_fieldtype || ''
  form.po_number = data.po_number || ''
  form.po_entered = boolValue(data.po_entered)
  form.ds_requested = intValue(data.ds_requested)
  form.ns_requested = intValue(data.ns_requested)
  form.is_active = boolValue(data.is_active, true)
  form.project_start_date = data.project_start_date || ''
  form.project_end_date = data.project_end_date || ''
  form.project_notes = data.notes || ''
  form.task_count = intValue(data.task_count)
  form.has_tasks = boolValue(data.has_tasks)
  form.can_create_generic_tasks = Boolean(data.can_create_generic_tasks)
  form.generic_tasks_unavailable_reason = data.generic_tasks_unavailable_reason || ''
  form.can_update_po = Boolean(data.can_update_po)
  form.can_update_ds = Boolean(data.can_update_ds)
  form.can_update_ns = Boolean(data.can_update_ns)
  form.can_update_is_active = Boolean(data.can_update_is_active)
  form.can_update_project_dates = Boolean(data.can_update_project_dates)
  form.can_update_notes = Boolean(data.can_update_notes)
}

function closeDialog() {
  isOpen.value = false
}

const projectDetails = createResource({
  url: 'verto.api.planner.get_project_planner_details',
  auto: false,
  makeParams() {
    return {
      project: props.project?.project,
    }
  },
  onSuccess(data: ProjectDetails | undefined) {
    applyDetails(data)
  },
  onError(error: { messages?: string[]; message?: string }) {
    raiseToast('error', error?.messages?.[0] || error?.message || 'Failed to load project details')
  },
})

function confirmCreateGenericTasks() {
  if (!canSubmitGenericTasks.value || createGenericTasks.loading) return

  const locationCount = form.generic_locations.length
  const locationLabel = locationCount === 1 ? 'location' : 'locations'
  const confirmed = window.confirm(
    `Create the generic task hierarchy for ${form.project_name || form.project}?\n\n`
    + `This will create ${genericTaskTotalCount.value} linked Tasks across ${locationCount} ${locationLabel} `
    + 'and lock the Project dates while those Tasks exist.',
  )
  if (confirmed) createGenericTasks.submit()
}

const createGenericTasks = createResource({
  url: 'verto.api.planner.create_generic_project_tasks',
  auto: false,
  makeParams() {
    return {
      project: form.project,
      locations: genericLocationNames.value,
      work_summary_subject: form.generic_work_summary_subject,
      expected_start_time: form.generic_start_time,
      expected_end_time: form.generic_end_time,
    }
  },
  onSuccess(data: GenericTaskResponse | undefined) {
    applyDetails(data?.project_details)
    const createdCount = data?.created_tasks?.length || genericTaskTotalCount.value
    raiseToast('success', `Created ${createdCount} linked generic tasks for ${form.project_name || form.project}.`)
    emit('fetchEvents')
  },
  onError(error: { messages?: string[]; message?: string }) {
    raiseToast('error', error?.messages?.[0] || error?.message || 'Failed to create generic tasks')
    projectDetails.fetch()
  },
})

const updateProject = createResource({
  url: 'verto.api.planner.update_project_planner_details',
  auto: false,
  makeParams() {
    return {
      project: form.project,
      po_number: form.po_number,
      po_entered: form.po_entered ? 1 : 0,
      ds_requested: form.ds_requested,
      ns_requested: form.ns_requested,
      is_active: form.is_active ? 1 : 0,
      project_start_date: form.project_start_date,
      project_end_date: form.project_end_date,
      project_notes: form.project_notes,
    }
  },
  onSuccess(data: ProjectDetails | undefined) {
    applyDetails(data)
    raiseToast('success', 'Project updated successfully!')
    emit('fetchEvents')
  },
  onError(error: { messages?: string[]; message?: string }) {
    raiseToast('error', error?.messages?.[0] || error?.message || 'Failed to update project')
  },
})

watch(
  () => [props.isDialogOpen, props.project?.project],
  ([open]) => {
    if (!open) return
    resetForm()
    if (props.project?.project) projectDetails.fetch()
  },
  { immediate: true },
)
</script>
