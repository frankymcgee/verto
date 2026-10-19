<template>
  <fieldset class="reference-picker" :disabled="disabled">
    <legend>{{ label }}</legend>
    <p v-if="!items.length" class="help">
      {{ emptyText || 'Add evidence first, then link it here.' }}
    </p>
    <Checkbox
      v-for="item in items"
      :key="item.entry_id"
      :model-value="selected.includes(item.entry_id)"
      :disabled="disabled"
      padded
      class="reference-option"
      @update:model-value="toggle(item.entry_id, $event)"
    >
      <template #label>
        <code>{{ item.entry_id }}</code> {{ item.title || item.description || item.entry_id }}
        <small v-if="item.verification_status"> · {{ item.verification_status }}</small>
      </template>
    </Checkbox>
  </fieldset>
</template>
<script setup>
import { computed } from 'vue'
import { Checkbox } from 'frappe-ui'
import { refs } from '../model'
const props = defineProps({
  modelValue: String,
  label: { type: String, default: 'Supporting evidence' },
  items: { type: Array, default: () => [] },
  disabled: Boolean,
  emptyText: String,
})
const emit = defineEmits(['update:modelValue'])
const selected = computed(() => refs(props.modelValue))
function toggle(key, enabled) {
  emit(
    'update:modelValue',
    (enabled
      ? [...new Set([...selected.value, key])]
      : selected.value.filter((value) => value !== key)
    ).join('\n'),
  )
}
</script>
