<template>
  <Dialog v-model="dialogOpen" :options="{ title: 'Create Event', size: '4xl' }">
    <template #body-content>
      <div v-if="eventMeta.loading" class="py-8 text-center text-sm text-gray-500">
        Loading Event fields...
      </div>

      <div v-else class="space-y-5">
        <div class="rounded-md border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-800">
          This form is generated from the Event DocType fields on this site.
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
                {{ field.fieldtype }} fields are managed from the full Event form in Desk.
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
    </template>

    <template #actions>
      <div class="flex items-center justify-end gap-2">
        <Button variant="subtle" @click="closeDialog">Cancel</Button>
        <Button
          variant="solid"
          :loading="createEvent.loading"
          @click="submitEvent"
        >
          Create Event
        </Button>
      </div>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { Button, Dialog, createResource } from 'frappe-ui'
import { dayjs, raiseToast } from '../utils'

type EventField = {
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

type EventMetaResponse = {
  doctype: string
  title?: string
  fields: EventField[]
}

const props = defineProps<{
  modelValue?: boolean
  isDialogOpen: boolean
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'fetchEvents'): void
}>()

const form = reactive<Record<string, any>>({})

const dialogOpen = computed({
  get: () => props.modelValue ?? props.isDialogOpen,
  set: (value: boolean) => emit('update:modelValue', value),
})

const eventMeta = createResource({
  url: 'verto.api.planner.get_event_planner_meta',
  auto: false,
  onSuccess(data: EventMetaResponse) {
    initialiseForm(data?.fields || [])
  },
  onError(error: { messages?: string[]; message?: string }) {
    raiseToast('error', error?.messages?.[0] || error?.message || 'Failed to load Event fields')
  },
})

const createEvent = createResource({
  url: 'verto.api.planner.create_planner_event',
  makeParams() {
    return { values: buildSubmitValues() }
  },
  onSuccess(data: { name?: string; subject?: string }) {
    raiseToast('success', `Event created${data?.subject ? `: ${data.subject}` : ''}`)
    emit('fetchEvents')
    closeDialog()
  },
  onError(error: { messages?: string[]; message?: string }) {
    raiseToast('error', error?.messages?.[0] || error?.message || 'Failed to create Event')
  },
})

const fields = computed<EventField[]>(() => {
  const rawFields = (eventMeta.data as EventMetaResponse | undefined)?.fields || []
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
      if (eventMeta.data) initialiseForm(fields.value)
      eventMeta.fetch()
    }
  },
  { immediate: true },
)

function initialiseForm(inputFields: EventField[]) {
  Object.keys(form).forEach((key) => delete form[key])

  for (const field of inputFields) {
    if (!field.fieldname || isSectionField(field) || field.fieldtype === 'Column Break' || field.unsupported) continue
    form[field.fieldname] = defaultValue(field)
  }

  const now = dayjs().minute(0).second(0).millisecond(0)
  if ('subject' in form) form.subject = ''
  if ('event_category' in form && !form.event_category) form.event_category = 'Event'
  if ('event_type' in form && !form.event_type) form.event_type = 'Public'
  if ('status' in form && !form.status) form.status = 'Open'
  if ('send_reminder' in form && form.send_reminder === undefined) form.send_reminder = true
  if ('all_day' in form && form.all_day === undefined) form.all_day = false
  if ('starts_on' in form && !form.starts_on) form.starts_on = now.format('YYYY-MM-DDTHH:mm')
  if ('ends_on' in form && !form.ends_on) form.ends_on = now.add(1, 'hour').format('YYYY-MM-DDTHH:mm')
}

function defaultValue(field: EventField) {
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

function submitEvent() {
  const missing = fields.value.find((field) => {
    if (!field.reqd || !isFieldVisible(field) || field.unsupported) return false
    const value = form[field.fieldname]
    return value === '' || value === undefined || value === null
  })

  if (missing) {
    raiseToast('error', `${missing.label || missing.fieldname} is required.`)
    return
  }

  createEvent.submit()
}

function closeDialog() {
  emit('update:modelValue', false)
}

function isSectionField(field: EventField) {
  return field.fieldtype === 'Section Break' || field.fieldtype === 'Tab Break'
}

function sectionFallbackLabel(fieldtype: string) {
  return fieldtype === 'Tab Break' ? 'Section' : 'Details'
}

function fieldContainerClass(field: EventField) {
  return isWideField(field) ? 'col-span-2' : 'col-span-1'
}

function isWideField(field: EventField) {
  return ['Small Text', 'Long Text', 'Text', 'Text Editor', 'Code'].includes(field.fieldtype)
}

function isTextareaField(field: EventField) {
  return ['Small Text', 'Long Text', 'Text', 'Text Editor', 'Code'].includes(field.fieldtype)
}

function inputType(field: EventField) {
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

function placeholderText(field: EventField) {
  if (field.fieldtype === 'Link') return field.options ? `Enter ${field.options}` : ''
  if (field.fieldtype === 'Dynamic Link') return field.options ? `Uses ${field.options}` : ''
  return ''
}

function selectOptions(field: EventField) {
  const options = String(field.options || '').split('\n')
  return options.map((option) => ({ value: option, label: option || '' }))
}

function isFieldVisible(field: EventField) {
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
