<template>
  <div class="rounded-3xl bg-white p-4 shadow-sm">
    <button
      type="button"
      class="flex w-full items-center justify-between gap-3 text-left"
      @click="open = !open"
    >
      <div>
        <h2 class="text-lg font-semibold text-gray-900">
          {{ title }}
        </h2>
        <p
          v-if="subtitle"
          class="text-sm text-gray-500"
        >
          {{ subtitle }}
        </p>
      </div>

      <span class="text-xl text-gray-400">
        {{ open ? '−' : '+' }}
      </span>
    </button>

    <div
      v-if="open"
      class="mt-4"
    >
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  title: string
  subtitle?: string
  defaultOpen?: boolean
}>()

const open = ref(Boolean(props.defaultOpen))
</script>