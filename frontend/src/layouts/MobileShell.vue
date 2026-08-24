<!-- VERTO_MOBILE_SHELL_OFFLINE_SYNC_2026_08_24 -->
<template>
  <div
    class="mobile-shell min-h-[100dvh] overflow-hidden bg-gray-50 text-gray-900"
    @click.capture="handleAppBrowserLinkClick"
  >
    <div class="mobile-shell-frame mx-auto flex h-[100dvh] min-h-[100dvh] w-full flex-col overflow-hidden bg-gray-50">
      <div class="mobile-shell-content flex min-h-0 min-w-0 flex-1 flex-col">
        <div class="mobile-shell-header">
          <AppHeader />
        </div>
        <OfflineSyncStatus />

        <main
          ref="mainEl"
          class="mobile-shell-main min-h-0 flex-1 overflow-y-auto overscroll-contain"
        >
          <div class="mobile-shell-page mx-auto h-full w-full max-w-[var(--verto-shell-max-width,28rem)]">
            <router-view />
          </div>
        </main>
      </div>

      <BottomTabs />
    </div>

    <AppBrowserDrawer />
    <PwaUpdatePrompt />
    <PwaInstallPrompt />
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '../components/AppHeader.vue'
import BottomTabs from '../components/BottomTabs.vue'
import AppBrowserDrawer from '../components/AppBrowserDrawer.vue'
import OfflineSyncStatus from '../components/OfflineSyncStatus.vue'
import PwaUpdatePrompt from '../components/PwaUpdatePrompt.vue'
import PwaInstallPrompt from '../components/PwaInstallPrompt.vue'
import { handleAppBrowserLinkClick } from '../lib/appBrowser'
import { usePushNotifications } from '../pwa/usePushNotifications'

const route = useRoute()
const mainEl = ref<HTMLElement | null>(null)
const { initialisePushNotifications } = usePushNotifications()

onMounted(() => {
  void initialisePushNotifications()
})

watch(
  () => route.fullPath,
  async () => {
    await nextTick()

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
  --verto-header-safe-top: max(env(safe-area-inset-top, 0px), 20px);
  --verto-footer-safe-bottom: env(safe-area-inset-bottom, 0px);

  padding-left: env(safe-area-inset-left, 0px);
  padding-right: env(safe-area-inset-right, 0px);
}

.mobile-shell-frame {
  max-width: var(--verto-shell-max-width);
}

.mobile-shell-content {
  isolation: isolate;
}

.mobile-shell-header {
  position: relative;
  z-index: 50;
  flex-shrink: 0;
  overflow: visible;
}

.mobile-shell-main {
  position: relative;
  z-index: 0;
  -webkit-overflow-scrolling: touch;
}

@media (min-width: 480px) {
  .mobile-shell {
    --verto-shell-max-width: 32rem;
    --verto-page-x: 1rem;
    --verto-page-y: 1rem;
  }
}

@media (min-width: 640px) {
  .mobile-shell {
    --verto-shell-max-width: 42rem;
    --verto-page-x: 1.25rem;
    --verto-page-y: 1.25rem;
  }
}

@media (min-width: 768px) {
  .mobile-shell {
    --verto-shell-max-width: 48rem;
    --verto-page-x: 1.5rem;
    --verto-page-y: 1.5rem;
  }
}

@media (min-width: 1024px) {
  .mobile-shell-header {
    display: none;
  }

  .mobile-shell {
    --verto-shell-max-width: 90rem;
    --verto-page-x: 1.75rem;
    --verto-page-y: 1.75rem;
    --verto-header-safe-top: 0px;
  }

  .mobile-shell-frame {
    max-width: none;
    flex-direction: row;
  }

  .mobile-shell-content {
    order: 2;
  }

  .mobile-shell-page {
    min-height: 100%;
  }
}

@media (min-width: 1440px) {
  .mobile-shell {
    --verto-page-x: 2.25rem;
    --verto-page-y: 2rem;
  }
}
</style>
