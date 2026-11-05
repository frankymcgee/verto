<template>
  <Combobox
    size="md"
    :model-value="modelValue || null"
    v-model:query="query"
    v-model:open="open"
    :label="label"
    :placeholder="placeholder || 'Search…'"
    :options="options"
    :disabled="disabled"
    :loading="loading"
    :filterable="false"
    :open-on-focus="true"
    :empty-text="error || 'No matching accessible records'"
    @update:model-value="$emit('update:modelValue', $event || '')"
  >
    <template #suffix>
      <Button
        v-if="modelValue && !disabled"
        variant="ghost"
        :aria-label="`Clear ${label}`"
        icon="lucide-x"
        @pointerdown.stop
        @click.stop="$emit('update:modelValue', '')"
      />
      <span v-else class="lucide-chevron-down size-4 text-ink-gray-5" aria-hidden="true" />
    </template>
  </Combobox>
</template>
<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'
import { Button, Combobox } from 'frappe-ui'
import { call } from '../api'
const props = defineProps({
  modelValue: String,
  label: String,
  kind: String,
  sourceDoctype: String,
  placeholder: String,
  disabled: Boolean,
})
defineEmits(['update:modelValue'])
const query = ref(''),
  options = ref([]),
  open = ref(false),
  loading = ref(false),
  error = ref('')
let timer,
  generation = 0
function invalidate() {
  generation++
  clearTimeout(timer)
}
async function search(current, value) {
  try {
    const results = await call('search_options', {
      kind: props.kind,
      query: value,
      source_doctype: props.sourceDoctype,
    })
    if (current === generation)
      options.value = (results || []).map((row) => ({
        value: row.name,
        label: row.label || row.name,
        description: row.label && row.label !== row.name ? row.name : undefined,
      }))
  } catch {
    if (current === generation) {
      options.value = []
      error.value = 'Could not load options. Close and reopen to retry.'
    }
  } finally {
    if (current === generation) loading.value = false
  }
}
function schedule(delay = 200) {
  invalidate()
  if (!open.value || props.disabled) {
    loading.value = false
    return
  }
  loading.value = true
  error.value = ''
  const current = generation
  const value = query.value === props.modelValue ? '' : query.value
  timer = setTimeout(() => search(current, value), delay)
}
watch(query, () => schedule())
watch(open, (value) => {
  if (value) schedule(0)
  else {
    invalidate()
    loading.value = false
  }
})
watch(
  () => props.sourceDoctype,
  () => {
    options.value = []
    schedule(0)
  },
)
watch(
  () => props.disabled,
  (value) => {
    if (value) open.value = false
  },
)
onBeforeUnmount(invalidate)
</script>
