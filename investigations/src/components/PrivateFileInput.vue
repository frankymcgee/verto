<template>
  <div class="private-file-input">
    <input
      ref="input"
      type="file"
      hidden
      :disabled="disabled"
      :aria-label="label"
      @change="$emit('change', $event)"
    />
    <Button :disabled="disabled" icon-left="lucide-paperclip" @click="input?.click()">{{
      label
    }}</Button>
  </div>
</template>
<script setup>
import { ref } from 'vue'
import { Button } from 'frappe-ui'
defineProps({ label: { type: String, default: 'Attach file' }, disabled: Boolean })
defineEmits(['change'])
const input = ref(null)
</script>
