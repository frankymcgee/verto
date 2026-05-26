<template>
  <div class="min-h-screen bg-surface-gray-1 text-ink-gray-9 antialiased">
    <AppHeader />

    <main
      ref="mainEl"
      class="mx-auto min-h-[calc(100vh-3.5rem)] max-w-md pb-[calc(var(--mobile-bottom-tabs-height,4rem)+1rem)]"
    >
      <RouterView />
    </main>

    <BottomTabs />
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '../components/AppHeader.vue'
import BottomTabs from '../components/BottomTabs.vue'

const route = useRoute()
const mainEl = ref<HTMLElement | null>(null)

watch(
  () => route.fullPath,
  async () => {
    await nextTick()

    window.scrollTo({
      top: 0,
      left: 0,
      behavior: 'auto',
    })

    mainEl.value?.scrollTo({
      top: 0,
      left: 0,
      behavior: 'auto',
    })
  }
)
</script>