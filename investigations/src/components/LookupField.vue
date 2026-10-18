<template>
  <label class="field lookup">
    <span>{{ label }}</span>
    <div class="lookup-input">
      <input
        :value="query"
        :disabled="disabled"
        :placeholder="placeholder || 'Search…'"
        autocomplete="off"
        role="combobox"
        :aria-expanded="open"
        :aria-controls="listId"
        @input="onInput"
        @focus="search"
        @keydown.escape="open = false"
        @keydown.enter.prevent="choose(options[0])"
        @blur="deferClose"
      />
      <button
        v-if="modelValue && !disabled"
        type="button"
        class="clear-lookup"
        :aria-label="`Clear ${label}`"
        @mousedown.prevent="choose(null)"
      >
        ×
      </button>
    </div>
    <ul v-if="open && !disabled" :id="listId" role="listbox" class="lookup-options">
      <li v-if="loading" class="lookup-help">Searching…</li>
      <li v-for="option in options" :key="option.name">
        <button
          type="button"
          role="option"
          :aria-selected="option.name === modelValue"
          @mousedown.prevent="choose(option)"
        >
          {{ option.label || option.name
          }}<small v-if="option.label && option.label !== option.name">{{ option.name }}</small>
        </button>
      </li>
      <li v-if="!loading && !options.length" class="lookup-help">
        {{ error || 'No matching accessible records' }}
      </li>
    </ul>
  </label>
</template>
<script setup>
import { ref, watch, onBeforeUnmount, useId } from 'vue'
import { call } from '../api'
const props = defineProps({
  modelValue: String,
  label: String,
  kind: String,
  sourceDoctype: String,
  placeholder: String,
  disabled: Boolean,
})
const emit = defineEmits(['update:modelValue'])
const query = ref(props.modelValue || ''),
  options = ref([]),
  open = ref(false),
  loading = ref(false),
  error = ref('')
const listId = useId()
let timer,
  closeTimer,
  generation = 0
watch(
  () => props.modelValue,
  (value) => {
    query.value = value || ''
  },
)
watch(
  () => props.sourceDoctype,
  () => {
    options.value = []
    generation++
  },
)
function onInput(event) {
  query.value = event.target.value
  clearTimeout(timer)
  timer = setTimeout(search, 200)
}
async function search() {
  if (props.disabled) return
  const current = ++generation
  open.value = true
  loading.value = true
  error.value = ''
  try {
    const results = await call('search_options', {
      kind: props.kind,
      query: query.value === props.modelValue ? '' : query.value,
      source_doctype: props.sourceDoctype,
    })
    if (current === generation) options.value = results || []
  } catch {
    if (current === generation) error.value = 'Could not load options. Try again.'
  } finally {
    if (current === generation) loading.value = false
  }
}
function choose(option) {
  if (!option && options.value.length === 0 && !props.modelValue) return
  generation++
  emit('update:modelValue', option?.name || '')
  query.value = option?.name || ''
  open.value = false
}
function deferClose() {
  closeTimer = setTimeout(() => {
    open.value = false
    query.value = props.modelValue || ''
  }, 150)
}
onBeforeUnmount(() => {
  generation++
  clearTimeout(timer)
  clearTimeout(closeTimer)
})
</script>
