<template>
  <Dialog :open="dialogOpen" :title="dialogTitle" size="5xl" @update:open="(open) => { if (!open) closeDialog() }">
    <div class="planner-leave-dialog-body max-h-[calc(100vh-13rem)] overflow-y-auto px-6 py-5">
      <div v-if="loading" class="py-8 text-center text-sm text-gray-500">Loading Leave Application...</div>
      <div v-else-if="loadError" class="space-y-3" role="alert">
        <p class="text-sm text-red-700">{{ loadError }}</p>
        <Button @click="loadForm">Retry</Button>
      </div>
      <div v-else-if="metadata" class="space-y-5">
        <div v-if="isEditing" class="flex flex-wrap items-center justify-between gap-3 rounded-5 border bg-gray-50 px-4 py-3">
          <div>
            <div class="text-sm-semibold">{{ metadata.name }}</div>
            <div class="text-xs text-gray-600">{{ metadata.status }} · {{ documentState }}</div>
          </div>
          <Button variant="subtle" :disabled="busy" @click="loadForm">{{ isDirty ? 'Discard edits and reload' : 'Reload' }}</Button>
        </div>
        <p v-if="isEditing && metadata.docstatus === 2" class="text-sm text-gray-600">This application is cancelled and cannot be edited.</p>
        <p v-else-if="isEditing && !metadata.can_write" class="text-sm text-gray-600">You can view this application. Available actions are shown below.</p>
        <p v-else-if="isEditing && metadata.docstatus === 1" class="text-sm text-gray-600">This application is submitted. Only fields permitted after submission can be edited.</p>
        <p v-else-if="!isEditing && !canSubmit" class="text-sm text-gray-600">Your request will be saved as Open for approval.</p>
        <div v-if="writeError" class="rounded-5 border border-red-200 bg-red-50 p-3 text-sm text-red-700" role="alert">{{ writeError }}</div>
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <template v-for="field in visibleFields" :key="field.key">
            <div v-if="isSectionField(field)" class="col-span-full mt-2 border-b pb-2 text-sm-semibold text-gray-700">{{ field.label || 'Details' }}</div>
            <div v-else-if="field.fieldtype !== 'Column Break' && !field.unsupported" :class="isTextareaField(field) ? 'col-span-full' : 'col-span-1'">
              <label class="mb-1 block text-xs-medium text-gray-600">{{ field.label || field.fieldname }} <span v-if="isRequired(field)" class="text-red-500">*</span></label>
              <Checkbox v-if="field.fieldtype === 'Check'" v-model="form[field.fieldname]" :aria-label="field.label || field.fieldname" :disabled="fieldDisabled(field)" />
              <Select v-else-if="field.fieldtype === 'Select'" v-model="form[field.fieldname]" :aria-label="field.label || field.fieldname" :options="selectOptions(field)" :disabled="fieldDisabled(field)" />
              <Combobox v-else-if="isLinkField(field)" :model-value="form[field.fieldname] || ''" :aria-label="field.label || field.fieldname"
                :options="linkOptions[field.fieldname] || []" :loading="linkLoading[field.fieldname]" :filterable="false"
                :disabled="fieldDisabled(field) || !resolveLinkDoctype(field)" :placeholder="`Search ${resolveLinkDoctype(field)}`"
                @update:model-value="(value) => { form[field.fieldname] = value || '' }"
                @update:query="(query) => searchLinks(field, query)"
                @update:open="(open) => { if (open) fetchLinkOptions(field, '') }" />
              <Textarea v-else-if="isTextareaField(field)" v-model="form[field.fieldname]" :aria-label="field.label || field.fieldname" :rows="field.fieldtype === 'Text Editor' ? 6 : 3" :disabled="fieldDisabled(field)" />
              <TextInput v-else v-model="form[field.fieldname]" :aria-label="field.label || field.fieldname" :type="inputType(field)" :disabled="fieldDisabled(field)" />
              <p v-if="field.description" class="mt-1 text-xs text-gray-500">{{ field.description }}</p>
            </div>
          </template>
        </div>
      </div>
    </div>
    <template #actions>
      <div class="rounded-b-6 border-t bg-gray-50 px-6 py-4">
        <div v-if="confirmation" class="mb-3 space-y-2" role="alert">
          <p class="text-sm">{{ confirmation.action === 'cancel' ? 'Cancel this Leave Application?' : `Apply ${confirmation.label} to this Leave Application?` }}</p>
          <div class="flex justify-end gap-2">
            <Button :disabled="busy" @click="confirmation = null">Go back</Button>
            <Button variant="solid" :loading="updateLeave.loading" @click="confirmAction">Confirm {{ confirmation.label }}</Button>
          </div>
        </div>
        <div v-else class="flex flex-wrap items-center justify-end gap-2">
          <Button variant="subtle" :disabled="saving" @click="closeDialog">Close</Button>
          <template v-if="metadata && !loading && !loadError">
            <Button v-if="isEditing && metadata.can_cancel" :disabled="busy" @click="confirmation = { action: 'cancel', label: 'Cancellation' }">Cancel Leave Application</Button>
            <Button v-for="action in metadata.workflow_actions || []" :key="action" :disabled="busy" @click="confirmation = { action: 'workflow', label: action }">{{ action }}</Button>
            <Button v-if="isEditing && metadata.can_write" variant="solid" :loading="updateLeave.loading" :disabled="busy || !isDirty" @click="submitLeave('save')">Save Changes</Button>
            <Button v-if="isEditing && canSubmit && ['Approved', 'Rejected'].includes(form.status)" variant="solid" :disabled="busy" @click="confirmation = { action: 'submit', label: 'Submission' }">Submit</Button>
            <Button v-if="!isEditing" variant="solid" :loading="createLeave.loading" :disabled="busy" @click="submitLeave('save')">Create Leave Application</Button>
          </template>
        </div>
      </div>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { Button, Checkbox, Combobox, Select, TextInput, Textarea, createResource } from 'frappe-ui'
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import Dialog from './PlannerDialog.vue'
import { dayjs, raiseToast } from '../utils'

type LeaveField = {
  key?: string; fieldname: string; fieldtype: string; label?: string; options?: string;
  reqd?: number | boolean; default?: string | number | null; depends_on?: string;
  read_only?: number | boolean; read_only_depends_on?: string; mandatory_depends_on?: string;
  description?: string; unsupported?: boolean;
}
type LeaveDetails = {
  fields: LeaveField[]; name?: string; modified?: string; docstatus?: number; status?: string;
  values?: Record<string, any>; can_write?: boolean; can_submit?: boolean; can_cancel?: boolean;
  workflow_actions?: string[];
}
type LinkOption = { value: string; label?: string; description?: string }
type Action = 'save' | 'submit' | 'cancel' | 'workflow'
const props = defineProps<{ modelValue?: boolean; isDialogOpen: boolean; company?: string; leaveApplicationName?: string }>()
const emit = defineEmits<{ (event: 'update:modelValue', value: boolean): void; (event: 'fetchEvents'): void }>()
const dialogOpen = computed(() => props.modelValue ?? props.isDialogOpen)
const isEditing = computed(() => Boolean(props.leaveApplicationName))
const dialogTitle = computed(() => isEditing.value ? 'Leave Application' : 'Create Leave Application')
const metadata = ref<LeaveDetails | null>(null)
const form = reactive<Record<string, any>>({})
const original = ref<Record<string, any>>({})
const loading = ref(false)
const loadError = ref('')
const writeError = ref('')
const confirmation = ref<{ action: Action; label: string } | null>(null)
const linkOptions = reactive<Record<string, LinkOption[]>>({})
const linkLoading = reactive<Record<string, boolean>>({})
const linkTimers: Record<string, ReturnType<typeof setTimeout>> = {}
const linkVersions: Record<string, number> = {}
let loadVersion = 0
const canSubmit = computed(() => Boolean(metadata.value?.can_submit))
const documentState = computed(() => ['Draft', 'Submitted', 'Cancelled'][metadata.value?.docstatus || 0])
const fields = computed(() => (metadata.value?.fields || []).map((field, index) => ({ ...field, key: field.fieldname || `${field.fieldtype}-${index}` })))
const visibleFields = computed(() => fields.value.filter(field => condition(field.depends_on, true)))
const leaveMeta = createResource({ url: 'verto.api.planner.get_leave_application_create_meta', auto: false })
const leaveDetails = createResource({ url: 'verto.api.planner_leave.get_details', auto: false })
const linkSearch = createResource({ url: 'verto.api.planner.search_leave_application_link_options', auto: false })
const saving = computed(() => createLeave.loading || updateLeave.loading)
const busy = computed(() => loading.value || saving.value)
const isDirty = computed(() => Object.keys(buildSubmitValues()).length > 0)

function errorMessage(error: any) {
  return error?.messages?.[0] || error?.message || 'Unable to save the Leave Application.'
}
function saved(message: string) {
  raiseToast('success', message)
  emit('fetchEvents')
  emit('update:modelValue', false)
}
const createLeave = createResource({
  url: 'verto.api.planner.create_planner_leave_application', auto: false,
  onSuccess() { saved('Leave Application created.') },
  onError(error: any) { writeError.value = errorMessage(error) },
})
const updateLeave = createResource({
  url: 'verto.api.planner_leave.update', auto: false,
  onSuccess() { saved('Leave Application updated.') },
  onError(error: any) { writeError.value = errorMessage(error); confirmation.value = null },
})

function clearSearchTimers() {
  Object.values(linkTimers).forEach(clearTimeout)
  Object.keys(linkTimers).forEach(key => delete linkTimers[key])
}
async function loadForm() {
  const version = ++loadVersion
  clearSearchTimers()
  loading.value = true
  loadError.value = ''
  writeError.value = ''
  confirmation.value = null
  metadata.value = null
  Object.keys(form).forEach(key => delete form[key])
  Object.keys(linkOptions).forEach(key => delete linkOptions[key])
  Object.keys(linkLoading).forEach(key => delete linkLoading[key])
  try {
    const data: LeaveDetails = isEditing.value
      ? await leaveDetails.fetch({ name: props.leaveApplicationName }) : await leaveMeta.fetch()
    if (version !== loadVersion || !dialogOpen.value) return
    metadata.value = data
    for (const field of data.fields || []) {
      if (!field.fieldname || isLayout(field) || field.unsupported) continue
      let value = isEditing.value ? data.values?.[field.fieldname] : defaultValue(field)
      if (field.fieldtype === 'Check') value = ['1', 1, true, 'true', 'Yes'].includes(value)
      if (field.fieldtype === 'Datetime' && value) value = String(value).replace(' ', 'T').slice(0, 16)
      form[field.fieldname] = value ?? ''
      if (isLinkField(field) && value) linkOptions[field.fieldname] = [{ value: String(value), label: String(value) }]
    }
    form.name = data.name || ''
    form.docstatus = data.docstatus || 0
    form.__islocal = !isEditing.value
    if (!isEditing.value) {
      for (const key of ['from_date', 'to_date', 'posting_date']) {
        if (key in form && !form[key]) form[key] = dayjs().format('YYYY-MM-DD')
      }
      if ('status' in form) form.status = canSubmit.value ? 'Approved' : 'Open'
    }
    original.value = { ...form }
  } catch (error: any) {
    if (version === loadVersion) loadError.value = errorMessage(error)
  } finally {
    if (version === loadVersion) loading.value = false
  }
}
watch(() => [dialogOpen.value, props.leaveApplicationName], ([open]) => {
  if (open) void loadForm()
  else { ++loadVersion; clearSearchTimers(); confirmation.value = null }
}, { immediate: true })
onBeforeUnmount(() => { ++loadVersion; clearSearchTimers() })

function defaultValue(field: LeaveField) {
  const value = field.default
  if (field.fieldtype === 'Date' && String(value).toLowerCase() === 'today') return dayjs().format('YYYY-MM-DD')
  if (field.fieldtype === 'Datetime' && String(value).toLowerCase() === 'now') return dayjs().format('YYYY-MM-DDTHH:mm')
  if (value !== undefined && value !== null && value !== '') return value
  if (field.fieldtype === 'Select' && field.reqd) return selectOptions(field).find(option => option.value)?.value || ''
  return ''
}
function fieldReadOnly(field: LeaveField) {
  return Boolean(field.read_only || condition(field.read_only_depends_on, false))
}
function fieldDisabled(field: LeaveField) { return busy.value || fieldReadOnly(field) }
function isRequired(field: LeaveField) { return Boolean(field.reqd || condition(field.mandatory_depends_on, false)) }
function buildSubmitValues() {
  const values: Record<string, any> = {}
  for (const field of fields.value) {
    if (!field.fieldname || isLayout(field) || field.unsupported || fieldReadOnly(field) || !condition(field.depends_on, true)) continue
    const value = form[field.fieldname]
    if (isEditing.value) {
      if (String(value ?? '') !== String(original.value[field.fieldname] ?? '')) values[field.fieldname] = value ?? ''
    } else if (value !== undefined && value !== null && value !== '') values[field.fieldname] = value
  }
  return values
}
function validForm() {
  const missing = visibleFields.value.find(field => !isLayout(field) && !field.unsupported && !fieldReadOnly(field)
    && isRequired(field) && (form[field.fieldname] === '' || form[field.fieldname] == null))
  if (missing) { writeError.value = `${missing.label || missing.fieldname} is required.`; return false }
  if (form.from_date && form.to_date && dayjs(form.to_date).isBefore(dayjs(form.from_date), 'day')) {
    writeError.value = 'To Date cannot be before From Date.'; return false
  }
  if (form.half_day && form.half_day_date && (dayjs(form.half_day_date).isBefore(dayjs(form.from_date), 'day') || dayjs(form.half_day_date).isAfter(dayjs(form.to_date), 'day'))) {
    writeError.value = 'Half Day Date must be between From Date and To Date.'; return false
  }
  return true
}
async function submitLeave(action: Action, workflowAction?: string) {
  if (busy.value || !metadata.value || loadError.value) return
  writeError.value = ''
  if (action !== 'cancel' && !validForm()) { confirmation.value = null; return }
  try {
    if (isEditing.value) {
      await updateLeave.submit({ name: metadata.value.name, expected_modified: metadata.value.modified,
        values: action === 'cancel' ? {} : buildSubmitValues(), action, workflow_action: workflowAction })
    } else await createLeave.submit({ values: buildSubmitValues() })
  } catch { /* Resource error handler keeps the form and the user's edits visible. */ }
}
function confirmAction() {
  if (confirmation.value) void submitLeave(confirmation.value.action, confirmation.value.action === 'workflow' ? confirmation.value.label : undefined)
}
function closeDialog() { if (!saving.value) emit('update:modelValue', false) }
function isSectionField(field: LeaveField) { return ['Section Break', 'Tab Break'].includes(field.fieldtype) }
function isLayout(field: LeaveField) { return isSectionField(field) || field.fieldtype === 'Column Break' }
function isLinkField(field: LeaveField) { return ['Link', 'Dynamic Link'].includes(field.fieldtype) }
function isTextareaField(field: LeaveField) { return ['Small Text', 'Long Text', 'Text', 'Text Editor', 'Code'].includes(field.fieldtype) }
function resolveLinkDoctype(field: LeaveField) { return field.fieldtype === 'Dynamic Link' ? form[field.options || ''] || '' : field.options || '' }
function inputType(field: LeaveField) {
  if (field.fieldtype === 'Date') return 'date'
  if (field.fieldtype === 'Datetime') return 'datetime-local'
  if (field.fieldtype === 'Time') return 'time'
  if (field.fieldtype === 'Color') return 'color'
  if (['Int', 'Float', 'Currency', 'Percent', 'Rating'].includes(field.fieldtype)) return 'number'
  if (field.options === 'Email') return 'email'
  if (field.fieldtype === 'Password') return 'password'
  if (field.fieldtype === 'Phone') return 'tel'
  return 'text'
}
function selectOptions(field: LeaveField) {
  let options = String(field.options || '').split('\n')
  if (field.fieldname === 'status' && !fieldReadOnly(field)) options = canSubmit.value
    ? options.filter(option => option !== 'Cancelled') : options.filter(option => !option || option === 'Open')
  return options.map(value => ({ value, label: value }))
}
function condition(expression?: string, fallback = true): boolean {
  if (!expression?.trim()) return fallback
  if (!expression.startsWith('eval:')) return Boolean(form[expression])
  try { return Boolean(Function('doc', `return Boolean(${expression.slice(5)})`)(form)) }
  catch { return false }
}
function searchLinks(field: LeaveField, query: string) {
  clearTimeout(linkTimers[field.fieldname])
  linkTimers[field.fieldname] = setTimeout(() => void fetchLinkOptions(field, query), 220)
}
async function fetchLinkOptions(field: LeaveField, query: string) {
  if (fieldDisabled(field) || !resolveLinkDoctype(field)) return
  const generation = loadVersion
  const version = (linkVersions[field.fieldname] || 0) + 1
  linkVersions[field.fieldname] = version
  linkLoading[field.fieldname] = true
  try {
    const options = await linkSearch.fetch({ link_doctype: resolveLinkDoctype(field), txt: query, fieldname: field.fieldname,
      company: form.company || props.company || '', name: props.leaveApplicationName || undefined })
    if (generation === loadVersion && version === linkVersions[field.fieldname]) linkOptions[field.fieldname] = options || []
  } catch (error: any) {
    if (generation === loadVersion) raiseToast('error', errorMessage(error))
  } finally {
    if (generation === loadVersion && version === linkVersions[field.fieldname]) linkLoading[field.fieldname] = false
  }
}
defineExpose({ busy })
</script>
