<script setup lang="ts">
import { Button } from 'frappe-ui'

export type MobileFormOption = {
  label: string
  doctype: string
  mobile_doctype: string
}

withDefaults(defineProps<{
  title: string
  taskTitle?: string
  options: MobileFormOption[]
  closeLabel?: string
}>(), {
  closeLabel: 'Close',
})

const emit = defineEmits<{ close: []; select: [option: MobileFormOption] }>()
</script>

<template>
  <section class="bottom-sheet-panel drawer-panel flex w-full min-w-0 flex-col overflow-hidden rounded-t-3xl border border-outline-gray-1 bg-surface-base shadow-2xl">
    <div class="z-10 flex shrink-0 items-center justify-between gap-3 border-b border-outline-gray-1 bg-surface-base px-4 py-3">
      <div class="min-w-0">
        <h2 class="truncate text-lg-semibold text-ink-gray-9">{{ title }}</h2>
        <p v-if="taskTitle" class="mt-1 truncate text-sm text-ink-gray-5">{{ taskTitle }}</p>
      </div>
      <Button class="min-h-11 shrink-0" variant="subtle" theme="gray" @click="emit('close')">{{ closeLabel }}</Button>
    </div>

    <div class="bottom-sheet-body grid min-h-0 flex-1 grid-cols-1 content-start gap-2 overflow-y-auto overscroll-contain p-4 pb-[calc(env(safe-area-inset-bottom)+2rem)] sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      <button
        v-for="option in options"
        :key="option.mobile_doctype"
        type="button"
        class="w-full rounded-7 border border-outline-gray-1 bg-surface-base p-3 text-left shadow-sm transition hover:border-outline-gray-2 hover:bg-surface-gray-1 active:scale-[0.99]"
        @click="emit('select', option)"
      >
        <p class="font-semibold text-ink-gray-9">{{ option.label }}</p>
        <p class="mt-1 text-xs text-ink-gray-5">{{ option.doctype }}</p>
      </button>

      <div
        v-if="!options.length"
        class="rounded-7 border border-dashed border-outline-gray-2 bg-surface-gray-1 px-4 py-6 text-center sm:col-span-2 lg:col-span-3 xl:col-span-4"
      >
        <p class="text-sm-medium text-ink-gray-7">No forms available.</p>
        <p class="mt-1 text-sm text-ink-gray-5">Check the mobile form configuration for this action.</p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.bottom-sheet-panel {
  max-height: min(
    82dvh,
    calc(100dvh - max(env(safe-area-inset-top, 0px), 0.75rem))
  );
}
</style>
