<template>
  <div
    ref="root"
    class="relative space-y-1"
  >
    <div
      v-if="field.label"
      class="space-y-1"
    >
      <label class="block text-sm font-medium text-ink-gray-8">
        {{ field.label }}
        <span
          v-if="required"
          class="text-red-500"
        >*</span>
      </label>

      <p
        v-if="field.description"
        class="text-sm text-ink-gray-5"
      >
        {{ field.description }}
      </p>
    </div>

    <div class="relative">
      <TextInput
        v-model="search"
        class="w-full"
        :placeholder="placeholder"
        :disabled="disabled"
        :required="required"
        autocomplete="off"
        @focus="openOptions"
        @input="handleInput"
        @keydown.down.prevent="moveHighlight(1)"
        @keydown.up.prevent="moveHighlight(-1)"
        @keydown.enter.prevent="selectHighlightedOption"
        @keydown.esc.prevent="closeOptions"
        @change="emit('change')"
      />

      <div
        v-if="loading"
        class="pointer-events-none absolute inset-y-0 right-3 flex items-center"
      >
        <div class="h-4 w-4 animate-spin rounded-full border-2 border-outline-gray-2 border-t-ink-gray-5" />
      </div>
    </div>

    <div
      v-if="showDropdown && !disabled"
      class="absolute left-0 right-0 z-50 mt-1 overflow-hidden rounded-xl border border-outline-gray-2 bg-surface-white shadow-lg"
    >
      <div
        v-if="options.length"
        class="max-h-60 overflow-auto py-1"
      >
        <button
          v-for="(option, index) in options"
          :key="option.name"
          type="button"
          class="block w-full px-3 py-2.5 text-left text-sm transition-colors"
          :class="index === highlightedIndex
            ? 'bg-surface-gray-2 text-ink-gray-9'
            : 'bg-surface-white text-ink-gray-7 hover:bg-surface-gray-1 hover:text-ink-gray-9'"
          @mousedown.prevent="selectOption(option.name)"
        >
          <div class="truncate font-medium">
            {{ option.name }}
          </div>

          <div
            v-if="option.description"
            class="mt-0.5 truncate text-xs text-ink-gray-5"
          >
            {{ option.description }}
          </div>
        </button>
      </div>

      <div
        v-else-if="loading"
        class="px-3 py-3 text-sm text-ink-gray-5"
      >
        Searching...
      </div>

      <div
        v-else-if="search"
        class="px-3 py-3 text-sm text-ink-gray-5"
      >
        No results found.
      </div>

      <div
        v-else
        class="px-3 py-3 text-sm text-ink-gray-5"
      >
        Start typing to search {{ field.options || 'records' }}.
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { TextInput } from 'frappe-ui'
import { apiRequest } from '../../lib/api'
import type { MobileField } from '../../pages/NewDocument.vue'

type LinkOption = {
  name: string
  description?: string
}

type FrappeResponse<T> = {
  message: T
}

const props = defineProps<{
  modelValue?: string
  field: MobileField
  required?: boolean
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  change: []
}>()

const root = ref<HTMLElement | null>(null)
const search = ref(props.modelValue || '')
const options = ref<LinkOption[]>([])
const showOptions = ref(false)
const loading = ref(false)
const highlightedIndex = ref(-1)

let timer: number | undefined
let latestRequestId = 0

const placeholder = computed(() => {
  if (props.field.options) {
    return `Search ${props.field.options}`
  }

  return props.field.label || 'Search'
})

const showDropdown = computed(() => {
  return showOptions.value && !props.disabled
})

watch(
  () => props.modelValue,
  (value) => {
    if (value !== search.value) {
      search.value = value || ''
    }
  }
)

watch(search, (value) => {
  emit('update:modelValue', value || '')
})

function openOptions() {
  if (props.disabled) return

  showOptions.value = true
  loadOptions()
}

function closeOptions() {
  showOptions.value = false
  highlightedIndex.value = -1
}

function handleInput() {
  if (props.disabled) return

  showOptions.value = true
  highlightedIndex.value = -1
  loadOptions()
}

function selectOption(value: string) {
  search.value = value
  emit('update:modelValue', value)
  emit('change')
  closeOptions()
}

function moveHighlight(direction: 1 | -1) {
  if (!showDropdown.value) {
    openOptions()
    return
  }

  if (!options.value.length) {
    highlightedIndex.value = -1
    return
  }

  const nextIndex = highlightedIndex.value + direction

  if (nextIndex < 0) {
    highlightedIndex.value = options.value.length - 1
    return
  }

  if (nextIndex >= options.value.length) {
    highlightedIndex.value = 0
    return
  }

  highlightedIndex.value = nextIndex
}

function selectHighlightedOption() {
  if (!showDropdown.value) {
    openOptions()
    return
  }

  const option = options.value[highlightedIndex.value]

  if (!option) {
    emit('change')
    closeOptions()
    return
  }

  selectOption(option.name)
}

function handleClickOutside(event: MouseEvent) {
  if (!root.value) return

  if (!root.value.contains(event.target as Node)) {
    closeOptions()
  }
}

function loadOptions() {
  if (props.disabled) return

  window.clearTimeout(timer)

  timer = window.setTimeout(async () => {
    if (!props.field.options) {
      options.value = []
      loading.value = false
      return
    }

    const requestId = latestRequestId + 1
    latestRequestId = requestId
    loading.value = true

    try {
      const params = new URLSearchParams({
        doctype: props.field.options,
        txt: search.value || '',
        page_length: '20',
      })

      const data = await apiRequest<FrappeResponse<LinkOption[]>>(
        `/api/method/verto.api.mobile.documents.search_link?${params.toString()}`
      )

      if (requestId !== latestRequestId) {
        return
      }

      options.value = data.message || []
      highlightedIndex.value = options.value.length ? 0 : -1
    } catch {
      if (requestId === latestRequestId) {
        options.value = []
      }
    } finally {
      if (requestId === latestRequestId) {
        loading.value = false
      }
    }
  }, 250)
}

document.addEventListener('mousedown', handleClickOutside)

onBeforeUnmount(() => {
  window.clearTimeout(timer)
  document.removeEventListener('mousedown', handleClickOutside)
})
</script>