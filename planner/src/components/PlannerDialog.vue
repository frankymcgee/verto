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
