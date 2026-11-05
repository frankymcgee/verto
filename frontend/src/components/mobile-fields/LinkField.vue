<template>
  <Combobox
    :model-value="modelValue || null"
    :options="selectOptions"
    :label="field.label"
    :description="field.description"
    :placeholder="placeholder"
    :required="required"
    :disabled="disabled"
    :loading="loading"
    :filterable="false"
    :empty-text="
      isOffline ? 'No cached results found.' : 'No matching records found.'
    "
    clearable
    @update:model-value="selectOption"
    @update:query="searchChanged"
    @update:open="opened"
  />
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Combobox } from 'frappe-ui'
import { apiRequest } from '../../lib/api'
import {
  getCachedLinkOptions,
  mergeCachedLinkOptions,
} from '../../pwa/offlineQueue'
import type { MobileField } from '../../pages/NewDocument.vue'

type LinkOption = { name: string; description?: string }
const props = defineProps<{
  modelValue?: string
  field: MobileField
  required?: boolean
  disabled?: boolean
}>()
const emit = defineEmits<{ 'update:modelValue': [value: string]; change: [] }>()
const search = ref('')
const options = ref<LinkOption[]>([])
const loading = ref(false)
const isOffline = ref(!navigator.onLine)
let timer: ReturnType<typeof setTimeout> | undefined
let latestRequestId = 0
const placeholder = computed(() =>
  props.field.options
    ? `Search ${props.field.options}`
    : props.field.label || 'Search'
)
const selectOptions = computed(() => {
  const rows = options.value.map((row) => ({
    value: row.name,
    label: row.name,
    description: row.description,
  }))
  if (props.modelValue && !rows.some((row) => row.value === props.modelValue)) {
    rows.unshift({
      value: props.modelValue,
      label: props.modelValue,
      description: undefined,
    })
  }
  return rows
})
function selectOption(value: unknown) {
  if (value != null && typeof value !== 'string' && typeof value !== 'number')
    return
  emit('update:modelValue', value == null ? '' : String(value))
  emit('change')
}
function searchChanged(value: string) {
  search.value = value
  loadOptions()
}
function opened(open: boolean) {
  if (open) {
    search.value = ''
    loadOptions()
  }
}
function loadOptions() {
  clearTimeout(timer)
  // Invalidate the previous request immediately, including during debounce.
  const requestId = ++latestRequestId
  if (props.disabled || !props.field.options) {
    loading.value = false
    return
  }
  const doctype = String(props.field.options)
  const query = search.value
  loading.value = true
  timer = setTimeout(async () => {
    isOffline.value = !navigator.onLine
    try {
      let rows: LinkOption[]
      if (isOffline.value) {
        rows = await getCachedLinkOptions(doctype, query)
      } else {
        try {
          const params = new URLSearchParams({
            doctype,
            txt: query,
            page_length: '20',
          })
          const response = await apiRequest<{ message: LinkOption[] }>(
            `/api/method/verto.api.mobile.documents.search_link?${params}`
          )
          rows = response.message || []
          void mergeCachedLinkOptions(doctype, rows).catch(() => {})
        } catch {
          rows = await getCachedLinkOptions(doctype, query)
        }
      }
      if (requestId === latestRequestId) options.value = rows
    } catch {
      if (requestId === latestRequestId) options.value = []
    } finally {
      if (requestId === latestRequestId) loading.value = false
    }
  }, 250)
}
watch(
  () => [props.field.options, props.disabled],
  () => {
    options.value = []
    search.value = ''
    loadOptions()
  }
)
onBeforeUnmount(() => {
  clearTimeout(timer)
  latestRequestId++
})
</script>
