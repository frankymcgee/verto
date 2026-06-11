<template>
  <div class="mobile-shell flex h-[100dvh] min-h-0 flex-col overflow-hidden bg-gray-50 text-gray-900">
    <AppHeader class="mobile-shell-header shrink-0" />
    <OfflineSyncStatus />

    <main
      ref="mainEl"
      class="verto-main mx-auto w-full flex-1 overflow-y-auto overscroll-contain bg-surface-gray-1"
    >
      <router-view />
    </main>

    <BottomTabs class="mobile-shell-tabs shrink-0" />
    <PwaUpdatePrompt />
  </div>
</template>

<script setup lang="ts">
// VERTO_MOBILE_SHELL_REMOVE_BOTTOM_PAGE_GAP_2026_06_10
import { nextTick, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '../components/AppHeader.vue'
import BottomTabs from '../components/BottomTabs.vue'
import OfflineSyncStatus from '../components/OfflineSyncStatus.vue'
import PwaUpdatePrompt from '../components/PwaUpdatePrompt.vue'

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
  --verto-shell-max-width: 28rem;
  --verto-page-x: 0.75rem;
  --verto-page-y: 0.75rem;

  padding-left: env(safe-area-inset-left, 0px);
  padding-right: env(safe-area-inset-right, 0px);
}

.verto-main {
  /*
    The bottom tabs now live in the shell as a real footer row.
    This resets the old fixed-tab spacing variable for pages that still
    contain classes such as pb-[calc(var(--mobile-bottom-tabs-height)+...)]
    from the previous layout.
  */
  --mobile-bottom-tabs-height: 0px;

  max-width: var(--verto-shell-max-width);
  min-height: 0;
}

/*
  Older Verto pages were built for the previous fixed-bottom-tabs layout and
  often use min-h-screen or viewport-height calculations internally. In the new
  constrained shell those values create a visible blank area above BottomTabs.

  These scoped deep overrides only apply to page content rendered inside this
  shell main area. They make the top-level page fit the available middle row
  instead of trying to be a full viewport on its own.
*/
.verto-main :deep(> section) {
  min-height: 100% !important;
}

.verto-main :deep(> section.min-h-screen) {
  min-height: 100% !important;
}

.verto-main :deep(> section > main) {
  height: 100% !important;
  min-height: 0 !important;
  padding-bottom: var(--verto-page-y) !important;
}

@media (min-width: 480px) {
  .mobile-shell {
    --verto-shell-max-width: 32rem;
  }
}

@media (min-width: 640px) {
  .mobile-shell {
    --verto-shell-max-width: 42rem;
    --verto-page-x: 1rem;
    --verto-page-y: 1rem;
  }
}

@media (min-width: 768px) {
  .mobile-shell {
    --verto-shell-max-width: 48rem;
  }
}

@media (min-width: 1024px) {
  .mobile-shell {
    --verto-shell-max-width: 56rem;
    --verto-page-x: 1.25rem;
    --verto-page-y: 1.25rem;
  }
}
</style>
