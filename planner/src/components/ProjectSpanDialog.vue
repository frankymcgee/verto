<template>
  <Dialog v-model="isOpen" :options="{ title: dialogTitle, size: '2xl' }">
    <template #body-content>
      <div class="space-y-6">
        <div v-if="projectDetails.loading" class="rounded-lg border border-gray-200 bg-gray-50 px-4 py-6 text-sm text-gray-600">
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
          </div>

          <div
            v-if="missingEditableFieldMessage"
            class="rounded-lg border border-yellow-200 bg-yellow-50 px-3 py-2 text-xs text-yellow-800"
          >
            {{ missingEditableFieldMessage }}
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
    </template>

    <template #actions>
      <div class="flex justify-end gap-3">
        <Button size="md" label="Cancel" class="w-28" @click="closeDialog" />
        <Button
          size="md"
          variant="solid"
          class="w-28"
          :disabled="projectDetails.loading || updateProject.loading || !form.project"
          @click="updateProject.submit()"
        >
          Update
        </Button>
      </div>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { Button, Dialog, FormControl, createResource } from 'frappe-ui'
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
  task_count?: number | string | null
  has_tasks?: boolean | number | string | null
  can_update_po?: boolean
  can_update_ds?: boolean
  can_update_ns?: boolean
  can_update_is_active?: boolean
  can_update_project_dates?: boolean
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
  task_count: 0,
  has_tasks: false,
  can_update_po: false,
  can_update_ds: false,
  can_update_ns: false,
  can_update_is_active: false,
  can_update_project_dates: false,
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

const dsPersonnel = computed(() => normalisePersonnel(props.project?.ds_personnel))
const nsPersonnel = computed(() => normalisePersonnel(props.project?.ns_personnel))

const missingEditableFieldMessage = computed(() => {
  const missing: string[] = []
  if (!form.can_update_po) missing.push('PO Number')
  if (!form.can_update_ds) missing.push('DS Personnel Required')
  if (!form.can_update_ns) missing.push('NS Personnel Required')
  if (!form.can_update_is_active) missing.push('Active')

  if (!missing.length) return ''
  return `Some fields cannot be edited because the matching Project fields were not found: ${missing.join(', ')}.`
})

function normalisePersonnel(value?: string[] | null) {
  return Array.isArray(value) ? value.filter(Boolean).sort() : []
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
  form.task_count = 0
  form.has_tasks = false
  form.can_update_po = false
  form.can_update_ds = false
  form.can_update_ns = false
  form.can_update_is_active = false
  form.can_update_project_dates = false
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
  form.task_count = intValue(data.task_count)
  form.has_tasks = boolValue(data.has_tasks)
  form.can_update_po = Boolean(data.can_update_po)
  form.can_update_ds = Boolean(data.can_update_ds)
  form.can_update_ns = Boolean(data.can_update_ns)
  form.can_update_is_active = Boolean(data.can_update_is_active)
  form.can_update_project_dates = Boolean(data.can_update_project_dates)
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
