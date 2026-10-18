<template>
  <fieldset class="reference-picker" :disabled="disabled">
    <legend>{{ label }}</legend>
    <p v-if="!items.length" class="help">
      {{ emptyText || 'Add evidence first, then link it here.' }}
    </p>
    <label v-for="item in items" :key="item.entry_id" class="check-line">
      <input
        type="checkbox"
        :checked="selected.includes(item.entry_id)"
        @change="toggle(item.entry_id, $event.target.checked)"
      />
      <span
        ><code>{{ item.entry_id }}</code> {{ item.title || item.description || item.entry_id }}
        <small v-if="item.verification_status">· {{ item.verification_status }}</small></span
      >
    </label>
  </fieldset>
</template>
<script setup>
import { computed } from 'vue'
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
    (enabled ? [...selected.value, key] : selected.value.filter((value) => value !== key)).join(
      '\n',
    ),
  )
}
</script>
