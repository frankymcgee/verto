<!-- VERTO_MOBILE_SHELL_OFFLINE_SYNC_2026_08_24 -->
<template>
  <div
    class="mobile-shell overflow-hidden bg-surface-gray-1 text-ink-gray-9"
    :class="{ 'mobile-shell--flow': isFlowPeriPage }"
    @click.capture="handleAppBrowserLinkClick"
  >
    <div class="mobile-shell-frame mx-auto flex w-full flex-col overflow-hidden bg-surface-gray-1">
      <div class="mobile-shell-content flex min-h-0 min-w-0 flex-1 flex-col">
        <div class="mobile-shell-header">
          <AppHeader />
        </div>
        <OfflineSyncStatus />
        <MissingHoursReminder />

        <main
          ref="mainEl"
          class="mobile-shell-main min-h-0 flex-1 overflow-x-hidden overflow-y-auto"
          :class="{
            'mobile-shell-main--interactive': route.name === 'project-gantt' || route.name === 'project-map',
            'mobile-shell-main--flow': isFlowPeriPage,
          }"
        >
          <div class="mobile-shell-page mx-auto h-full w-full max-w-[var(--verto-shell-max-width,28rem)]">
            <router-view />
          </div>
        </main>
      </div>

      <PwaUpdatePrompt />
      <BottomTabs />
    </div>

    <AppBrowserDrawer />
    <PwaInstallPrompt />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, provide, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '../components/AppHeader.vue'
import BottomTabs from '../components/BottomTabs.vue'
import AppBrowserDrawer from '../components/AppBrowserDrawer.vue'
import OfflineSyncStatus from '../components/OfflineSyncStatus.vue'
import MissingHoursReminder from '../components/MissingHoursReminder.vue'
import PwaUpdatePrompt from '../components/PwaUpdatePrompt.vue'
import PwaInstallPrompt from '../components/PwaInstallPrompt.vue'
import { handleAppBrowserLinkClick } from '../lib/appBrowser'
import { isAndroidDevice, isStandalonePwa } from '../pwa/displayMode'
import { clearNotificationIndicators } from '../pwa/clearNotificationIndicators'
import { usePushNotifications } from '../pwa/usePushNotifications'
import { useMobileBoot } from '../lib/mobileBoot'
import { flowEditingKey } from '../lib/flowFrame'

const route = useRoute()
const mainEl = ref<HTMLElement | null>(null)
const { initialisePushNotifications } = usePushNotifications()
const useAndroidBrowserViewport = isAndroidDevice() && !isStandalonePwa()
const { periChatVersion } = useMobileBoot()
const isFlowPeriPage = computed(() => route.path === '/chat/peri' && periChatVersion.value === 'Flow')
let viewportSyncInstalled = false
let flowEditing = false
let flowIdleHeight = 0
let flowViewportWidth = 0
provide(flowEditingKey, editing => {
  flowEditing = editing
  syncAndroidBrowserViewport()
})

function syncAndroidBrowserViewport() {
  if (!useAndroidBrowserViewport && !isFlowPeriPage.value) {
    return
  }

  const viewport = window.visualViewport
  // A pinch zoom also reduces visualViewport.height. Keep the layout at its
  // unzoomed size, instead of squeezing it into the magnified screen.
  const scale = isFlowPeriPage.value ? viewport?.scale || 1 : 1
  const viewportHeight = viewport ? viewport.height * scale : window.innerHeight

  if (isFlowPeriPage.value) {
    const root = document.documentElement
    if (!flowIdleHeight || !flowEditing) flowIdleHeight = viewportHeight
    if (flowViewportWidth && flowViewportWidth !== window.innerWidth) {
      flowIdleHeight = Math.max(viewportHeight, window.innerHeight)
    }
    flowViewportWidth = window.innerWidth
    const keyboardVisible = flowEditing && flowIdleHeight - viewportHeight > 100
    if (!keyboardVisible) {
      // At rest, CSS's dynamic viewport fills the app reliably. A fixed pixel
      // height from visualViewport can leave Safari's toolbar-sized gap below it.
      root.style.removeProperty('--verto-viewport-height')
      root.style.removeProperty('--verto-viewport-top')
      root.style.removeProperty('--verto-flow-footer-safe-bottom')
      return
    }
    root.style.setProperty('--verto-flow-footer-safe-bottom', '0px')
  }

  if (viewportHeight > 0) {
    document.documentElement.style.setProperty(
      '--verto-viewport-height',
      `${Math.round(viewportHeight)}px`
    )
  }

  // Safari can pan the visual viewport as it focuses a field inside a frame.
  // Follow that offset as well as keyboard height so the header stays in view.
  if (isFlowPeriPage.value && scale === 1) {
    document.documentElement.style.setProperty(
      '--verto-viewport-top', `${Math.max(0, viewport?.offsetTop || 0)}px`
    )
  }
}

function installAndroidBrowserViewportSync() {
  if (viewportSyncInstalled || (!useAndroidBrowserViewport && !isFlowPeriPage.value)) {
    return
  }

  syncAndroidBrowserViewport()
  viewportSyncInstalled = true
  window.addEventListener('resize', syncAndroidBrowserViewport, { passive: true })
  window.visualViewport?.addEventListener('resize', syncAndroidBrowserViewport, { passive: true })
  window.visualViewport?.addEventListener('scroll', syncAndroidBrowserViewport, { passive: true })
}

function removeAndroidBrowserViewportSync() {
  viewportSyncInstalled = false
  window.removeEventListener('resize', syncAndroidBrowserViewport)
  window.visualViewport?.removeEventListener('resize', syncAndroidBrowserViewport)
  window.visualViewport?.removeEventListener('scroll', syncAndroidBrowserViewport)
  document.documentElement.style.removeProperty('--verto-viewport-height')
  document.documentElement.style.removeProperty('--verto-viewport-top')
  document.documentElement.style.removeProperty('--verto-flow-footer-safe-bottom')
  flowEditing = false
  flowIdleHeight = 0
  flowViewportWidth = 0
}

function clearForegroundNotifications() {
  void clearNotificationIndicators()
}

onMounted(() => {
  document.documentElement.classList.toggle('verto-flow-active', isFlowPeriPage.value)
  clearForegroundNotifications()
  document.addEventListener('visibilitychange', clearForegroundNotifications)
  window.addEventListener('focus', clearForegroundNotifications)
  installAndroidBrowserViewportSync()
  void initialisePushNotifications()
})

onBeforeUnmount(() => {
  document.documentElement.classList.remove('verto-flow-active')
  document.removeEventListener('visibilitychange', clearForegroundNotifications)
  window.removeEventListener('focus', clearForegroundNotifications)
  removeAndroidBrowserViewportSync()
})

watch(isFlowPeriPage, () => {
  document.documentElement.classList.toggle('verto-flow-active', isFlowPeriPage.value)
  removeAndroidBrowserViewportSync()
  installAndroidBrowserViewportSync()
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

  min-height: var(--verto-viewport-height, 100dvh);
  padding-left: env(safe-area-inset-left, 0px);
  padding-right: env(safe-area-inset-right, 0px);
}

.mobile-shell-frame {
  height: var(--verto-viewport-height, 100dvh);
  min-height: var(--verto-viewport-height, 100dvh);
  max-width: var(--verto-shell-max-width);
}

.mobile-shell--flow {
  --verto-footer-safe-bottom: var(--verto-flow-footer-safe-bottom, env(safe-area-inset-bottom, 0px));
  position: fixed;
  top: var(--verto-viewport-top, 0px);
  right: 0;
  bottom: 0;
  left: 0;
  height: var(--verto-viewport-height, auto);
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: clip;
}

/* Fill the fixed inset box. A second 100dvh height can end above its bottom
   in an installed iOS app, leaving the page background below the tab bar. */
.mobile-shell--flow > .mobile-shell-frame {
  flex: 1 1 0;
  height: auto;
  min-height: 0;
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
  touch-action: pan-y;
  overscroll-behavior-y: auto;
  -webkit-overflow-scrolling: touch;
}

.mobile-shell-main--interactive {
  touch-action: auto;
}

.mobile-shell-main--flow {
  overflow: clip;
  touch-action: auto;
}

.mobile-shell-main--flow .mobile-shell-page {
  max-width: none;
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
  .mobile-shell--flow :deep(.bottom-tabs) {
    height: auto;
    min-height: 0;
  }

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
