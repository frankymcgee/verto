<template>
  <div class="mobile-shell min-h-screen bg-gray-50 text-gray-900">
    <AppHeader />

    <main
      ref="mainEl"
      class="mx-auto min-h-[calc(100vh-3.5rem)] max-w-md pb-28"
    >
      <router-view />
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

<style scoped>
.mobile-shell {
  padding-left: env(safe-area-inset-left, 0px);
  padding-right: env(safe-area-inset-right, 0px);
}
</style>