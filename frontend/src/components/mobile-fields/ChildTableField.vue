<!-- VERTO_CHILD_TABLE_DRAWER_SLIDE_UP_2026_06_11 -->
<template>
  <div class="space-y-2">
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <label class="block text-sm font-medium text-ink-gray-8">
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
        class="w-full rounded-xl border border-outline-gray-1 bg-surface-white px-3 py-3 text-left shadow-sm transition active:scale-[0.99]"
        @click="openExistingRow(index)"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <p class="truncate text-sm font-semibold text-ink-gray-9">
              {{ getRowTitle(row, index) }}
            </p>

            <p
              v-if="getRowSubtitle(row)"
              class="mt-1 line-clamp-2 text-xs text-ink-gray-5"
            >
              {{ getRowSubtitle(row) }}
            </p>
          </div>

          <span class="shrink-0 text-xs font-medium text-blue-600">
            {{ disabled ? 'View' : 'Edit' }}
          </span>
        </div>
      </button>
    </div>

    <div
      v-else
      class="rounded-xl border border-dashed border-outline-gray-2 bg-surface-gray-1 px-4 py-5 text-center"
    >
      <p class="text-sm font-medium text-ink-gray-7">
        No rows added.
      </p>

      <p class="mt-1 text-sm text-ink-gray-5">
        {{ disabled ? 'There are no entries to view.' : 'Tap Add to create an entry.' }}
      </p>
    </div>

    <Transition name="drawer-fade-slide">
      <div
        v-if="drawerOpen"
        class="fixed inset-0 z-[70] flex items-end bg-black/40"
        @click.self="closeDrawer"
      >
        <Card class="drawer-panel max-h-[88vh] w-full overflow-hidden rounded-b-none rounded-t-3xl border border-outline-gray-1 bg-surface-white">
        <div class="flex items-center justify-between gap-3 border-b border-outline-gray-1 px-4 py-3">
          <div class="min-w-0">
            <h2 class="truncate text-lg font-semibold text-ink-gray-9">
              {{ drawerTitle }}
            </h2>

            <p class="mt-1 truncate text-sm text-ink-gray-5">
              {{ field.label || field.fieldname }}
            </p>
          </div>

          <Button
            variant="subtle"
            theme="gray"
            @click="closeDrawer"
          >
            Close
          </Button>
        </div>

        <div class="max-h-[calc(88vh-132px)] space-y-4 overflow-y-auto px-4 py-4">
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
                class="text-base font-semibold text-ink-gray-9"
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
              <FormControl
                v-if="isTextInput(childField.fieldtype)"
                v-model="draftRow[childField.fieldname]"
                class="w-full"
                :type="getInputType(childField.fieldtype)"
                :label="childField.label"
                :description="childField.description"
                :placeholder="childField.label"
                :required="isFieldMandatory(childField)"
                :disabled="isFieldReadOnly(childField) || disabled"
              />

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
            class="rounded-xl border border-dashed border-outline-gray-2 bg-surface-gray-1 px-4 py-6 text-center"
          >
            <p class="text-sm font-medium text-ink-gray-7">
              No fields configured for this table.
            </p>
          </div>
        </div>

        <div class="flex gap-2 border-t border-outline-gray-1 bg-surface-white px-4 py-3 pb-[calc(env(safe-area-inset-bottom)+0.75rem)]">
          <Button
            v-if="!disabled && editingIndex !== null"
            variant="subtle"
            theme="red"
            class="flex-1 justify-center"
            @click="deleteRow"
          >
            Delete
          </Button>

          <Button
            v-if="!disabled"
            variant="solid"
            theme="gray"
            class="flex-1 justify-center"
            @click="saveRow"
          >
            Save Row
          </Button>

          <Button
            v-else
            variant="solid"
            theme="gray"
            class="w-full justify-center"
            @click="closeDrawer"
          >
            Done
          </Button>
        </div>
        </Card>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  Button,
  Card,
  Checkbox,
  FormControl,
  Select,
  Textarea,
} from 'frappe-ui'
import {
  evaluateDependsOn,
  evaluateMandatoryDependsOn,
  evaluateReadOnlyDependsOn,
} from '../../lib/dependencies'
import LinkField from './LinkField.vue'
import SignatureField from './SignatureField.vue'

type MobileField = {
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

type SelectOption = {
  label: string
  value: string
}

type SelectValue = string | number | bigint | Record<string, any> | undefined

const props = defineProps<{
  modelValue?: Record<string, any>[]
  field: MobileField
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: Record<string, any>[]]
}>()

const drawerOpen = ref(false)
const editingIndex = ref<number | null>(null)
const draftRow = ref<Record<string, any>>({})

const rows = computed(() => {
  return Array.isArray(props.modelValue) ? props.modelValue : []
})

const childFields = computed(() => {
  return (props.field.child_fields || [])
    .slice()
    .sort((a, b) => Number(a.idx || 0) - Number(b.idx || 0))
})

const visibleChildFields = computed(() => {
  return childFields.value.filter((field) => {
    if (field.fieldtype === 'Tab Break' || field.fieldtype === 'Column Break') {
      return false
    }

    if (field.fieldtype === 'Section Break') {
      return true
    }

    return isFieldVisible(field)
  })
})

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
  if (props.disabled) {
    return
  }

  editingIndex.value = null
  draftRow.value = createDraftFromRow()
  drawerOpen.value = true
}

function openExistingRow(index: number) {
  editingIndex.value = index
  draftRow.value = createDraftFromRow(rows.value[index])
  drawerOpen.value = true
}

function closeDrawer() {
  drawerOpen.value = false
  editingIndex.value = null
  draftRow.value = {}
}

function saveRow() {
  if (props.disabled) {
    closeDrawer()
    return
  }

  const cleaned: Record<string, any> = {
    ...draftRow.value,
  }

  for (const field of childFields.value) {
    if (isLayoutField(field)) {
      continue
    }

    if (!isFieldVisible(field)) {
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

  emit('update:modelValue', nextRows)
  closeDrawer()
}

function deleteRow() {
  if (props.disabled || editingIndex.value === null) {
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
  if (props.disabled) {
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
  return evaluateDependsOn(field.depends_on, draftRow.value)
}

function isFieldMandatory(field: MobileField) {
  return Boolean(field.required) || evaluateMandatoryDependsOn(
    field.mandatory_depends_on,
    draftRow.value
  )
}

function isFieldReadOnly(field: MobileField) {
  return Boolean(field.read_only) ||
    evaluateReadOnlyDependsOn(field.read_only_depends_on, draftRow.value)
}

function getRowKey(row: Record<string, any>, index: number) {
  return row.name || row.idx || `${props.field.fieldname}-${index}`
}

function getSummaryFields(row: Record<string, any>) {
  return childFields.value
    .filter((field) => !isLayoutField(field))
    .filter((field) => {
      const value = row[field.fieldname]

      return value !== undefined && value !== null && String(value).trim() !== ''
    })
}

function getRowTitle(row: Record<string, any>, index: number) {
  const firstField = getSummaryFields(row)[0]

  if (firstField) {
    return String(row[firstField.fieldname])
  }

  return `Row ${index + 1}`
}

function getRowSubtitle(row: Record<string, any>) {
  return getSummaryFields(row)
    .slice(1, 4)
    .map((field) => `${field.label || field.fieldname}: ${row[field.fieldname]}`)
    .join(' • ')
}
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
