<template>
  <Teleport to="body">
    <div
      v-if="dialogOpen"
      class="fixed inset-0 z-[9998] bg-black/50"
      @click.self="closeDialog"
    />

    <div
      v-if="dialogOpen"
      class="fixed inset-0 z-[9999] flex items-start justify-center overflow-y-auto px-4 py-10"
      @click.self="closeDialog"
    >
      <div
        class="w-full max-w-5xl overflow-hidden rounded-lg bg-white shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-label="Create Project"
        @click.stop
      >
        <div class="flex items-center justify-between border-b border-gray-200 px-6 py-4">
          <h2 class="text-xl font-semibold text-gray-900">Create Project</h2>
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
      <div v-if="projectMeta.loading" class="py-8 text-center text-sm text-gray-500">
        Loading Project fields...
      </div>

      <div v-else class="space-y-5">
        <div class="rounded-md border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-800">
          This form is generated from the Project DocType fields on this site.
        </div>

        <div class="grid grid-cols-2 gap-4">
          <template v-for="field in visibleFields" :key="field.key">
            <div
              v-if="isSectionField(field)"
              class="col-span-2 mt-2 border-b border-gray-200 pb-2 text-sm font-semibold text-gray-700"
            >
              {{ field.label || sectionFallbackLabel(field.fieldtype) }}
            </div>

            <div
              v-else-if="field.fieldtype !== 'Column Break'"
              :class="fieldContainerClass(field)"
            >
              <label class="mb-1 block text-xs font-medium text-gray-600">
                {{ field.label || field.fieldname }}
                <span v-if="field.reqd" class="text-red-500">*</span>
              </label>

              <div
                v-if="field.unsupported"
                class="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-xs text-gray-500"
              >
                {{ field.fieldtype }} fields are managed from the full Project form in Desk.
              </div>

              <label
                v-else-if="field.fieldtype === 'Check'"
                class="flex min-h-[38px] items-center gap-2 rounded-md border border-gray-200 bg-white px-3 text-sm text-gray-700"
              >
                <input
                  type="checkbox"
                  class="h-4 w-4 rounded border-gray-300"
                  v-model="form[field.fieldname]"
                />
                <span>{{ field.description || 'Yes' }}</span>
              </label>

              <select
                v-else-if="field.fieldtype === 'Select'"
                v-model="form[field.fieldname]"
                class="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-gray-500 focus:outline-none"
              >
                <option
                  v-for="option in selectOptions(field)"
                  :key="option.value"
                  :value="option.value"
                >
                  {{ option.label }}
                </option>
              </select>

              <div v-else-if="isLinkField(field)" class="relative">
                <input
                  :value="linkSearch[field.fieldname] ?? ''"
                  :placeholder="placeholderText(field)"
                  autocomplete="off"
                  class="w-full rounded-md border border-gray-300 bg-white px-3 py-2 pr-9 text-sm text-gray-900 shadow-sm focus:border-gray-500 focus:outline-none"
                  @focus="openLinkField(field)"
                  @input="onLinkInputEvent(field, $event)"
                  @blur="closeLinkFieldSoon(field)"
                />
                <button
                  v-if="form[field.fieldname]"
                  type="button"
                  class="absolute right-2 top-1/2 -translate-y-1/2 rounded px-1 text-xs text-gray-400 hover:text-gray-700"
                  title="Clear"
                  @mousedown.prevent
                  @click="clearLinkField(field)"
                >
                  ✕
                </button>

                <div
                  v-if="activeLinkField === field.fieldname"
                  class="absolute left-0 right-0 top-full z-[10020] mt-1 max-h-56 overflow-y-auto rounded-md border border-gray-200 bg-white py-1 text-sm shadow-xl"
                  @mousedown.prevent
                >
                  <div v-if="!resolveLinkDoctype(field)" class="px-3 py-2 text-xs text-gray-500">
                    Select {{ linkTargetFieldLabel(field) }} first.
                  </div>
                  <div v-else-if="linkLoading[field.fieldname]" class="px-3 py-2 text-xs text-gray-500">
                    Searching {{ resolveLinkDoctype(field) }}...
                  </div>
                  <div
                    v-else-if="(linkOptions[field.fieldname] || []).length === 0"
                    class="px-3 py-2 text-xs text-gray-500"
                  >
                    No {{ resolveLinkDoctype(field) }} records found.
                  </div>
                  <button
                    v-for="option in linkOptions[field.fieldname] || []"
                    :key="option.value"
                    type="button"
                    class="block w-full px-3 py-2 text-left hover:bg-gray-50 focus:bg-gray-50 focus:outline-none"
                    @mousedown.prevent="selectLinkOption(field, option)"
                  >
                    <div class="font-medium text-gray-900">
                      {{ option.label || option.value }}
                    </div>
                    <div v-if="option.description && option.description !== option.label" class="mt-0.5 truncate text-xs text-gray-500">
                      {{ option.description }}
                    </div>
                    <div v-if="option.label && option.label !== option.value" class="mt-0.5 truncate text-[11px] text-gray-400">
                      {{ option.value }}
                    </div>
                  </button>
                </div>
              </div>

              <textarea
                v-else-if="isTextareaField(field)"
                v-model="form[field.fieldname]"
                :rows="field.fieldtype === 'Text Editor' ? 6 : 3"
                class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-gray-500 focus:outline-none"
              />

              <input
                v-else
                :type="inputType(field)"
                v-model="form[field.fieldname]"
                :placeholder="placeholderText(field)"
                class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-gray-500 focus:outline-none"
              />

              <p v-if="field.description && field.fieldtype !== 'Check'" class="mt-1 text-xs text-gray-500">
                {{ field.description }}
              </p>
            </div>
          </template>
        </div>
      </div>
        </div>

        <div class="border-t border-gray-200 bg-gray-50 px-6 py-4">
      <div class="flex items-center justify-end gap-2">
        <Button variant="subtle" @click="closeDialog">Cancel</Button>
        <Button
          variant="solid"
          :loading="createProject.loading"
          @click="submitProject"
        >
          Create Project
        </Button>
      </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Button, createResource } from 'frappe-ui'
import { raiseToast } from '../utils'

type ProjectField = {
  key: string
  fieldname: string
  fieldtype: string
  label?: string | null
  options?: string | null
  reqd?: 0 | 1 | boolean
  default?: string | number | null
  depends_on?: string | null
  description?: string | null
  unsupported?: boolean
}

type ProjectMetaResponse = {
  doctype: string
  title?: string
  fields: ProjectField[]
}

type LinkOption = {
  value: string
  label?: string
  description?: string
}

const props = defineProps<{
  modelValue?: boolean
  isDialogOpen: boolean
  company?: string
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'fetchEvents'): void
}>()

const form = reactive<Record<string, any>>({})
const linkSearch = reactive<Record<string, string>>({})
const linkOptions = reactive<Record<string, LinkOption[]>>({})
const linkLoading = reactive<Record<string, boolean>>({})
const activeLinkField = ref<string | null>(null)
const linkSearchTimers: Record<string, ReturnType<typeof window.setTimeout>> = {}

const dialogOpen = computed({
  get: () => props.modelValue ?? props.isDialogOpen,
  set: (value: boolean) => emit('update:modelValue', value),
})

const projectMeta = createResource({
  url: 'verto.api.planner.get_project_create_meta',
  auto: false,
  onSuccess(data: ProjectMetaResponse) {
    initialiseForm(data?.fields || [])
  },
  onError(error: { messages?: string[]; message?: string }) {
    raiseToast('error', error?.messages?.[0] || error?.message || 'Failed to load Project fields')
  },
})

const createProject = createResource({
  url: 'verto.api.planner.create_planner_project',
  makeParams() {
    return { values: buildSubmitValues() }
  },
  onSuccess(data: { name?: string; project_name?: string }) {
    raiseToast('success', `Project created${data?.project_name ? `: ${data.project_name}` : ''}`)
    emit('fetchEvents')
    closeDialog()
  },
  onError(error: { messages?: string[]; message?: string }) {
    raiseToast('error', error?.messages?.[0] || error?.message || 'Failed to create Project')
  },
})

const fields = computed<ProjectField[]>(() => {
  const rawFields = (projectMeta.data as ProjectMetaResponse | undefined)?.fields || []
  return rawFields.map((field, index) => ({
    ...field,
    key: field.fieldname || `${field.fieldtype}-${index}`,
  }))
})

const visibleFields = computed(() => fields.value.filter((field) => isFieldVisible(field)))

watch(
  () => props.isDialogOpen,
  (open) => {
    if (open) {
      if (projectMeta.data) initialiseForm(fields.value)
      projectMeta.fetch()
    }
  },
  { immediate: true },
)

function initialiseForm(inputFields: ProjectField[]) {
  Object.keys(form).forEach((key) => delete form[key])
  Object.keys(linkSearch).forEach((key) => delete linkSearch[key])
  Object.keys(linkOptions).forEach((key) => delete linkOptions[key])
  Object.keys(linkLoading).forEach((key) => delete linkLoading[key])
  activeLinkField.value = null

  for (const field of inputFields) {
    if (!field.fieldname || isSectionField(field) || field.fieldtype === 'Column Break' || field.unsupported) continue
    const value = defaultValue(field)
    form[field.fieldname] = value
    if (isLinkField(field)) linkSearch[field.fieldname] = value ? String(value) : ''
  }

  if ('project_name' in form) form.project_name = ''
  if ('status' in form && !form.status) form.status = 'Open'
  if ('is_active' in form && (form.is_active === '' || form.is_active === undefined || form.is_active === null)) {
    const isActiveField = inputFields.find((field) => field.fieldname === 'is_active')
    form.is_active = isActiveField?.fieldtype === 'Check' ? true : 'Yes'
  }
  if ('percent_complete_method' in form && !form.percent_complete_method) form.percent_complete_method = 'Task Completion'
  if ('company' in form && props.company) {
    form.company = props.company
    linkSearch.company = props.company
  }
}

function defaultValue(field: ProjectField) {
  if (field.fieldtype === 'Check') return ['1', 1, true, 'true', 'Yes'].includes(field.default as any)
  if (field.default !== undefined && field.default !== null && field.default !== '') return field.default
  if (field.fieldtype === 'Select' && field.reqd) {
    return selectOptions(field).find((option) => option.value)?.value || ''
  }
  if (['Int', 'Float', 'Currency', 'Percent', 'Rating'].includes(field.fieldtype)) return ''
  return ''
}

function buildSubmitValues() {
  const output: Record<string, any> = {}
  for (const field of fields.value) {
    if (!field.fieldname || isSectionField(field) || field.fieldtype === 'Column Break' || field.unsupported) continue
    if (!isFieldVisible(field)) continue

    const value = form[field.fieldname]
    if (value === '' || value === undefined || value === null) {
      if (field.fieldtype === 'Check') output[field.fieldname] = false
      continue
    }
    output[field.fieldname] = value
  }
  return output
}

function submitProject() {
  const missing = fields.value.find((field) => {
    if (!field.reqd || !isFieldVisible(field) || field.unsupported) return false
    const value = form[field.fieldname]
    return value === '' || value === undefined || value === null
  })

  if (missing) {
    raiseToast('error', `${missing.label || missing.fieldname} is required.`)
    return
  }

  createProject.submit()
}

function closeDialog() {
  emit('update:modelValue', false)
}

function isLinkField(field: ProjectField) {
  return field.fieldtype === 'Link' || field.fieldtype === 'Dynamic Link'
}

function resolveLinkDoctype(field: ProjectField) {
  if (field.fieldtype === 'Link') return field.options || ''
  if (field.fieldtype === 'Dynamic Link' && field.options) return form[field.options] || ''
  return ''
}

function linkTargetFieldLabel(field: ProjectField) {
  if (field.fieldtype !== 'Dynamic Link' || !field.options) return 'document type'
  const targetField = fields.value.find((item) => item.fieldname === field.options)
  return targetField?.label || field.options
}

function openLinkField(field: ProjectField) {
  activeLinkField.value = field.fieldname
  if (!(field.fieldname in linkSearch)) {
    linkSearch[field.fieldname] = form[field.fieldname] ? String(form[field.fieldname]) : ''
  }
  fetchLinkOptions(field)
}

function closeLinkFieldSoon(field: ProjectField) {
  window.setTimeout(() => {
    if (activeLinkField.value === field.fieldname) activeLinkField.value = null
  }, 160)
}

function onLinkInputEvent(field: ProjectField, event: Event) {
  onLinkInput(field, (event.target as HTMLInputElement).value)
}

function onLinkInput(field: ProjectField, value: string) {
  linkSearch[field.fieldname] = value
  form[field.fieldname] = value

  if (linkSearchTimers[field.fieldname]) window.clearTimeout(linkSearchTimers[field.fieldname])
  linkSearchTimers[field.fieldname] = window.setTimeout(() => fetchLinkOptions(field), 220)
}

function clearLinkField(field: ProjectField) {
  form[field.fieldname] = ''
  linkSearch[field.fieldname] = ''
  linkOptions[field.fieldname] = []
  activeLinkField.value = null
}

function selectLinkOption(field: ProjectField, option: LinkOption) {
  form[field.fieldname] = option.value
  linkSearch[field.fieldname] = option.label || option.value
  activeLinkField.value = null
}

async function fetchLinkOptions(field: ProjectField) {
  const linkDoctype = resolveLinkDoctype(field)
  if (!linkDoctype) {
    linkOptions[field.fieldname] = []
    return
  }

  linkLoading[field.fieldname] = true

  try {
    const data = await callPlannerMethod<LinkOption[]>('verto.api.planner.search_project_link_options', {
      link_doctype: linkDoctype,
      txt: linkSearch[field.fieldname] || '',
      fieldname: field.fieldname,
    })
    linkOptions[field.fieldname] = data || []
  } catch (error: any) {
    linkOptions[field.fieldname] = []
    raiseToast('error', error?.message || `Failed to search ${linkDoctype}`)
  } finally {
    linkLoading[field.fieldname] = false
  }
}

async function callPlannerMethod<T>(method: string, params: Record<string, any>): Promise<T> {
  const response = await fetch(`/api/method/${method}`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-Frappe-CSRF-Token': getCsrfToken(),
    },
    body: JSON.stringify(params),
  })

  const payload = await response.json().catch(() => ({}))

  if (!response.ok || payload.exc || payload.exception) {
    const messages = parseServerMessages(payload)
    throw new Error(messages[0] || payload._error_message || payload.message || 'Request failed')
  }

  return payload.message as T
}

function getCsrfToken() {
  const win = window as any
  return win.csrf_token || win.frappe?.csrf_token || ''
}

function parseServerMessages(payload: any) {
  try {
    if (!payload?._server_messages) return []
    return JSON.parse(payload._server_messages)
      .map((message: string) => JSON.parse(message)?.message)
      .filter(Boolean)
  } catch {
    return []
  }
}

function isSectionField(field: ProjectField) {
  return field.fieldtype === 'Section Break' || field.fieldtype === 'Tab Break'
}

function sectionFallbackLabel(fieldtype: string) {
  return fieldtype === 'Tab Break' ? 'Section' : 'Details'
}

function fieldContainerClass(field: ProjectField) {
  return isWideField(field) ? 'col-span-2' : 'col-span-1'
}

function isWideField(field: ProjectField) {
  return ['Small Text', 'Long Text', 'Text', 'Text Editor', 'Code'].includes(field.fieldtype)
}

function isTextareaField(field: ProjectField) {
  return ['Small Text', 'Long Text', 'Text', 'Text Editor', 'Code'].includes(field.fieldtype)
}

function inputType(field: ProjectField) {
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

function placeholderText(field: ProjectField) {
  if (field.fieldtype === 'Link') return field.options ? `Enter ${field.options}` : ''
  if (field.fieldtype === 'Dynamic Link') return field.options ? `Uses ${field.options}` : ''
  return ''
}

function selectOptions(field: ProjectField) {
  const options = String(field.options || '').split('\n')
  return options.map((option) => ({ value: option, label: option || '' }))
}

function isFieldVisible(field: ProjectField) {
  if (!field.depends_on) return true

  const dependsOn = String(field.depends_on).trim()
  if (!dependsOn) return true

  if (dependsOn.startsWith('eval:')) {
    const expression = dependsOn.slice(5)
    try {
      return Boolean(Function('doc', `return Boolean(${expression})`)(form))
    } catch {
      return false
    }
  }

  return Boolean(form[dependsOn])
}
</script>
