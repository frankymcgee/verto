<!-- VERTO_CHILD_TABLE_DRAWER_STANDARD_ZINDEX_2026_07_01 -->
<template>
  <div class="space-y-2">
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <label class="block text-sm-medium text-ink-gray-8">
          {{ field.label || field.fieldname }}
          <span
            v-if="field.required"
            class="text-red-500"
          >
            *
          </span>
        </label>

        <p
          v-if="field.description"
          class="mt-1 text-sm text-ink-gray-5"
        >
          {{ field.description }}
        </p>
      </div>

      <Button
        v-if="!disabled"
        variant="subtle"
        theme="gray"
        size="sm"
        :disabled="locked"
        @click="openNewRow"
      >
        + Add
      </Button>
    </div>

    <div
      v-if="rows.length"
      class="space-y-2"
    >
      <button
        v-for="(row, index) in rows"
        :key="getRowKey(row, index)"
        type="button"
        :disabled="locked"
        class="w-full rounded-7 border border-outline-gray-1 bg-surface-base px-3 py-3 text-left shadow-sm transition active:scale-[0.99]"
        @click="openExistingRow(index)"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <p class="truncate text-sm-semibold text-ink-gray-9">
              {{ rowSummaries[index].title }}
            </p>

            <p
              v-if="rowSummaries[index].subtitle"
              class="mt-1 line-clamp-2 text-xs text-ink-gray-5"
            >
              {{ rowSummaries[index].subtitle }}
            </p>
          </div>

          <span class="shrink-0 text-xs-medium text-blue-600">
            {{ disabled ? 'View' : 'Edit' }}
          </span>
        </div>
      </button>
    </div>

    <div
      v-else
      class="rounded-7 border border-dashed border-outline-gray-2 bg-surface-gray-1 px-4 py-5 text-center"
    >
      <p class="text-sm-medium text-ink-gray-7">
        No rows added.
      </p>

      <p class="mt-1 text-sm text-ink-gray-5">
        {{ disabled ? 'There are no entries to view.' : 'Tap Add to create an entry.' }}
      </p>
    </div>

    <MobileSheet :open="Boolean(drawerOpen)" :title="drawerTitle" :dismissible="!locked" @update:open="!$event && closeDrawer()">
<template v-if="drawerOpen">
          <section class="rounded-7 shadow-sm drawer-panel flex max-h-[92dvh] w-full flex-col overflow-hidden rounded-b-none rounded-t-3xl border border-outline-gray-1 bg-surface-base shadow-xl">
            <div class="shrink-0 border-b border-outline-gray-1 bg-surface-base px-4 py-3">
              <div class="flex items-center justify-between gap-3">
                <div class="min-w-0">
                  <h2 class="truncate text-lg-semibold text-ink-gray-9">
                    {{ drawerTitle }}
                  </h2>

                  <p class="mt-1 truncate text-sm text-ink-gray-5">
                    {{ field.label || field.fieldname }}
                  </p>
                </div>

                <Button
                  variant="subtle"
                  theme="gray"
                  :disabled="locked"
                  @click="closeDrawer"
                >
                  Close
                </Button>
              </div>
            </div>

            <div class="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain px-4 py-4 pb-[calc(env(safe-area-inset-bottom)+7rem)]">
          <template
            v-for="childField in visibleChildFields"
            :key="childField.fieldname"
          >
            <div
              v-if="childField.fieldtype === 'Section Break'"
              class="border-t border-outline-gray-1 pt-4 first:border-t-0 first:pt-0"
            >
              <h3
                v-if="childField.label"
                class="text-base-semibold text-ink-gray-9"
              >
                {{ childField.label }}
              </h3>

              <p
                v-if="childField.description"
                class="mt-1 text-sm text-ink-gray-5"
              >
                {{ childField.description }}
              </p>
            </div>

            <div
              v-else-if="!isLayoutField(childField)"
              class="space-y-1"
            >
              <DateTimeField
                v-if="isDateTimeField(childField.fieldtype)"
                v-model="draftRow[childField.fieldname]"
                :fieldtype="childField.fieldtype"
                :label="childField.label"
                :description="childField.description"
                :required="isFieldMandatory(childField)"
                :disabled="isFieldReadOnly(childField) || disabled || locked"
              />

              <FormControl
                v-else-if="isTextInput(childField.fieldtype)"
                v-model="draftRow[childField.fieldname]"
                class="w-full"
                :type="getInputType(childField.fieldtype)"
                :label="childField.label"
                :description="childField.description"
                :placeholder="childField.label"
                :required="isFieldMandatory(childField)"
                :disabled="isFieldReadOnly(childField) || disabled"
              />

              <RatingField
                v-else-if="childField.fieldtype === 'Rating'"
                v-model="draftRow[childField.fieldname]"
                :label="childField.label"
                :description="childField.description"
                :required="isFieldMandatory(childField)"
                :disabled="isFieldReadOnly(childField) || disabled || locked"
              />

              <RichTextEditorField v-else-if="childField.fieldtype === 'Text Editor'"
                v-model="draftRow[childField.fieldname]" :label="childField.label"
                :description="childField.description" :required="isFieldMandatory(childField)"
                :disabled="isFieldReadOnly(childField)" />
              <Textarea
                v-else-if="isTextArea(childField.fieldtype)"
                v-model="draftRow[childField.fieldname]"
                class="w-full"
                :label="childField.label"
                :description="childField.description"
                :placeholder="childField.label"
                :required="isFieldMandatory(childField)"
                :disabled="isFieldReadOnly(childField) || disabled"
                :rows="4"
              />

              <Select
                v-else-if="childField.fieldtype === 'Select'"
                :key="getFieldRenderKey(childField)"
                :model-value="getSelectValue(childField.fieldname)"
                class="w-full"
                variant="outline"
                size="md"
                :label="childField.label"
                :description="childField.description"
                :placeholder="childField.label || 'Select option'"
                :options="getSelectOptions(childField.options)"
                :required="isFieldMandatory(childField)"
                :disabled="isFieldReadOnly(childField) || disabled"
                @update:model-value="(value) => updateSelectValue(childField, value)"
              >
                <template #item-label="{ item }">
                  <div class="min-w-0 truncate text-sm text-ink-gray-8">
                    {{ item.label }}
                  </div>
                </template>
              </Select>

              <Checkbox
                v-else-if="childField.fieldtype === 'Check'"
                v-model="draftRow[childField.fieldname]"
                :label="childField.label"
                :description="childField.description"
                :required="isFieldMandatory(childField)"
                :disabled="isFieldReadOnly(childField) || disabled"
              />

              <LinkField
                v-else-if="childField.fieldtype === 'Link'"
                v-model="draftRow[childField.fieldname]"
                :field="childField"
                :required="isFieldMandatory(childField)"
                :disabled="isFieldReadOnly(childField) || disabled"
              />

              <SignatureField
                v-else-if="childField.fieldtype === 'Signature'"
                v-model="draftRow[childField.fieldname]"
                :label="childField.label"
                :description="childField.description"
                :required="isFieldMandatory(childField)"
                :disabled="isFieldReadOnly(childField) || disabled"
              />

              <FormControl
                v-else
                v-model="draftRow[childField.fieldname]"
                class="w-full"
                type="text"
                :label="childField.label"
                :description="childField.description"
                :placeholder="`${childField.label} (${childField.fieldtype})`"
                :required="isFieldMandatory(childField)"
                :disabled="isFieldReadOnly(childField) || disabled"
              />
            </div>
          </template>

          <div
            v-if="visibleChildFields.length === 0"
            class="rounded-7 border border-dashed border-outline-gray-2 bg-surface-gray-1 px-4 py-6 text-center"
          >
            <p class="text-sm-medium text-ink-gray-7">
              No fields configured for this table.
            </p>
          </div>

              <div
                class="h-32 shrink-0"
                aria-hidden="true"
              />
        </div>

            <div class="shrink-0 border-t border-outline-gray-1 bg-surface-base px-4 py-3 pb-[calc(env(safe-area-inset-bottom)+0.75rem)]">
              <p v-if="saveError" role="alert" class="mb-3 whitespace-pre-wrap text-sm text-red-700">
                {{ saveError }}
              </p>
              <div class="flex gap-2">
          <Button
            v-if="!disabled && editingIndex !== null"
            variant="subtle"
            theme="red"
            class="flex-1 justify-center"
            :disabled="locked"
            @click="deleteRow"
          >
            Delete
          </Button>

          <Button
            v-if="!disabled"
            variant="solid"
            theme="gray"
            type="button"
            class="flex-1 justify-center"
            :loading="rowSaving"
            :disabled="locked"
            @click="saveRow"
          >
            Save Row
          </Button>

                <Button
                  v-else
                  variant="solid"
                  theme="gray"
                  class="w-full justify-center"
                  :disabled="locked"
                  @click="closeDrawer"
                >
                  Done
                </Button>
              </div>
            </div>
          </section>
        </template>
</MobileSheet>
  </div>
</template>

<script setup lang="ts">
import MobileSheet from '../MobileSheet.vue'
import { defineAsyncComponent, computed, ref, watch } from 'vue'
import {
  Button,
  Checkbox,
  FormControl,
  Select,
  Textarea,
} from 'frappe-ui'
import {
  evaluateDependsOn,
  evaluateMandatoryDependsOn,
  evaluateReadOnlyDependsOn,
  getVisibleFormFields,
} from '../../lib/dependencies'
import { isDateTimeField } from '../../lib/dateTimeFields'
import DateTimeField from './DateTimeField.vue'
import LinkField from './LinkField.vue'
import SignatureField from './SignatureField.vue'
import RatingField from './RatingField.vue'
const RichTextEditorField = defineAsyncComponent(() => import('./RichTextEditorField.vue'))

type MobileField = {
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

type SelectOption = {
  label: string
  value: string
}

type SelectValue = string | number | bigint | Record<string, any> | undefined

const props = defineProps<{
  modelValue?: Record<string, any>[]
  field: MobileField
  disabled?: boolean
  busy?: boolean
  saveRows?: (rows: Record<string, any>[]) => Promise<boolean | void>
}>()

const emit = defineEmits<{
  'update:modelValue': [value: Record<string, any>[]]
}>()

const drawerOpen = ref(false)
const editingIndex = ref<number | null>(null)
const draftRow = ref<Record<string, any>>({})
const rowSaving = ref(false)
const saveError = ref('')
const locked = computed(() => rowSaving.value || Boolean(props.busy))

const rows = computed(() => {
  return Array.isArray(props.modelValue) ? props.modelValue : []
})

function normaliseFieldDefinition(field: MobileField): MobileField {
  return {
    ...field,
    options: normaliseOptionsValue(field.options),
  }
}

const childFields = computed(() => {
  return (props.field.child_fields || [])
    .map((field) => normaliseFieldDefinition(field))
    .slice()
    .sort((a, b) => Number(a.idx || 0) - Number(b.idx || 0))
})

const visibleChildFields = computed(() => getVisibleFormFields(childFields.value, draftRow.value))

const rowSummaries = computed(() => rows.value.map((row, index) => {
  const summaryFields = getVisibleFormFields(childFields.value, createDraftFromRow(row))
    .filter((field) => {
      const value = row[field.fieldname]
      return !isLayoutField(field) && value !== undefined && value !== null && String(value).trim() !== ''
    })
  const titleField = summaryFields[0]

  return {
    title: titleField ? String(row[titleField.fieldname]) : `Row ${index + 1}`,
    subtitle: summaryFields.slice(1, 4)
      .map((field) => `${field.label || field.fieldname}: ${row[field.fieldname]}`)
      .join(' • '),
  }
}))

const drawerTitle = computed(() => {
  if (editingIndex.value === null) {
    return 'Add row'
  }

  return props.disabled ? 'View row' : 'Edit row'
})

watch(
  () => props.modelValue,
  (value) => {
    if (!Array.isArray(value)) {
      emit('update:modelValue', [])
    }
  },
  { immediate: true }
)

function isLayoutField(field: MobileField) {
  return ['Section Break', 'Column Break', 'Tab Break'].includes(field.fieldtype)
}

function isTextInput(fieldtype: string) {
  return [
    'Data',
    'Phone',
    'Email',
    'Password',
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

  if (field.fieldtype === 'Time') {
    return normaliseTimeValue(field.default)
  }

  return field.default ?? ''
}

function normaliseLoadedValue(field: MobileField, value: any) {
  if (value === undefined || value === null) {
    return getDefaultValue(field)
  }

  if (field.fieldtype === 'Check') {
    return value === 1 || value === '1' || value === true
  }

  if (field.fieldtype === 'Time') {
    return normaliseTimeValue(value)
  }

  if (field.fieldtype === 'Datetime' && typeof value === 'string' && value.includes(' ')) {
    return value.replace(' ', 'T').slice(0, 16)
  }

  return value
}

function getValueForSave(field: MobileField) {
  const value = draftRow.value[field.fieldname]

  if (field.fieldtype === 'Time') {
    return normaliseTimeForSave(value)
  }

  return value
}

function createEmptyRow() {
  const row: Record<string, any> = {}

  for (const field of childFields.value) {
    if (isLayoutField(field)) {
      continue
    }

    row[field.fieldname] = getDefaultValue(field)
  }

  return row
}

function createDraftFromRow(row?: Record<string, any>) {
  const draft = createEmptyRow()

  for (const field of childFields.value) {
    if (isLayoutField(field)) {
      continue
    }

    draft[field.fieldname] = normaliseLoadedValue(field, row?.[field.fieldname])
  }

  if (row) {
    for (const [key, value] of Object.entries(row)) {
      if (!(key in draft)) {
        draft[key] = value
      }
    }
  }

  return draft
}

function openNewRow() {
  if (props.disabled || locked.value) {
    return
  }

  editingIndex.value = null
  saveError.value = ''
  draftRow.value = createDraftFromRow()
  drawerOpen.value = true
}

function openExistingRow(index: number) {
  if (locked.value) return
  saveError.value = ''
  editingIndex.value = index
  draftRow.value = createDraftFromRow(rows.value[index])
  drawerOpen.value = true
}

function closeDrawer() {
  if (locked.value) return
  drawerOpen.value = false
  editingIndex.value = null
  draftRow.value = {}
  saveError.value = ''
}

async function saveRow() {
  if (locked.value) return
  if (props.disabled) {
    closeDrawer()
    return
  }

  // The parent saves the full row, including any hidden field values.
  const cleaned: Record<string, any> = {
    ...draftRow.value,
  }

  for (const field of childFields.value) {
    if (isLayoutField(field)) {
      continue
    }

    if (!evaluateDependsOn(field.depends_on, draftRow.value)) {
      continue
    }

    cleaned[field.fieldname] = getValueForSave(field)
  }

  const nextRows = rows.value.map((row) => ({ ...row }))

  if (editingIndex.value === null) {
    nextRows.push(cleaned)
  } else {
    nextRows[editingIndex.value] = {
      ...nextRows[editingIndex.value],
      ...cleaned,
    }
  }

  rowSaving.value = true
  saveError.value = ''
  try {
    if (props.saveRows) {
      // The parent applies the saved document, including server-normalised rows.
      if (await props.saveRows(nextRows) === false) return
    } else {
      emit('update:modelValue', nextRows)
    }
    rowSaving.value = false
    closeDrawer()
  } catch (err) {
    saveError.value = err instanceof Error ? err.message : 'Could not save row.'
  } finally {
    rowSaving.value = false
  }
}

function deleteRow() {
  if (props.disabled || locked.value || editingIndex.value === null) {
    return
  }

  const nextRows = rows.value.filter((_, index) => index !== editingIndex.value)

  emit('update:modelValue', nextRows)
  closeDrawer()
}

function getSelectValue(fieldname: string) {
  const value = draftRow.value[fieldname]

  if (value === null || value === undefined || value === '') {
    return undefined
  }

  return String(value)
}

function updateSelectValue(field: MobileField, selected: SelectValue) {
  if (props.disabled || locked.value) {
    return
  }

  if (selected === undefined) {
    draftRow.value[field.fieldname] = ''
    return
  }

  if (typeof selected === 'object') {
    const optionValue = selected.value ?? selected.label ?? ''

    draftRow.value[field.fieldname] = String(optionValue)
    return
  }

  draftRow.value[field.fieldname] = String(selected)
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

function isFieldMandatory(field: MobileField) {
  return Boolean(field.required) || evaluateMandatoryDependsOn(
    field.mandatory_depends_on,
    draftRow.value
  )
}

function isFieldReadOnly(field: MobileField) {
  return props.disabled || locked.value || Boolean(field.read_only) ||
    evaluateReadOnlyDependsOn(field.read_only_depends_on, draftRow.value)
}

function getRowKey(row: Record<string, any>, index: number) {
  return row.name || row.idx || `${props.field.fieldname}-${index}`
}
</script>


<style scoped>
.drawer-fade-slide-enter-active,
.drawer-fade-slide-leave-active {
  transition: opacity 0.18s ease;
}

.drawer-panel {
  position: relative;
  z-index: 1;
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
