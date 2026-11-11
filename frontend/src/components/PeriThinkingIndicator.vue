<script setup lang="ts">
defineProps<{ name: string }>()
</script>

<template>
  <div
    role="status"
    class="ml-8 flex w-fit items-center gap-1.5 rounded-8 border border-outline-gray-1 bg-surface-base px-3 py-3 text-ink-gray-6 shadow-sm"
  >
    <span class="sr-only">{{ name }} is thinking</span>
    <span
      v-for="dot in 3"
      :key="dot"
      class="thinking-dot h-1.5 w-1.5 rounded-full bg-current"
      aria-hidden="true"
    />
  </div>
</template>

<style scoped>
.thinking-dot {
  animation: peri-thinking 1.2s ease-in-out infinite;
}

.thinking-dot:nth-last-child(2) {
  animation-delay: 0.15s;
}

.thinking-dot:last-child {
  animation-delay: 0.3s;
}

@keyframes peri-thinking {
  0%, 60%, 100% {
    opacity: 0.45;
    transform: translateY(0);
  }

  30% {
    opacity: 1;
    transform: translateY(-0.2rem);
  }
}

@media (prefers-reduced-motion: reduce) {
  .thinking-dot {
    animation: none;
  }
}
</style>
