<!-- VERTO_FRAPPE_UI_V1_RESPONSIVE_SHELL -->
<script setup lang="ts">
import { onMounted } from 'vue'
import { useMediaQuery } from '@vueuse/core'
import {
  DesktopShell as FrappeDesktopShell,
  MobileShell as FrappeMobileShell,
} from 'frappe-ui'
import AppHeader from '../components/AppHeader.vue'
import BottomTabs from '../components/BottomTabs.vue'
import AppBrowserDrawer from '../components/AppBrowserDrawer.vue'
import PwaUpdatePrompt from '../components/PwaUpdatePrompt.vue'
import PwaInstallPrompt from '../components/PwaInstallPrompt.vue'
import { handleAppBrowserLinkClick } from '../lib/appBrowser'
import { usePushNotifications } from '../pwa/usePushNotifications'

const isDesktop = useMediaQuery('(min-width: 1024px)')
const { initialisePushNotifications } = usePushNotifications()

onMounted(() => {
  void initialisePushNotifications()
})
</script>

<template>
  <div
    class="verto-app-shell bg-surface-gray-1 text-ink-gray-9"
    @click.capture="handleAppBrowserLinkClick"
  >
    <FrappeDesktopShell
      v-if="isDesktop"
      class="h-dvh"
    >
      <template #sidebar>
        <BottomTabs />
      </template>

      <OfflineSyncStatus />

      <div class="mx-auto min-h-full w-full max-w-[90rem]">
        <router-view />
      </div>
    </FrappeDesktopShell>

    <FrappeMobileShell v-else>
      <AppHeader />
      <OfflineSyncStatus />

      <div class="mx-auto min-h-full w-full max-w-3xl">
        <router-view />
      </div>

      <template #nav>
        <BottomTabs />
      </template>
    </FrappeMobileShell>

    <AppBrowserDrawer />
    <PwaUpdatePrompt />
    <PwaInstallPrompt />
  </div>
</template>

<style scoped>
.verto-app-shell {
  --verto-shell-max-width: 28rem;
  --verto-page-x: 0.75rem;
  --verto-page-y: 0.75rem;
  --verto-header-safe-top: max(env(safe-area-inset-top, 0px), 20px);
  --verto-footer-safe-bottom: env(safe-area-inset-bottom, 0px);

  min-height: 100dvh;
  padding-left: env(safe-area-inset-left, 0px);
  padding-right: env(safe-area-inset-right, 0px);
}

@media (min-width: 480px) {
  .verto-app-shell {
    --verto-shell-max-width: 32rem;
    --verto-page-x: 1rem;
    --verto-page-y: 1rem;
  }
}

@media (min-width: 640px) {
  .verto-app-shell {
    --verto-shell-max-width: 42rem;
    --verto-page-x: 1.25rem;
    --verto-page-y: 1.25rem;
  }
}

@media (min-width: 768px) {
  .verto-app-shell {
    --verto-shell-max-width: 48rem;
    --verto-page-x: 1.5rem;
    --verto-page-y: 1.5rem;
  }
}

@media (min-width: 1024px) {
  .verto-app-shell {
    --verto-shell-max-width: 90rem;
    --verto-page-x: 1.75rem;
    --verto-page-y: 1.75rem;
    --verto-header-safe-top: 0px;
  }
}

@media (min-width: 1440px) {
  .verto-app-shell {
    --verto-page-x: 2.25rem;
    --verto-page-y: 2rem;
  }
}
</style>
