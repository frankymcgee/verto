<template>
  <section class="h-full min-h-0 bg-surface-gray-1">
    <main class="space-y-3 px-[var(--verto-page-x,0.75rem)] py-[var(--verto-page-y,0.75rem)]">
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

      <!-- Initial Load Error -->
      <Card
        v-else-if="loadError"
        class="border border-red-200 bg-red-50 p-3"
      >
        <div class="space-y-3">
          <div>
            <p class="text-sm font-medium text-red-800">
              Could not load the form
            </p>

            <p class="mt-1 whitespace-pre-wrap text-sm text-red-700">
              {{ cleanServerMessage(loadError) }}
            </p>
          </div>

          <Button
            variant="solid"
            theme="gray"
            class="w-full justify-center"
            @click="loadNewDocument()"
          >
            Try Again
          </Button>
        </div>
      </Card>

      <!-- Form -->
      <form
        v-else
        class="space-y-3"
        @submit.prevent="submitForm"
      >
        <!-- Restored Draft Notice -->
        <Card
          v-if="draftRestored"
          class="border border-blue-200 bg-blue-50 p-3"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <p class="text-sm font-medium text-blue-900">
                Unsaved draft restored
              </p>

              <p class="mt-1 text-sm text-blue-800">
                Your previously entered form values have been restored.
                <span v-if="draftHadFiles">
                  Attachments must be selected again after leaving or reloading the page.
                </span>
              </p>
            </div>

            <Button
              variant="subtle"
              theme="gray"
              size="sm"
              class="shrink-0"
              @click="discardRestoredDraft"
            >
              Discard
            </Button>
          </div>
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

                  <RichTextEditorField
                    v-else-if="field.fieldtype === 'Text Editor'"
                    v-model="values[field.fieldname]"
                    :label="field.label"
                    :description="field.description"
                    :placeholder="field.label"
                    :required="isFieldMandatory(field)"
                    :disabled="isFieldReadOnly(field)"
                    @change="handleFieldChange(field)"
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
                    :key="getFieldRenderKey(field)"
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

    <Teleport to="body">
      <Transition name="drawer-fade-slide">
        <div
          v-if="actionError"
          class="fixed inset-0 z-[70] flex items-end bg-black/40"
          @click.self="closeErrorDrawer"
        >
          <Card class="drawer-panel flex max-h-[82dvh] w-full flex-col overflow-hidden rounded-b-none rounded-t-3xl border border-outline-gray-1 bg-surface-white shadow-xl">
            <div class="shrink-0 border-b border-outline-gray-1 bg-surface-white px-4 py-3">
              <div class="flex items-center justify-between gap-3">
                <div class="min-w-0">
                  <p class="text-xs font-medium uppercase tracking-wide text-red-600">
                    Action required
                  </p>

                  <h2 class="mt-1 truncate text-lg font-semibold text-ink-gray-9">
                    {{ actionErrorTitle }}
                  </h2>
                </div>

                <Button
                  variant="subtle"
                  theme="gray"
                  size="sm"
                  @click="closeErrorDrawer"
                >
                  Close
                </Button>
              </div>
            </div>

            <div class="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-4">
              <div class="rounded-xl border border-red-200 bg-red-50 p-3">
                <p class="whitespace-pre-wrap text-sm leading-6 text-red-800">
                  {{ cleanServerMessage(actionError) }}
                </p>
              </div>

              <p class="mt-3 text-sm text-ink-gray-5">
                Your form entries have not been cleared. Close this message, correct the issue, and submit again.
              </p>
            </div>

            <div class="shrink-0 border-t border-outline-gray-1 bg-surface-white px-4 py-3 pb-[calc(env(safe-area-inset-bottom)+0.75rem)]">
              <div class="flex gap-2">
                <Button
                  variant="subtle"
                  theme="gray"
                  class="w-full justify-center"
                  @click="closeErrorDrawer"
                >
                  Return to Form
                </Button>
              </div>
            </div>
          </Card>
        </div>
      </Transition>
    </Teleport>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
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
import { withCsrfHeaders } from '../lib/csrf'
import { reportClientError } from '../lib/diagnostics'
import {
  attachFileToDocumentOperation,
  makeOfflineAttachment,
} from '../pwa/offlineQueue'
import {
  evaluateDependsOn,
  evaluateMandatoryDependsOn,
  evaluateReadOnlyDependsOn,
} from '../lib/dependencies'
import LinkField from '../components/mobile-fields/LinkField.vue'
import ChildTableField from '../components/mobile-fields/ChildTableField.vue'
import SignatureField from '../components/mobile-fields/SignatureField.vue'
import RichTextEditorField from '../components/mobile-fields/RichTextEditorField.vue'

export type MobileField = {
  fieldname: string
  label: string
  fieldtype: string
  options?: string | string[]
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
  [key: string]: any
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
  offline_queued?: boolean
  offline_operation_id?: string
}

type DynamicFieldChangeResponse = {
  values?: Record<string, any>
  defaults?: Record<string, any>
  messages?: string[]
  warnings?: string[]
  fields?: MobileField[]
  schema?: Partial<FormSchema> & {
    fields?: MobileField[]
  }
  field_updates?: Record<string, Partial<MobileField>>
  field_options?: Record<string, string | string[]>
  options?: Record<string, string | string[]>
}

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const submitting = ref(false)
const loadError = ref('')
const actionError = ref('')
const actionErrorTitle = ref('Could not save document')
const actionErrorCanRetry = ref(false)
const schema = ref<FormSchema | null>(null)
const values = ref<Record<string, any>>({})
const files = ref<File[]>([])
const messages = ref<string[]>([])
const warnings = ref<string[]>([])
const activeTab = ref('')
const draftRestored = ref(false)
const draftHadFiles = ref(false)
const draftReady = ref(false)

const mobileDoctype = String(route.params.mobileDoctype || '')
const draftStorageKey = `verto:new-document-draft:${mobileDoctype}:${route.fullPath}`

let fieldChangeTimer: number | undefined
let fieldChangeRequestId = 0
let draftSaveTimer: number | undefined

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

type NewDocumentDraft = {
  version: number
  mobileDoctype: string
  route: string
  values: Record<string, any>
  activeTab?: string
  fileNames?: string[]
  savedAt: string
}

function closeErrorDrawer() {
  actionError.value = ''
  actionErrorCanRetry.value = false
}

function showActionError(
  message: string,
  title = 'Could not save document',
  canRetry = false
) {
  actionErrorTitle.value = title
  actionError.value = message
  actionErrorCanRetry.value = canRetry
}

function clearStoredDraft() {
  try {
    window.sessionStorage.removeItem(draftStorageKey)
  } catch {
    // Session storage may be unavailable in restricted browser modes.
  }
}

function getDraftValues() {
  const draftValues: Record<string, any> = {}

  for (const field of schema.value?.fields || []) {
    if (isLayoutField(field)) {
      continue
    }

    draftValues[field.fieldname] = values.value[field.fieldname]
  }

  return draftValues
}

function saveDraftNow() {
  if (!draftReady.value || !schema.value) {
    return
  }

  const draft: NewDocumentDraft = {
    version: 1,
    mobileDoctype,
    route: route.fullPath,
    values: getDraftValues(),
    activeTab: activeTab.value,
    fileNames: files.value.map((file) => file.name),
    savedAt: new Date().toISOString(),
  }

  try {
    window.sessionStorage.setItem(draftStorageKey, JSON.stringify(draft))
  } catch {
    // Keep the live form intact even when browser storage is full/unavailable.
  }
}

function scheduleDraftSave() {
  if (!draftReady.value) {
    return
  }

  window.clearTimeout(draftSaveTimer)

  draftSaveTimer = window.setTimeout(() => {
    saveDraftNow()
  }, 250)
}

function restoreStoredDraft() {
  let rawDraft = ''

  try {
    rawDraft = window.sessionStorage.getItem(draftStorageKey) || ''
  } catch {
    return
  }

  if (!rawDraft) {
    return
  }

  try {
    const draft = JSON.parse(rawDraft) as NewDocumentDraft

    if (
      draft.version !== 1 ||
      draft.mobileDoctype !== mobileDoctype ||
      draft.route !== route.fullPath ||
      !draft.values ||
      typeof draft.values !== 'object'
    ) {
      return
    }

    mergeUpdatedValues(draft.values)
    applyDefaultsForVisibleFields()

    if (draft.activeTab && formTabs.value.some((tab) => tab.id === draft.activeTab)) {
      activeTab.value = draft.activeTab
    }

    draftHadFiles.value = Boolean(draft.fileNames?.length)
    draftRestored.value = true
  } catch {
    clearStoredDraft()
  }
}

async function discardRestoredDraft() {
  clearStoredDraft()
  draftRestored.value = false
  draftHadFiles.value = false
  await loadNewDocument(false)
}

function goBack() {
  saveDraftNow()
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

function normaliseOptionsValue(options?: string | string[]) {
  if (Array.isArray(options)) {
    return options
      .map((option) => String(option).trim())
      .filter(Boolean)
      .join('\n')
  }

  return String(options || '')
}

function getSelectOptions(options?: string | string[]): SelectOption[] {
  const seen = new Set<string>()

  return normaliseOptionsValue(options)
    .split('\n')
    .map((option) => option.trim())
    .filter(Boolean)
    .filter((option) => {
      if (seen.has(option)) {
        return false
      }

      seen.add(option)
      return true
    })
    .map((option) => ({
      label: option,
      value: option,
    }))
}

function getFieldRenderKey(field: MobileField) {
  return [
    field.fieldname,
    field.fieldtype,
    normaliseOptionsValue(field.options),
    String(field.default ?? ''),
    String(field.depends_on || ''),
    String(field.mandatory_depends_on || ''),
    String(field.read_only_depends_on || ''),
  ].join('::')
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

function isBlankValue(value: any) {
  if (value === undefined || value === null) {
    return true
  }

  if (typeof value === 'string') {
    return value.trim() === ''
  }

  if (Array.isArray(value)) {
    return value.length === 0
  }

  return false
}

function normaliseFieldDefinition(field: MobileField): MobileField {
  return {
    ...field,
    options: normaliseOptionsValue(field.options),
  }
}

function mergeUpdatedValues(updatedValues: Record<string, any>) {
  const schemaFieldnames = new Set(
    (schema.value?.fields || [])
      .filter((field) => !isLayoutField(field))
      .map((field) => field.fieldname)
  )

  const nextValues = {
    ...values.value,
  }

  for (const [fieldname, value] of Object.entries(updatedValues || {})) {
    if (schemaFieldnames.has(fieldname)) {
      const field = schema.value?.fields.find((item) => item.fieldname === fieldname)

      nextValues[fieldname] = field
        ? normaliseValueForField(field, value)
        : value
    }
  }

  values.value = nextValues
}

function mergeSchemaFields(updatedFields?: MobileField[]) {
  if (!schema.value || !updatedFields?.length) {
    return
  }

  const nextFields = [...schema.value.fields]

  for (const updatedField of updatedFields) {
    if (!updatedField?.fieldname) {
      continue
    }

    const normalisedField = normaliseFieldDefinition(updatedField)
    const index = nextFields.findIndex((field) => field.fieldname === normalisedField.fieldname)

    if (index >= 0) {
      nextFields[index] = {
        ...nextFields[index],
        ...normalisedField,
      }
    } else {
      nextFields.push(normalisedField)
    }
  }

  schema.value = {
    ...schema.value,
    fields: nextFields,
  }
}

function mergeFieldUpdates(fieldUpdates?: Record<string, Partial<MobileField>>) {
  if (!schema.value || !fieldUpdates || typeof fieldUpdates !== 'object') {
    return
  }

  const patchFields = Object.entries(fieldUpdates)
    .map(([fieldname, patch]) => ({
      fieldname,
      ...(patch || {}),
    })) as MobileField[]

  mergeSchemaFields(patchFields)
}

function mergeFieldOptions(fieldOptions?: Record<string, string | string[]>) {
  if (!schema.value || !fieldOptions || typeof fieldOptions !== 'object') {
    return
  }

  const patchFields = Object.entries(fieldOptions)
    .map(([fieldname, options]) => ({
      fieldname,
      options,
    })) as MobileField[]

  mergeSchemaFields(patchFields)
}

function applyDefaultsForVisibleFields() {
  const nextValues = {
    ...values.value,
  }

  let hasChanges = false

  for (const field of schema.value?.fields || []) {
    if (isLayoutField(field) || !isFieldVisible(field)) {
      continue
    }

    if (field.fieldtype === 'Table' && !Array.isArray(nextValues[field.fieldname])) {
      nextValues[field.fieldname] = []
      hasChanges = true
      continue
    }

    if (!isBlankValue(field.default) && isBlankValue(nextValues[field.fieldname])) {
      nextValues[field.fieldname] = getDefaultValue(field)
      hasChanges = true
    }
  }

  if (hasChanges) {
    values.value = nextValues
  }
}

function applyDynamicFieldResponse(message: DynamicFieldChangeResponse) {
  mergeSchemaFields(message.schema?.fields || message.fields)
  mergeFieldUpdates(message.field_updates)
  mergeFieldOptions(message.field_options)

  // Some backend helpers use "options" as a fieldname -> options map.
  if (message.options && typeof message.options === 'object' && !Array.isArray(message.options)) {
    mergeFieldOptions(message.options)
  }

  mergeUpdatedValues(message.values || {})
  mergeUpdatedValues(message.defaults || {})
  applyDefaultsForVisibleFields()
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

function getAllValuesForFieldChange() {
  const cleaned: Record<string, any> = {}

  for (const field of schema.value?.fields || []) {
    if (isLayoutField(field)) {
      continue
    }

    cleaned[field.fieldname] = getValueForSave(field)
  }

  return cleaned
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

async function processFieldChange(changedFieldname: string) {
  const payload = new FormData()

  payload.append('mobile_doctype', mobileDoctype)
  payload.append('changed_fieldname', changedFieldname)
  payload.append('values', JSON.stringify(getAllValuesForFieldChange()))

  const data = await apiRequest<FrappeResponse<DynamicFieldChangeResponse>>(
    '/api/method/verto.api.mobile.documents.process_field_change',
    {
      method: 'POST',
      body: payload,
    }
  )

  return getResponseMessage(data, {
    values: {},
    messages: [],
    warnings: [],
  })
}

function handleFieldChange(field: MobileField) {
  if (field.fieldtype === 'Time') {
    values.value[field.fieldname] = normaliseTimeValue(values.value[field.fieldname])
  }

  closeErrorDrawer()
  fieldChangeRequestId += 1
  const requestId = fieldChangeRequestId
  window.clearTimeout(fieldChangeTimer)

  fieldChangeTimer = window.setTimeout(async () => {
    try {
      const message = await processFieldChange(field.fieldname)

      if (requestId !== fieldChangeRequestId) {
        return
      }

      applyDynamicFieldResponse(message)
      messages.value = message.messages || []
      warnings.value = message.warnings || []
    } catch (err) {
      if (requestId !== fieldChangeRequestId) {
        return
      }

      if (err instanceof Error && err.message === 'Login required') {
        return
      }

      showActionError(
        err instanceof Error
          ? err.message
          : 'Could not update dependent fields.',
        'Could not update the form',
        false
      )
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

  schema.value = {
    ...data.message,
    fields: (data.message.fields || []).map((field) => normaliseFieldDefinition(field)),
  }

  for (const field of schema.value.fields) {
    if (isLayoutField(field)) {
      continue
    }

    values.value[field.fieldname] = getDefaultValue(field)
  }

  applyDefaultsForVisibleFields()

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
  applyDefaultsForVisibleFields()
}

async function loadNewDocument(restoreDraft = true) {
  loading.value = true
  draftReady.value = false
  loadError.value = ''
  closeErrorDrawer()
  messages.value = []
  warnings.value = []
  values.value = {}
  files.value = []
  draftRestored.value = false
  draftHadFiles.value = false

  try {
    if (!mobileDoctype) {
      throw new Error('Missing mobile DocType.')
    }

    await loadSchema()
    await loadPrefillValues()

    if (restoreDraft) {
      restoreStoredDraft()
    }
  } catch (err) {
    if (err instanceof Error && err.message === 'Login required') {
      return
    }

    loadError.value = err instanceof Error ? err.message : 'Could not load form.'
  } finally {
    loading.value = false
    draftReady.value = Boolean(schema.value && !loadError.value)
  }
}

async function uploadFiles(
  doctype: string,
  targetDocname: string,
  offlineOperationId?: string
) {
  for (const file of files.value) {
    if (offlineOperationId) {
      await attachFileToDocumentOperation(
        offlineOperationId,
        makeOfflineAttachment(file)
      )
      continue
    }

    const formData = new FormData()

    // Supplying the filename explicitly is important on iOS Safari. Without the
    // third argument, some multipart requests arrive in Frappe as an unnamed
    // blob, leaving the File document with neither file_name nor file_url.
    formData.append('file', file, file.name)
    formData.append('file_name', file.name)
    formData.append('doctype', doctype)
    formData.append('docname', targetDocname)
    formData.append('is_private', '1')

    let response: Response
    try {
      response = await fetch('/api/method/verto.api.mobile.documents.upload_mobile_attachment', {
        method: 'POST',
        credentials: 'include',
        headers: withCsrfHeaders(undefined, 'POST'),
        body: formData,
      })
    } catch (error) {
      void reportClientError({
        message: error instanceof Error ? error.message : 'Photo upload network failure',
        stack: error instanceof Error ? error.stack : '',
        source: 'form.photo_upload.network',
        details: {
          doctype,
          docname: targetDocname,
          file_name: file.name,
          file_type: file.type,
          file_size: file.size,
        },
      })
      throw error
    }

    if (response.status === 401 || response.status === 403) {
      window.location.href = `/login?redirect-to=${encodeURIComponent(window.location.pathname + window.location.search)}`
      throw new Error('Login required')
    }

    if (!response.ok) {
      const serverResponse = await response.text().catch(() => '')
      void reportClientError({
        message: `Failed to upload ${file.name}`,
        source: 'form.photo_upload',
        details: {
          doctype,
          docname: targetDocname,
          file_name: file.name,
          file_type: file.type,
          file_size: file.size,
          status: response.status,
          status_text: response.statusText,
          server_response: serverResponse,
        },
      })
      throw new Error(
        serverResponse
          ? `Failed to upload ${file.name}: ${serverResponse.slice(0, 500)}`
          : `Failed to upload ${file.name} (${response.status})`
      )
    }
  }
}

async function queuePhotoAnalysis(doctype: string, docname: string) {
  const payload = new FormData()
  payload.append('doctype', doctype)
  payload.append('docname', docname)

  try {
    await apiRequest(
      '/api/method/verto.api.mobile.ai_photo_analysis.queue_submitted_form_review',
      { method: 'POST', body: payload }
    )
  } catch (err) {
    // Evidence review is deliberately asynchronous and must never make a
    // successfully saved operational form appear to have failed.
    console.error('[Verto AI photo analysis] Could not queue review', err)
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
  closeErrorDrawer()
  saveDraftNow()

  try {
    if (schema.value?.doctype === 'Daily Timesheet' && values.value.duration) {
      const hours = (Number(values.value.duration) / 3600).toFixed(2)
      const confirmed = window.confirm(`Your current hours for this shift is ${hours} hours. Is this correct?`)

      if (!confirmed) {
        return
      }
    }

    const created = await createDocument()

    if (schema.value?.doctype && created.name && files.value.length) {
      await uploadFiles(
        schema.value.doctype,
        created.name,
        created.offline_operation_id
      )

      if (!created.offline_operation_id) {
        await queuePhotoAnalysis(schema.value.doctype, created.name)
      }
    }

    clearStoredDraft()
    draftReady.value = false

    if (created.route) {
      router.push(created.route)
      return
    }

    router.back()
  } catch (err) {
    if (err instanceof Error && err.message === 'Login required') {
      return
    }

    saveDraftNow()

    showActionError(
      err instanceof Error ? err.message : 'Could not submit form.',
      'Could not save document',
      true
    )
  } finally {
    submitting.value = false
  }
}

watch(
  values,
  () => {
    scheduleDraftSave()
  },
  {
    deep: true,
  }
)

watch(activeTab, () => {
  scheduleDraftSave()
})

watch(
  files,
  () => {
    scheduleDraftSave()
  },
  {
    deep: true,
  }
)

onMounted(() => {
  loadNewDocument()
})

onBeforeUnmount(() => {
  fieldChangeRequestId += 1
  window.clearTimeout(fieldChangeTimer)
  window.clearTimeout(draftSaveTimer)
  saveDraftNow()
})
</script>

<style scoped>
.drawer-panel {
  position: relative;
  z-index: 1;
}

.drawer-fade-slide-enter-active,
.drawer-fade-slide-leave-active {
  transition: opacity 0.22s ease;
}

.drawer-fade-slide-enter-active .drawer-panel,
.drawer-fade-slide-leave-active .drawer-panel {
  transition: transform 0.24s ease, opacity 0.24s ease;
}

.drawer-fade-slide-enter-from,
.drawer-fade-slide-leave-to {
  opacity: 0;
}

.drawer-fade-slide-enter-from .drawer-panel,
.drawer-fade-slide-leave-to .drawer-panel {
  transform: translateY(100%);
  opacity: 0.96;
}
</style>
