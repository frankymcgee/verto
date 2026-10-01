<template>
  <Dialog v-bind="$attrs" :title="title">
    <DialogDescription class="sr-only">{{
      description || `Review ${title.toLowerCase()} details and use the actions below.`
    }}</DialogDescription>
    <slot />
    <template v-if="$slots.actions" #actions="context"
      ><slot name="actions" v-bind="context"
    /></template>
  </Dialog>
</template>
<script setup lang="ts">
import { Dialog } from "frappe-ui";
import { DialogDescription } from "reka-ui";
defineOptions({ inheritAttrs: false });
defineProps<{ title: string; description?: string }>();
</script>

<style>
/* These selectors cover all planner dialogs, including confirmation dialogs.
   Keep the backdrop on its own composited layer and retain the final opacity
   until Reka removes it, so the closing frame cannot flash back to full dim. */
.dialog-overlay[data-dialog] {
  will-change: opacity;
}

.dialog-overlay[data-dialog][data-state="open"] {
  animation: planner-backdrop-in 180ms ease-out both;
}

.dialog-overlay[data-dialog][data-state="closed"] {
  animation: planner-backdrop-out 140ms ease-in both;
}

.dialog-scroll-container .dialog-content[data-state] {
  animation-duration: 180ms;
  animation-fill-mode: both;
  will-change: opacity, transform;
}

.dialog-scroll-container .dialog-content[data-state="closed"] {
  animation-duration: 140ms;
}

@keyframes planner-backdrop-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes planner-backdrop-out {
  from { opacity: 1; }
  to { opacity: 0; }
}

@media (prefers-reduced-motion: reduce) {
  .dialog-overlay[data-dialog][data-state],
  .dialog-scroll-container .dialog-content[data-state] {
    animation: none;
    will-change: auto;
  }
}
</style>
