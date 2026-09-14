<script setup lang="ts">
import { BottomSheet } from 'frappe-ui'
import { DialogTitle, DialogDescription } from 'reka-ui'

withDefaults(
  defineProps<{ open: boolean; title: string; dismissible?: boolean }>(),
  {
    dismissible: true,
  }
)
const emit = defineEmits<{ 'update:open': [open: boolean] }>()
</script>

<template>
  <BottomSheet
    :open="open"
    :dismissible="dismissible"
    @update:open="emit('update:open', $event)"
  >
    <div class="mobile-sheet-body">
      <DialogTitle class="sr-only">{{ title }}</DialogTitle>
      <DialogDescription class="sr-only"
        >Review {{ title.toLowerCase() }} and use the actions
        below.</DialogDescription
      >
      <slot />
    </div>
  </BottomSheet>
</template>

<style>
/* Preserve Verto's full-width sheets and one scroll region below each header.
   These selectors are scoped to this wrapper, not other Frappe UI sheets. */
.bottom-sheet-content:has(.mobile-sheet-body) {
  max-width: none;
  max-height: calc(100dvh - max(env(safe-area-inset-top), 0.75rem));
}
.bottom-sheet-content:has(.mobile-sheet-body) > div:last-child {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.mobile-sheet-body {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}
.mobile-sheet-body > .drawer-panel {
  min-height: 0;
  max-height: 100%;
}
</style>
