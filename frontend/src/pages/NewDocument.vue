<template>
  <section class="min-h-screen bg-surface-gray-1">
    <main class="space-y-3 px-3 py-3 pb-[calc(var(--mobile-bottom-tabs-height,4rem)+2rem)]">
      <!-- Top Action Row -->
      <div class="flex items-center justify-between gap-3">
        <div class="min-w-0">
          <p class="truncate text-sm text-ink-gray-5">
            New document
          </p>

          <h1 class="truncate text-base font-semibold text-ink-gray-9">
            {{ schema?.title || 'New Form' }}
          </h1>
        </div>

        <Button
          variant="subtle"
          theme="gray"
          size="sm"
          @click="goBack"
        >
          Back
        </Button>
      </div>

      <!-- Loading State -->
      <Card
        v-if="loading"
        class="p-3"
      >
        <div class="space-y-3">
          <div class="h-4 w-32 rounded bg-surface-gray-3" />
          <div class="h-10 rounded bg-surface-gray-2" />
          <div class="h-10 rounded bg-surface-gray-2" />
          <div class="h-24 rounded bg-surface-gray-2" />
        </div>
      </Card>

      <!-- Error State -->
      <Card
        v-else-if="error"
        class="border border-red-200 bg-red-50 p-3"
      >
        <div class="space-y-2">
          <p class="text-sm font-medium text-red-800">
            Something went wrong
          </p>

          <p class="whitespace-pre-wrap text-sm text-red-700">
            {{ cleanServerMessage(error) }}
          </p>
        </div>
      </Card>

      <!-- Form -->
      <form
        v-else
        class="space-y-3"
        @submit.prevent="submitForm"
      >
        <!-- Warnings -->
        <div
          v-if="warnings.length"
          class="space-y-2"
        >
          <Card
            v-for="warning in warnings"
            :key="warning"
            class="border border-yellow-200 bg-yellow-50 p-3"
          >
            <div class="text-sm text-yellow-800">
              {{ warning }}
            </div>
          </Card>
        </div>

        <!-- Messages -->
        <div
          v-if="messages.length"
          class="space-y-2"
        >
          <Card
            v-for="message in messages"
            :key="message"
            class="border border-blue-200 bg-blue-50 p-3"
          >
            <div class="text-sm text-blue-800">
              {{ message }}
            </div>
          </Card>
        </div>

        <!-- Main Form Card -->
        <Card class="overflow-hidden border border-outline-gray-1 bg-surface-white">
          <!-- Form Tabs -->
          <div
            v-if="formTabs.length > 1"
            class="border-b border-outline-gray-1 bg-surface-white px-3 py-3"
          >
            <div class="flex gap-2 overflow-x-auto">
              <Button
                v-for="tab in formTabs"
                :key="tab.id"
                :variant="activeTab === tab.id ? 'solid' : 'subtle'"
                theme="gray"
                size="sm"
                @click="activeTab = tab.id"
              >
                {{ tab.label || 'Details' }}
              </Button>
            </div>
          </div>

          <!-- Form Fields -->
          <div class="space-y-5 p-3">
            <div
              v-for="tab in formTabs"
              v-show="activeTab === tab.id"
              :key="tab.id"
              class="space-y-5"
            >
              <template
                v-for="field in tab.fields"
                :key="field.fieldname"
              >
                <!-- Section Break -->
                <div
                  v-if="field.fieldtype === 'Section Break'"
                  class="border-t border-outline-gray-1 pt-5 first:border-t-0 first:pt-0"
                >
                  <h2
                    v-if="field.label"
                    class="text-base font-semibold text-ink-gray-9"
                  >
                    {{ field.label }}
                  </h2>

                  <p
                    v-if="field.description"
                    class="mt-1 text-sm text-ink-gray-5"
                  >
                    {{ field.description }}
                  </p>
                </div>

                <!-- Non-table Fields -->
                <div
                  v-else-if="field.fieldtype !== 'Table' && isFieldVisible(field)"
                  class="space-y-1"
                >
                  <FormControl
                    v-if="isTextInput(field.fieldtype)"
                    v-model="values[field.fieldname]"
                    class="w-full"
                    :type="getInputType(field.fieldtype)"
                    :label="field.label"
                    :description="field.description"
                    :placeholder="field.label"
                    :required="isFieldMandatory(field)"
                    :disabled="isFieldReadOnly(field)"
                    @update:model-value="handleFieldChange(field)"
                  />

                  <Textarea
                    v-else-if="isTextArea(field.fieldtype)"
                    v-model="values[field.fieldname]"
                    class="w-full"
                    :label="field.label"
                    :description="field.description"
                    :placeholder="field.label"
                    :required="isFieldMandatory(field)"
                    :disabled="isFieldReadOnly(field)"
                    :rows="4"
                    @update:model-value="handleFieldChange(field)"
                  />

                  <Select
                    v-else-if="field.fieldtype === 'Select'"
                    :model-value="getSelectValue(field.fieldname)"
                    class="w-full"
                    variant="outline"
                    size="md"
                    :label="field.label"
                    :description="field.description"
                    :placeholder="field.label || 'Select option'"
                    :options="getSelectOptions(field.options)"
                    :required="isFieldMandatory(field)"
                    :disabled="isFieldReadOnly(field)"
                    @update:model-value="(value) => updateSelectValue(field, value)"
                  >
                    <template #item-label="{ item }">
                      <div class="min-w-0 truncate text-sm text-ink-gray-8">
                        {{ item.label }}
                      </div>
                    </template>
                  </Select>

                  <Checkbox
                    v-else-if="field.fieldtype === 'Check'"
                    v-model="values[field.fieldname]"
                    :label="field.label"
                    :description="field.description"
                    :required="isFieldMandatory(field)"
                    :disabled="isFieldReadOnly(field)"
                    @update:model-value="handleFieldChange(field)"
                  />

                  <LinkField
                    v-else-if="field.fieldtype === 'Link'"
                    v-model="values[field.fieldname]"
                    :field="field"
                    :required="isFieldMandatory(field)"
                    :disabled="isFieldReadOnly(field)"
                    @change="handleFieldChange(field)"
                  />

                  <SignatureField
                    v-else-if="field.fieldtype === 'Signature'"
                    v-model="values[field.fieldname]"
                    :label="field.label"
                    :description="field.description"
                    :required="isFieldMandatory(field)"
                    :disabled="isFieldReadOnly(field)"
                    @change="handleFieldChange(field)"
                  />

                  <FormControl
                    v-else
                    v-model="values[field.fieldname]"
                    class="w-full"
                    type="text"
                    :label="field.label"
                    :description="field.description"
                    :placeholder="`${field.label} (${field.fieldtype})`"
                    :required="isFieldMandatory(field)"
                    :disabled="isFieldReadOnly(field)"
                    @update:model-value="handleFieldChange(field)"
                  />
                </div>

                <!-- Child Table -->
                <ChildTableField
                  v-else-if="field.fieldtype === 'Table' && isFieldVisible(field)"
                  v-model="values[field.fieldname]"
                  :field="field"
                />
              </template>
            </div>
          </div>
        </Card>

        <!-- Attachments -->
        <Card class="border border-outline-gray-1 bg-surface-white p-3">
          <div class="space-y-3">
            <div>
              <label class="block text-sm font-medium text-ink-gray-8">
                Attachments / Photos
              </label>

              <p class="mt-1 text-sm text-ink-gray-5">
                Add photos, documents, or supporting files.
              </p>
            </div>

            <input
              type="file"
              multiple
              accept="image/*,.pdf,.doc,.docx,.xls,.xlsx"
              class="block w-full rounded border border-outline-gray-2 bg-surface-white px-3 py-2 text-sm text-ink-gray-7 file:mr-3 file:rounded file:border-0 file:bg-surface-gray-2 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-ink-gray-8"
              @change="handleFiles"
            />

            <div
              v-if="files.length"
              class="flex flex-wrap gap-2"
            >
              <Badge
                v-for="file in files"
                :key="file.name + file.size"
                variant="subtle"
              >
                {{ file.name }}
              </Badge>
            </div>
          </div>
        </Card>

        <!-- Submit Button -->
        <div class="pt-1">
          <Button
            type="submit"
            variant="solid"
            theme="gray"
            size="lg"
            class="w-full"
            :loading="submitting"
            :disabled="submitting"
          >
            Submit
          </Button>
        </div>
      </form>
    </main>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Badge,
  Button,
  Card,
  Checkbox,
  FormControl,
  Select,
  Textarea,
} from 'frappe-ui'
import { apiRequest } from '../lib/api'
import {
  evaluateDependsOn,
  evaluateMandatoryDependsOn,
  evaluateReadOnlyDependsOn,
} from '../lib/dependencies'
import LinkField from '../components/mobile-fields/LinkField.vue'
import ChildTableField from '../components/mobile-fields/ChildTableField.vue'
import SignatureField from '../components/mobile-fields/SignatureField.vue'

export type MobileField = {
  fieldname: string
  label: string
  fieldtype: string
  options?: string
  required?: boolean
  default?: any
  description?: string
  depends_on?: string
  mandatory_depends_on?: string
  read_only_depends_on?: string
  read_only?: boolean
  fetch_from?: string
  fetch_if_empty?: boolean
  precision?: string | number
  length?: string | number
  idx?: number
  child_doctype?: string
  child_fields?: MobileField[]
}

type FormSchema = {
  mobile_doctype: string
  doctype: string
  title: string
  title_field?: string
  fields: MobileField[]
}

type FrappeResponse<T> = {
  message: T
}

type FormTab = {
  id: string
  label: string
  fields: MobileField[]
}

type SelectOption = {
  label: string
  value: string
}

type SelectValue = string | number | bigint | Record<string, any> | undefined

type CreateDocumentPayload = {
  doctype: string
  name: string
  route?: string
}

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const submitting = ref(false)
const error = ref('')
const schema = ref<FormSchema | null>(null)
const values = ref<Record<string, any>>({})
const files = ref<File[]>([])
const messages = ref<string[]>([])
const warnings = ref<string[]>([])
const activeTab = ref('')

const mobileDoctype = String(route.params.mobileDoctype || '')

let fieldChangeTimer: number | undefined

const formTabs = computed<FormTab[]>(() => {
  const fields = schema.value?.fields || []
  const tabs: FormTab[] = []

  let currentTab: FormTab = {
    id: 'main',
    label: 'Details',
    fields: [],
  }

  let hasExplicitTabs = false

  for (const field of fields) {
    if (field.fieldtype === 'Tab Break') {
      hasExplicitTabs = true

      if (currentTab.fields.length || tabs.length === 0) {
        tabs.push(currentTab)
      }

      currentTab = {
        id: field.fieldname,
        label: field.label || 'Details',
        fields: [],
      }

      continue
    }

    currentTab.fields.push(field)
  }

  tabs.push(currentTab)

  if (!hasExplicitTabs) {
    return [
      {
        id: 'main',
        label: 'Details',
        fields: fields.filter((field) => field.fieldtype !== 'Tab Break'),
      },
    ]
  }

  return tabs.filter((tab) => tab.fields.length > 0)
})

function goBack() {
  router.back()
}

function isLayoutField(field: MobileField) {
  return ['Section Break', 'Tab Break'].includes(field.fieldtype)
}

function isTextInput(fieldtype: string) {
  return [
    'Data',
    'Phone',
    'Email',
    'Password',
    'Date',
    'Datetime',
    'Time',
    'Int',
    'Float',
    'Currency',
    'Percent',
    'Duration',
    'Barcode',
  ].includes(fieldtype)
}

function isTextArea(fieldtype: string) {
  return [
    'Text',
    'Small Text',
    'Long Text',
    'Text Editor',
    'Code',
  ].includes(fieldtype)
}

function getInputType(fieldtype: string) {
  if (fieldtype === 'Date') return 'date'
  if (fieldtype === 'Datetime') return 'datetime-local'
  if (fieldtype === 'Time') return 'time'
  if (fieldtype === 'Int') return 'number'

  if (['Float', 'Currency', 'Percent', 'Duration'].includes(fieldtype)) {
    return 'number'
  }

  if (fieldtype === 'Email') return 'email'
  if (fieldtype === 'Password') return 'password'
  if (fieldtype === 'Phone') return 'tel'

  return 'text'
}

function normaliseTimeValue(value: any) {
  if (value === undefined || value === null || value === '') {
    return ''
  }

  const stringValue = String(value).trim()

  if (/^\d{2}:\d{2}$/.test(stringValue)) {
    return stringValue
  }

  if (/^\d{2}:\d{2}:\d{2}$/.test(stringValue)) {
    return stringValue.slice(0, 5)
  }

  if (/^\d{1}:\d{2}(:\d{2})?$/.test(stringValue)) {
    return `0${stringValue}`.slice(0, 5)
  }

  if (stringValue.includes('T')) {
    return normaliseTimeValue(stringValue.split('T')[1])
  }

  if (stringValue.includes(' ')) {
    return normaliseTimeValue(stringValue.split(' ')[1])
  }

  return stringValue.slice(0, 5)
}

function normaliseTimeForSave(value: any) {
  const timeValue = normaliseTimeValue(value)

  if (!timeValue) {
    return ''
  }

  return `${timeValue}:00`
}

function getDefaultValue(field: MobileField) {
  if (field.fieldtype === 'Check') {
    return field.default === 1 || field.default === '1' || field.default === true
  }

  if (field.fieldtype === 'Table') {
    return []
  }

  if (field.fieldtype === 'Signature') {
    return field.default ? String(field.default) : ''
  }

  if (field.fieldtype === 'Time') {
    return normaliseTimeValue(field.default)
  }

  return field.default ?? ''
}

function normaliseValueForField(field: MobileField, value: any) {
  if (value === undefined || value === null) {
    return getDefaultValue(field)
  }

  if (field.fieldtype === 'Check') {
    return value === 1 || value === '1' || value === true
  }

  if (field.fieldtype === 'Table') {
    return Array.isArray(value) ? value : []
  }

  if (field.fieldtype === 'Signature') {
    return String(value || '')
  }

  if (field.fieldtype === 'Time') {
    return normaliseTimeValue(value)
  }

  if (field.fieldtype === 'Datetime' && typeof value === 'string' && value.includes(' ')) {
    return value.replace(' ', 'T').slice(0, 16)
  }

  return value
}

function getSelectValue(fieldname: string) {
  const value = values.value[fieldname]

  if (value === null || value === undefined || value === '') {
    return undefined
  }

  return String(value)
}

function updateSelectValue(field: MobileField, selected: SelectValue) {
  if (selected === undefined) {
    values.value[field.fieldname] = ''
    handleFieldChange(field)
    return
  }

  if (typeof selected === 'object') {
    const optionValue = selected.value ?? selected.label ?? ''

    values.value[field.fieldname] = String(optionValue)
    handleFieldChange(field)
    return
  }

  values.value[field.fieldname] = String(selected)
  handleFieldChange(field)
}

function getSelectOptions(options?: string): SelectOption[] {
  if (!options) return []

  return options
    .split('\n')
    .map((option) => option.trim())
    .filter(Boolean)
    .map((option) => ({
      label: option,
      value: option,
    }))
}

function isFieldVisible(field: MobileField) {
  return evaluateDependsOn(field.depends_on, values.value)
}

function isFieldMandatory(field: MobileField) {
  return Boolean(field.required) || evaluateMandatoryDependsOn(
    field.mandatory_depends_on,
    values.value
  )
}

function isFieldReadOnly(field: MobileField) {
  return Boolean(field.read_only) ||
    evaluateReadOnlyDependsOn(field.read_only_depends_on, values.value)
}

function handleFiles(event: Event) {
  const input = event.target as HTMLInputElement
  files.value = Array.from(input.files || [])
}

function mergeUpdatedValues(updatedValues: Record<string, any>) {
  const schemaFieldnames = new Set(
    (schema.value?.fields || [])
      .filter((field) => !isLayoutField(field))
      .map((field) => field.fieldname)
  )

  for (const [fieldname, value] of Object.entries(updatedValues || {})) {
    if (schemaFieldnames.has(fieldname)) {
      const field = schema.value?.fields.find((item) => item.fieldname === fieldname)

      values.value[fieldname] = field
        ? normaliseValueForField(field, value)
        : value
    }
  }
}

function getResponseMessage<T>(data: FrappeResponse<T> | any, fallback: T): T {
  return data?.message ?? fallback
}

function cleanServerMessage(value: string) {
  if (!value) {
    return ''
  }

  try {
    const parsed = JSON.parse(value)

    if (Array.isArray(parsed)) {
      return parsed
        .map((item) => {
          const message = typeof item === 'string' ? JSON.parse(item) : item
          return message.message || message.title || String(item)
        })
        .join('\n')
    }

    if (parsed.message || parsed.exception) {
      return parsed.message || parsed.exception
    }
  } catch {
    // Return original message below.
  }

  return value
}

function getValueForSave(field: MobileField) {
  const value = values.value[field.fieldname]

  if (field.fieldtype === 'Time') {
    return normaliseTimeForSave(value)
  }

  return value
}

function getVisibleValues() {
  const cleaned: Record<string, any> = {}

  for (const field of schema.value?.fields || []) {
    if (isLayoutField(field)) {
      continue
    }

    if (!isFieldVisible(field)) {
      continue
    }

    cleaned[field.fieldname] = getValueForSave(field)
  }

  return cleaned
}

async function applyFetchFrom(changedFieldname: string) {
  const payload = new FormData()

  payload.append('mobile_doctype', mobileDoctype)
  payload.append('changed_fieldname', changedFieldname)
  payload.append('values', JSON.stringify(getVisibleValues()))

  const data = await apiRequest<FrappeResponse<{ values: Record<string, any> }>>(
    '/api/method/verto.api.mobile.documents.apply_fetch_from',
    {
      method: 'POST',
      body: payload,
    }
  )

  const message = getResponseMessage(data, { values: {} })

  mergeUpdatedValues(message.values || {})
}

async function runFieldChange(changedFieldname: string) {
  const payload = new FormData()

  payload.append('mobile_doctype', mobileDoctype)
  payload.append('changed_fieldname', changedFieldname)
  payload.append('values', JSON.stringify(getVisibleValues()))

  const data = await apiRequest<FrappeResponse<{
    values: Record<string, any>
    messages: string[]
    warnings: string[]
  }>>(
    '/api/method/verto.api.mobile.documents.run_field_change',
    {
      method: 'POST',
      body: payload,
    }
  )

  const message = getResponseMessage(data, {
    values: {},
    messages: [],
    warnings: [],
  })

  mergeUpdatedValues(message.values || {})

  messages.value = message.messages || []
  warnings.value = message.warnings || []
}

function handleFieldChange(field: MobileField) {
  if (field.fieldtype === 'Time') {
    values.value[field.fieldname] = normaliseTimeValue(values.value[field.fieldname])
  }

  error.value = ''
  window.clearTimeout(fieldChangeTimer)

  fieldChangeTimer = window.setTimeout(async () => {
    try {
      await applyFetchFrom(field.fieldname)
      await runFieldChange(field.fieldname)
    } catch (err) {
      if (err instanceof Error && err.message === 'Login required') {
        return
      }

      error.value = err instanceof Error
        ? err.message
        : 'Could not update dependent fields.'
    }
  }, 300)
}

async function loadSchema() {
  const params = new URLSearchParams({
    mobile_doctype: mobileDoctype,
  })

  const data = await apiRequest<FrappeResponse<FormSchema>>(
    `/api/method/verto.api.mobile.documents.get_form_schema?${params.toString()}`
  )

  schema.value = data.message

  for (const field of data.message.fields) {
    if (isLayoutField(field)) {
      continue
    }

    values.value[field.fieldname] = getDefaultValue(field)
  }

  activeTab.value = formTabs.value[0]?.id || 'main'
}

async function loadPrefillValues() {
  const params = new URLSearchParams({
    mobile_doctype: mobileDoctype,
  })

  const allowedQueryKeys = [
    'date',
    'project',
    'link_task',
    'work_order_number',
    'project_scope_name',
    'parent_task_name',
  ]

  for (const key of allowedQueryKeys) {
    const value = route.query[key]

    if (typeof value === 'string' && value) {
      params.append(key, value)
    }
  }

  const data = await apiRequest<FrappeResponse<{ values: Record<string, any> }>>(
    `/api/method/verto.api.mobile.documents.get_prefill_values?${params.toString()}`
  )

  mergeUpdatedValues(data.message.values || {})
}

async function loadNewDocument() {
  loading.value = true
  error.value = ''
  messages.value = []
  warnings.value = []
  values.value = {}
  files.value = []

  try {
    if (!mobileDoctype) {
      throw new Error('Missing mobile DocType.')
    }

    await loadSchema()
    await loadPrefillValues()
  } catch (err) {
    if (err instanceof Error && err.message === 'Login required') {
      return
    }

    error.value = err instanceof Error ? err.message : 'Could not load form.'
  } finally {
    loading.value = false
  }
}

async function uploadFiles(doctype: string, targetDocname: string) {
  for (const file of files.value) {
    const formData = new FormData()

    formData.append('file', file)
    formData.append('doctype', doctype)
    formData.append('docname', targetDocname)
    formData.append('is_private', '1')

    const response = await fetch('/api/method/upload_file', {
      method: 'POST',
      credentials: 'include',
      body: formData,
    })

    if (response.status === 401 || response.status === 403) {
      window.location.href = `/login?redirect-to=${encodeURIComponent(window.location.pathname + window.location.search)}`
      throw new Error('Login required')
    }

    if (!response.ok) {
      throw new Error(`Failed to upload ${file.name}`)
    }
  }
}

async function createDocument() {
  const payload = new FormData()

  payload.append('mobile_doctype', mobileDoctype)
  payload.append('values', JSON.stringify(getVisibleValues()))

  const data = await apiRequest<FrappeResponse<CreateDocumentPayload>>(
    '/api/method/verto.api.mobile.documents.create_mobile_doc',
    {
      method: 'POST',
      body: payload,
    }
  )

  return data.message
}

async function submitForm() {
  submitting.value = true
  error.value = ''

  try {
    if (schema.value?.doctype === 'Daily Timesheet' && values.value.duration) {
      const hours = (Number(values.value.duration) / 3600).toFixed(2)
      const confirmed = window.confirm(`Your current hours for this shift is ${hours} hours. Is this correct?`)

      if (!confirmed) {
        submitting.value = false
        return
      }
    }

    const created = await createDocument()

    if (schema.value?.doctype && created.name && files.value.length) {
      await uploadFiles(schema.value.doctype, created.name)
    }

    if (created.route) {
      router.push(created.route)
      return
    }

    goBack()
  } catch (err) {
    if (err instanceof Error && err.message === 'Login required') {
      return
    }

    error.value = err instanceof Error ? err.message : 'Could not submit form.'
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  loadNewDocument()
})
</script>