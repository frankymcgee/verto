<template>
  <Card class="overflow-visible border border-outline-gray-1 bg-surface-white">
    <!-- Header -->
    <div class="border-b border-outline-gray-1 px-4 py-3">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <h3 class="truncate text-sm font-semibold text-ink-gray-9">
            {{ field.label || 'Rows' }}
          </h3>

          <p
            v-if="field.description"
            class="mt-1 text-sm text-ink-gray-5"
          >
            {{ field.description }}
          </p>

          <p
            v-else-if="field.child_doctype"
            class="mt-1 text-xs text-ink-gray-5"
          >
            {{ field.child_doctype }}
          </p>
        </div>

        <Button
          variant="subtle"
          theme="gray"
          size="sm"
          @click="addRow"
        >
          Add
        </Button>
      </div>
    </div>

    <!-- Empty State -->
    <div
      v-if="rows.length === 0"
      class="p-4"
    >
      <div class="rounded-xl border border-dashed border-outline-gray-2 bg-surface-gray-1 px-4 py-5 text-center">
        <p class="text-sm font-medium text-ink-gray-7">
          No rows added yet.
        </p>

        <p class="mt-1 text-sm text-ink-gray-5">
          Tap Add to create the first row.
        </p>
      </div>
    </div>

    <!-- Rows -->
    <div
      v-else
      class="space-y-3 p-3"
    >
      <Card
        v-for="(row, index) in rows"
        :key="getRowKey(row, index)"
        class="overflow-visible border border-outline-gray-1 bg-surface-white"
      >
        <!-- Row Header -->
        <div class="flex items-center justify-between gap-3 border-b border-outline-gray-1 px-3 py-2.5">
          <div class="min-w-0">
            <p class="text-sm font-medium text-ink-gray-8">
              Row {{ index + 1 }}
            </p>

            <p
              v-if="getRowSummary(row)"
              class="truncate text-xs text-ink-gray-5"
            >
              {{ getRowSummary(row) }}
            </p>
          </div>

          <Button
            variant="ghost"
            theme="red"
            size="sm"
            @click="removeRow(index)"
          >
            Remove
          </Button>
        </div>

        <!-- Row Fields -->
        <div class="space-y-4 p-3">
          <template
            v-for="childField in field.child_fields || []"
            :key="childField.fieldname"
          >
            <!-- Section Break -->
            <div
              v-if="childField.fieldtype === 'Section Break'"
              v-show="isChildFieldVisible(childField, row)"
              class="border-t border-outline-gray-1 pt-4 first:border-t-0 first:pt-0"
            >
              <h4
                v-if="childField.label"
                class="text-sm font-semibold text-ink-gray-9"
              >
                {{ childField.label }}
              </h4>

              <p
                v-if="childField.description"
                class="mt-1 text-sm text-ink-gray-5"
              >
                {{ childField.description }}
              </p>
            </div>

            <!-- Standard Child Fields -->
            <div
              v-else-if="childField.fieldtype !== 'Table'"
              v-show="isChildFieldVisible(childField, row)"
              class="space-y-1"
            >
              <FormControl
                v-if="isTextInput(childField.fieldtype)"
                v-model="row[childField.fieldname]"
                class="w-full"
                :type="getInputType(childField.fieldtype)"
                :label="childField.label"
                :description="childField.description"
                :placeholder="childField.label"
                :required="isChildFieldMandatory(childField, row)"
                :disabled="isChildFieldReadOnly(childField, row)"
              />

              <Textarea
                v-else-if="isTextArea(childField.fieldtype)"
                v-model="row[childField.fieldname]"
                class="w-full"
                :label="childField.label"
                :description="childField.description"
                :placeholder="childField.label"
                :required="isChildFieldMandatory(childField, row)"
                :disabled="isChildFieldReadOnly(childField, row)"
                :rows="3"
              />

              <Select
                v-else-if="childField.fieldtype === 'Select'"
                :model-value="getSelectValue(row, childField.fieldname)"
                class="w-full"
                variant="outline"
                size="md"
                :label="childField.label"
                :description="childField.description"
                :placeholder="childField.label || 'Select option'"
                :options="getSelectOptions(childField.options)"
                :required="isChildFieldMandatory(childField, row)"
                :disabled="isChildFieldReadOnly(childField, row)"
                @update:model-value="(value) => updateSelectValue(row, childField, value)"
              >
                <template #item-label="{ item }">
                  <div class="min-w-0 truncate text-sm text-ink-gray-8">
                    {{ item.label }}
                  </div>
                </template>
              </Select>

              <Checkbox
                v-else-if="childField.fieldtype === 'Check'"
                v-model="row[childField.fieldname]"
                :label="childField.label"
                :description="childField.description"
                :required="isChildFieldMandatory(childField, row)"
                :disabled="isChildFieldReadOnly(childField, row)"
              />

              <LinkField
                v-else-if="childField.fieldtype === 'Link'"
                v-model="row[childField.fieldname]"
                :field="childField"
                :required="isChildFieldMandatory(childField, row)"
                :disabled="isChildFieldReadOnly(childField, row)"
              />

              <div
                v-else-if="childField.fieldtype === 'Signature'"
                class="space-y-1"
              >
                <SignatureField
                  v-model="row[childField.fieldname]"
                  :label="childField.label"
                  :description="childField.description"
                  :required="isChildFieldMandatory(childField, row)"
                  :disabled="isChildFieldReadOnly(childField, row)"
                />
              </div>

              <FormControl
                v-else
                v-model="row[childField.fieldname]"
                class="w-full"
                type="text"
                :label="childField.label"
                :description="childField.description"
                :placeholder="`${childField.label} (${childField.fieldtype})`"
                :required="isChildFieldMandatory(childField, row)"
                :disabled="isChildFieldReadOnly(childField, row)"
              />
            </div>
          </template>
        </div>
      </Card>
    </div>
  </Card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  Button,
  Card,
  Checkbox,
  FormControl,
  Select,
  Textarea,
} from 'frappe-ui'
import LinkField from './LinkField.vue'
import type { MobileField } from '../../pages/NewDocument.vue'
import {
  evaluateDependsOn,
  evaluateMandatoryDependsOn,
  evaluateReadOnlyDependsOn,
} from '../../lib/dependencies'
import SignatureField from './SignatureField.vue'

type ChildRow = Record<string, any>

type SelectOption = {
  label: string
  value: string
}

type SelectValue = string | number | bigint | Record<string, any> | undefined

const props = defineProps<{
  modelValue: ChildRow[]
  field: MobileField
}>()

const emit = defineEmits<{
  'update:modelValue': [value: ChildRow[]]
}>()

const rows = computed({
  get() {
    return props.modelValue || []
  },
  set(value: ChildRow[]) {
    emit('update:modelValue', value)
  },
})

function addRow() {
  const row: ChildRow = {}

  for (const childField of props.field.child_fields || []) {
    if (isLayoutField(childField)) {
      continue
    }

    row[childField.fieldname] = getDefaultValue(childField)
  }

  rows.value = [...rows.value, row]
}

function removeRow(index: number) {
  rows.value = rows.value.filter((_, rowIndex) => rowIndex !== index)
}

function getRowKey(row: ChildRow, index: number) {
  return row.name || row.idx || index
}

function getRowSummary(row: ChildRow) {
  const childFields = props.field.child_fields || []

  const firstUsefulField = childFields.find((childField) => {
    if (isLayoutField(childField)) return false
    if (childField.fieldtype === 'Check') return false
    if (childField.fieldtype === 'Table') return false

    const value = row[childField.fieldname]

    return value !== undefined && value !== null && String(value).trim() !== ''
  })

  if (!firstUsefulField) {
    return ''
  }

  return String(row[firstUsefulField.fieldname])
}

function isLayoutField(field: MobileField) {
  return ['Section Break', 'Tab Break', 'Column Break'].includes(field.fieldtype)
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

  return field.default ?? ''
}

function isChildFieldVisible(field: MobileField, row: ChildRow) {
  return evaluateDependsOn(field.depends_on, row)
}

function isChildFieldMandatory(field: MobileField, row: ChildRow) {
  return Boolean(field.required) || evaluateMandatoryDependsOn(
    field.mandatory_depends_on,
    row
  )
}

function isChildFieldReadOnly(field: MobileField, row: ChildRow) {
  return evaluateReadOnlyDependsOn(field.read_only_depends_on, row)
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

function getSelectValue(row: ChildRow, fieldname: string) {
  const value = row[fieldname]

  if (value === null || value === undefined || value === '') {
    return undefined
  }

  return String(value)
}

function updateSelectValue(row: ChildRow, field: MobileField, selected: SelectValue) {
  if (selected === undefined) {
    row[field.fieldname] = ''
    emitRowsChanged()
    return
  }

  if (typeof selected === 'object') {
    const optionValue = selected.value ?? selected.label ?? ''

    row[field.fieldname] = String(optionValue)
    emitRowsChanged()
    return
  }

  row[field.fieldname] = String(selected)
  emitRowsChanged()
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

function emitRowsChanged() {
  rows.value = [...rows.value]
}
</script>