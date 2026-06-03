<template>
  <section class="min-h-screen bg-surface-gray-1">
    <main class="space-y-3 px-3 py-3 pb-[calc(var(--mobile-bottom-tabs-height,4rem)+2rem)]">
      <!-- Top Action Row -->
      <div class="flex items-center justify-between gap-3">
        <div class="min-w-0">
          <p class="truncate text-sm text-ink-gray-5">
            Editing
          </p>

          <h1 class="truncate text-base font-semibold text-ink-gray-9">
            {{ schema?.title || docname || 'Edit Form' }}
          </h1>

          <p
            v-if="docname"
            class="mt-0.5 truncate text-xs text-ink-gray-5"
          >
            {{ docname }}
          </p>
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
        @submit.prevent="saveForm"
      >
        <!-- Permission Warning -->
        <Card
          v-if="!canWrite"
          class="border border-yellow-200 bg-yellow-50 p-3"
        >
          <p class="text-sm font-medium text-yellow-900">
            Read only
          </p>

          <p class="mt-1 text-sm text-yellow-800">
            You can view this document, but you do not have permission to save changes.
          </p>
        </Card>

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

        <!-- Saved Message -->
        <Card
          v-if="saved"
          class="border border-green-200 bg-green-50 p-3"
        >
          <p class="text-sm text-green-800">
            Saved successfully.
          </p>
        </Card>

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
                    :disabled="isFieldReadOnly(field) || !canWrite"
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
                    :disabled="isFieldReadOnly(field) || !canWrite"
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
                    :disabled="isFieldReadOnly(field) || !canWrite"
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
                    :disabled="isFieldReadOnly(field) || !canWrite"
                    @update:model-value="handleFieldChange(field)"
                  />

                  <LinkField
                    v-else-if="field.fieldtype === 'Link'"
                    v-model="values[field.fieldname]"
                    :field="field"
                    :required="isFieldMandatory(field)"
                    :disabled="isFieldReadOnly(field) || !canWrite"
                    @change="handleFieldChange(field)"
                  />

                  <SignatureField
                    v-else-if="field.fieldtype === 'Signature'"
                    v-model="values[field.fieldname]"
                    :label="field.label"
                    :description="field.description"
                    :required="isFieldMandatory(field)"
                    :disabled="isFieldReadOnly(field) || !canWrite"
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
                    :disabled="isFieldReadOnly(field) || !canWrite"
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

        <!-- Existing Attachments -->
        <Card
          v-if="existingFiles.length"
          class="border border-outline-gray-1 bg-surface-white p-3"
        >
          <div class="space-y-3">
            <div>
              <label class="block text-sm font-medium text-ink-gray-8">
                Existing Attachments
              </label>

              <p class="mt-1 text-sm text-ink-gray-5">
                Files already attached to this document.
              </p>
            </div>

            <div class="space-y-2">
              <a
                v-for="file in existingFiles"
                :key="file.name || file.file_url"
                :href="file.file_url"
                target="_blank"
                rel="noopener noreferrer"
                class="flex items-center justify-between gap-3 rounded-xl border border-outline-gray-1 bg-surface-gray-1 px-3 py-2 text-sm"
              >
                <span class="min-w-0 truncate text-ink-gray-8">
                  {{ file.file_name || file.file_url }}
                </span>

                <span class="shrink-0 text-xs text-ink-gray-5">
                  Open
                </span>
              </a>
            </div>
          </div>
        </Card>

        <!-- New Attachments -->
        <Card
          v-if="canWrite"
          class="border border-outline-gray-1 bg-surface-white p-3"
        >
          <div class="space-y-3">
            <div>
              <label class="block text-sm font-medium text-ink-gray-8">
                Add Attachments / Photos
              </label>

              <p class="mt-1 text-sm text-ink-gray-5">
                Add new photos, documents, or supporting files.
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

        <!-- Save Button -->
        <div
          v-if="canWrite"
          class="pt-1"
        >
          <Button
            type="submit"
            variant="solid"
            theme="gray"
            size="lg"
            class="w-full"
            :loading="saving"
            :disabled="saving"
          >
            Save Changes
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
import type { MobileField } from './NewDocument.vue'

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

type EditDocumentPayload = {
  schema: FormSchema
  doctype: string
  name: string
  docstatus?: number
  values: Record<string, any>
  files?: ExistingFile[]
  can_write?: boolean
}

type UpdateDocumentPayload = {
  doctype: string
  name: string
  docstatus?: number
  values?: Record<string, any>
  files?: ExistingFile[]
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

type ExistingFile = {
  name?: string
  file_name?: string
  file_url: string
  is_private?: boolean
  file_size?: number
}

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const saving = ref(false)
const saved = ref(false)
const error = ref('')
const schema = ref<FormSchema | null>(null)
const values = ref<Record<string, any>>({})
const files = ref<File[]>([])
const existingFiles = ref<ExistingFile[]>([])
const messages = ref<string[]>([])
const warnings = ref<string[]>([])
const activeTab = ref('')
const canWrite = ref(false)
const docstatus = ref(0)

const mobileDoctype = String(route.params.mobileDoctype || '')
const docname = String(route.params.docname || '')

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

function normaliseLoadedValue(field: MobileField, value: any) {
  if (value === undefined || value === null) {
    if (field.fieldtype === 'Check') {
      return false
    }

    if (field.fieldtype === 'Table') {
      return []
    }

    if (field.fieldtype === 'Signature') {
      return ''
    }

    if (field.fieldtype === 'Time') {
      return ''
    }

    return ''
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
  if (!canWrite.value) {
    return
  }

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
  return evaluateReadOnlyDependsOn(field.read_only_depends_on, values.value)
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
        ? normaliseLoadedValue(field, value)
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
  if (!canWrite.value) {
    return
  }

  const payload = new FormData()

  payload.append('mobile_doctype', mobileDoctype)
  payload.append('docname', docname)
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
  if (!canWrite.value) {
    return
  }

  const payload = new FormData()

  payload.append('mobile_doctype', mobileDoctype)
  payload.append('docname', docname)
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
  if (!canWrite.value) {
    return
  }

  if (field.fieldtype === 'Time') {
    values.value[field.fieldname] = normaliseTimeValue(values.value[field.fieldname])
  }

  saved.value = false
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

function setLoadedValues(loadedValues: Record<string, any>) {
  values.value = {}

  for (const field of schema.value?.fields || []) {
    if (isLayoutField(field)) {
      continue
    }

    values.value[field.fieldname] = normaliseLoadedValue(
      field,
      loadedValues?.[field.fieldname]
    )
  }
}

async function loadEditDocument() {
  loading.value = true
  error.value = ''
  messages.value = []
  warnings.value = []
  values.value = {}
  files.value = []
  existingFiles.value = []
  saved.value = false
  canWrite.value = false
  docstatus.value = 0

  try {
    if (!mobileDoctype || !docname) {
      throw new Error('Missing document details.')
    }

    const payload = new FormData()

    payload.append('mobile_doctype', mobileDoctype)
    payload.append('docname', docname)

    const data = await apiRequest<FrappeResponse<EditDocumentPayload>>(
      '/api/method/verto.api.mobile.documents.get_mobile_doc_for_edit',
      {
        method: 'POST',
        body: payload,
      }
    )

    const message = data.message

    schema.value = message.schema
    canWrite.value = Boolean(message.can_write)
    docstatus.value = Number(message.docstatus || 0)
    existingFiles.value = message.files || []

    setLoadedValues(message.values || {})

    activeTab.value = formTabs.value[0]?.id || 'main'
  } catch (err) {
    if (err instanceof Error && err.message === 'Login required') {
      return
    }

    error.value = err instanceof Error ? err.message : 'Could not load document.'
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

async function saveDocument() {
  const payload = new FormData()

  payload.append('mobile_doctype', mobileDoctype)
  payload.append('docname', docname)
  payload.append('values', JSON.stringify(getVisibleValues()))

  const data = await apiRequest<FrappeResponse<UpdateDocumentPayload>>(
    '/api/method/verto.api.mobile.documents.update_mobile_doc',
    {
      method: 'POST',
      body: payload,
    }
  )

  const message = data.message

  if (message.values) {
    setLoadedValues(message.values)
  }

  existingFiles.value = message.files || existingFiles.value
  docstatus.value = Number(message.docstatus || docstatus.value || 0)
}

async function saveForm() {
  if (!canWrite.value) {
    error.value = 'You do not have permission to save this document.'
    return
  }

  saving.value = true
  error.value = ''
  saved.value = false

  try {
    if (schema.value?.doctype === 'Daily Timesheet' && values.value.duration) {
      const hours = (Number(values.value.duration) / 3600).toFixed(2)
      const confirmed = window.confirm(`Your current hours for this shift is ${hours} hours. Is this correct?`)

      if (!confirmed) {
        saving.value = false
        return
      }
    }

    await saveDocument()

    if (schema.value?.doctype && files.value.length) {
      await uploadFiles(schema.value.doctype, docname)
    }

    files.value = []
    saved.value = true

    window.setTimeout(() => {
      goBack()
    }, 500)
  } catch (err) {
    if (err instanceof Error && err.message === 'Login required') {
      return
    }

    error.value = err instanceof Error ? err.message : 'Could not save document.'
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadEditDocument()
})
</script>