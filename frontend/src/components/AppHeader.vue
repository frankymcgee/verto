<!-- VERTO_APP_HEADER_PUSH_TOGGLE_2026_08_10 -->
<template>
  <header
    :class="props.compact
      ? 'app-profile-compact pointer-events-none fixed z-40'
      : 'app-header-safe z-40 shrink-0 border-b border-outline-gray-1 bg-surface-white/95 backdrop-blur'"
  >
    <div
      :class="props.compact
        ? 'pointer-events-auto relative'
        : 'mx-auto flex w-full max-w-[var(--verto-shell-max-width,28rem)] items-center justify-between gap-3 px-[var(--verto-page-x,0.75rem)] py-2'"
    >
      <div
        v-if="!props.compact"
        class="flex min-w-0 items-center gap-2"
      >
        <div class="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-surface-gray-2">
          <img
            v-if="resolvedAppIcon"
            :src="resolvedAppIcon"
            :alt="appName"
            class="h-full w-full object-cover"
            @error="iconFailed = true"
          />

          <span
            v-else
            class="text-sm font-semibold text-ink-gray-7"
          >
            {{ appInitials }}
          </span>
        </div>

        <div class="min-w-0">
          <p class="truncate text-xs text-ink-gray-5">
            {{ appName }}
          </p>

          <h1 class="truncate text-base font-semibold text-ink-gray-9">
            {{ pageTitle }}
          </h1>
        </div>
      </div>

      <div class="relative shrink-0">
        <button
          type="button"
          class="flex h-9 w-9 items-center justify-center overflow-hidden rounded-full border-2 bg-surface-gray-1 text-sm font-semibold text-ink-gray-8 shadow-sm transition-colors active:scale-95"
          :class="avatarStatusClass"
          aria-label="Open profile menu"
          :aria-expanded="menuOpen"
          @click="toggleMenu"
        >
          <img
            v-if="resolvedUserImage"
            :src="resolvedUserImage"
            :alt="userFullname || user || 'User avatar'"
            class="h-full w-full object-cover"
            @error="userImageFailed = true"
          />

          <span v-else>
            {{ userInitials }}
          </span>
        </button>

        <div
          v-if="menuOpen"
          class="absolute right-0 z-50 mt-2 w-64 overflow-hidden rounded-xl border border-outline-gray-1 bg-surface-white shadow-lg"
        >
          <div class="border-b border-outline-gray-1 px-3 py-2">
            <div class="flex items-center gap-2">
              <div
                class="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-full border-2 bg-surface-gray-2 text-sm font-semibold text-ink-gray-8 transition-colors"
                :class="avatarStatusClass"
              >
                <img
                  v-if="resolvedUserImage"
                  :src="resolvedUserImage"
                  :alt="userFullname || user || 'User avatar'"
                  class="h-full w-full object-cover"
                  @error="userImageFailed = true"
                />

                <span v-else>
                  {{ userInitials }}
                </span>
              </div>

              <div class="min-w-0">
                <p class="truncate text-sm font-medium text-ink-gray-9">
                  {{ userFullname }}
                </p>

                <p
                  v-if="user"
                  class="truncate text-xs text-ink-gray-5"
                >
                  {{ user }}
                </p>
              </div>
            </div>
          </div>

          <div class="border-b border-outline-gray-1 px-3 py-2.5">
            <button
              type="button"
              role="switch"
              class="flex w-full items-center justify-between gap-3 text-left disabled:cursor-not-allowed disabled:opacity-60"
              :aria-checked="subscribed"
              :aria-label="subscribed ? 'Disable notifications' : 'Enable notifications'"
              :disabled="notificationToggleDisabled"
              @click="handleNotificationToggle"
            >
              <span class="min-w-0">
                <span class="block text-sm font-medium text-ink-gray-9">
                  Notifications
                </span>

                <span class="mt-0.5 block text-xs leading-4 text-ink-gray-5">
                  {{ notificationStatus }}
                </span>
              </span>

              <span
                class="relative inline-flex h-6 w-10 shrink-0 rounded-full p-0.5 transition-colors"
                :class="subscribed ? 'bg-blue-600' : 'bg-surface-gray-4'"
                aria-hidden="true"
              >
                <span
                  class="block h-5 w-5 rounded-full bg-white shadow-sm transition-transform"
                  :class="subscribed ? 'translate-x-4' : 'translate-x-0'"
                />
              </span>
            </button>

            <p
              v-if="pushError"
              class="mt-2 text-xs leading-4 text-red-600"
            >
              {{ pushError }}
            </p>
          </div>

          <div class="border-b border-outline-gray-1 px-3 py-2.5">
            <div class="flex items-start justify-between gap-3">
              <span class="min-w-0">
                <span class="block text-sm font-medium text-ink-gray-9">
                  Offline data
                </span>

                <span class="mt-0.5 block text-xs leading-4 text-ink-gray-5">
                  {{ offlineDataStatus }}
                </span>
              </span>

              <button
                type="button"
                class="shrink-0 rounded-lg bg-surface-gray-2 px-2.5 py-1.5 text-xs font-semibold text-ink-gray-8 active:scale-95 disabled:cursor-not-allowed disabled:opacity-60"
                :disabled="!offlineIsOnline || offlineIsPriming || offlineIsSyncing"
                @click="handleOfflineRefresh"
              >
                {{ offlineIsPriming ? 'Refreshing' : 'Refresh' }}
              </button>
            </div>

            <button
              v-if="offlineSummary.total > 0"
              type="button"
              class="mt-2 flex w-full items-center justify-between gap-3 rounded-lg bg-blue-50 px-2.5 py-2 text-left text-xs font-semibold text-blue-800 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
              :disabled="!offlineIsOnline || offlineIsSyncing || offlineIsPriming"
              @click="syncNow"
            >
              <span>
                {{ offlineIsSyncing ? 'Syncing offline work…' : 'Sync offline work' }}
              </span>

              <span>
                {{ offlineSummary.total }}
              </span>
            </button>

            <p
              v-if="offlineRefreshError"
              class="mt-2 text-xs leading-4 text-red-600"
            >
              {{ offlineRefreshError }}
            </p>
          </div>

          <button
            type="button"
            class="block w-full px-3 py-2 text-left text-sm text-ink-gray-8 hover:bg-surface-gray-1"
            @click="openAppList"
          >
            Apps
          </button>

          <button
            type="button"
            class="block w-full px-3 py-2 text-left text-sm text-ink-gray-8 hover:bg-surface-gray-1"
            @click="reloadApp"
          >
            Reload app
          </button>

          <button
            type="button"
            class="block w-full px-3 py-2 text-left text-sm text-ink-gray-8 hover:bg-surface-gray-1"
            @click="openProfile"
          >
            My profile
          </button>

          <button
            type="button"
            class="block w-full px-3 py-2 text-left text-sm text-ink-gray-8 hover:bg-surface-gray-1"
            @click="openLearning"
          >
            Learning
          </button>

          <button
            type="button"
            class="block w-full px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50"
            @click="logout"
          >
            Log out
          </button>
        </div>
      </div>
    </div>
  </header>

  <button
    v-if="menuOpen"
    type="button"
    class="fixed inset-0 z-30 cursor-default bg-transparent"
    aria-label="Close menu"
    @click="menuOpen = false"
  />
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useMobileBoot } from '../lib/mobileBoot'
import { openAppBrowser } from '../lib/appBrowser'
import { useOfflineSync } from '../pwa/useOfflineSync'
import { usePushNotifications } from '../pwa/usePushNotifications'

const props = withDefaults(
  defineProps<{
    compact?: boolean
  }>(),
  {
    compact: false,
  }
)

const route = useRoute()

const {
  appName,
  appIconUrl,
  user,
  userFullname,
  userImageUrl,
  reloadMobileBoot,
} = useMobileBoot()

const {
  loading: pushLoading,
  enabling: pushEnabling,
  disabling: pushDisabling,
  configured: pushConfigured,
  supported: pushSupported,
  subscribed,
  permission: pushPermission,
  error: pushError,
  needsIosInstall,
  initialisePushNotifications,
  enablePushNotifications,
  disablePushNotifications,
} = usePushNotifications()

const {
  isOnline: offlineIsOnline,
  isSyncing: offlineIsSyncing,
  isPriming: offlineIsPriming,
  lastOfflineRefreshAt,
  offlineRefreshError,
  summary: offlineSummary,
  primeNow,
  syncNow,
} = useOfflineSync()

const menuOpen = ref(false)
const iconFailed = ref(false)
const userImageFailed = ref(false)

const routeTitles: Record<string, string> = {
  '/': 'Home',
  '/forms': 'Forms',
  '/shifts': 'Shifts',
  '/chat': 'Chat',
  '/chat/peri': 'Ask PERI',
}

const pageTitle = computed(() => {
  if (typeof route.meta?.title === 'string') {
    return route.meta.title
  }

  if (route.path.startsWith('/new/')) {
    return 'New Form'
  }

  if (route.path.startsWith('/edit/')) {
    return 'Edit Form'
  }

  return routeTitles[route.path] || 'Verto'
})

const resolvedAppIcon = computed(() => {
  if (iconFailed.value) {
    return ''
  }

  return appIconUrl.value || ''
})

const resolvedUserImage = computed(() => {
  if (userImageFailed.value) {
    return ''
  }

  return userImageUrl.value || ''
})

const appInitials = computed(() => {
  return getInitials(appName.value || 'Verto')
})

const userInitials = computed(() => {
  return getInitials(userFullname.value || user.value || 'User')
})

const notificationBusy = computed(() => {
  return pushLoading.value || pushEnabling.value || pushDisabling.value
})

const notificationToggleDisabled = computed(() => {
  if (subscribed.value) {
    return notificationBusy.value
  }

  return (
    notificationBusy.value ||
    needsIosInstall.value ||
    !pushSupported.value ||
    !pushConfigured.value ||
    pushPermission.value === 'denied'
  )
})

const notificationStatus = computed(() => {
  if (pushLoading.value) {
    return 'Checking this device…'
  }

  if (pushEnabling.value) {
    return 'Enabling…'
  }

  if (pushDisabling.value) {
    return 'Disabling…'
  }

  if (needsIosInstall.value) {
    return 'Add Verto to the Home Screen first'
  }

  if (!pushSupported.value) {
    return 'Not supported on this device'
  }

  if (!pushConfigured.value) {
    return 'Not configured for this site'
  }

  if (pushPermission.value === 'denied') {
    return 'Blocked in device settings'
  }

  return subscribed.value
    ? 'Enabled on this device'
    : 'Disabled on this device'
})

const offlineDataStatus = computed(() => {
  if (!offlineIsOnline.value) {
    return offlineSummary.value.total > 0
      ? `${offlineSummary.value.total} item${offlineSummary.value.total === 1 ? '' : 's'} saved offline`
      : 'Offline mode active'
  }

  if (offlineIsSyncing.value) {
    return 'Syncing saved work…'
  }

  if (offlineIsPriming.value) {
    return 'Updating forms and shifts…'
  }

  if (offlineSummary.value.failed > 0) {
    return `${offlineSummary.value.failed} item${offlineSummary.value.failed === 1 ? '' : 's'} failed to sync`
  }

  if (offlineSummary.value.total > 0) {
    return `${offlineSummary.value.total} item${offlineSummary.value.total === 1 ? '' : 's'} waiting to sync`
  }

  if (!lastOfflineRefreshAt.value) {
    return 'Not prepared on this device'
  }

  const date = new Date(lastOfflineRefreshAt.value)

  if (Number.isNaN(date.getTime())) {
    return 'Ready for offline use'
  }

  const formatted = new Intl.DateTimeFormat(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date)

  return `Updated ${formatted}`
})

const avatarStatusClass = computed(() => {
  if (!offlineIsOnline.value) {
    return 'border-amber-400'
  }

  if (offlineSummary.value.failed > 0 || offlineRefreshError.value) {
    return 'border-red-500'
  }

  if (
    offlineIsSyncing.value ||
    offlineIsPriming.value ||
    offlineSummary.value.total > 0
  ) {
    return 'border-blue-500'
  }

  if (lastOfflineRefreshAt.value) {
    return 'border-green-500'
  }

  return 'border-outline-gray-2'
})

function handleOfflineRefresh() {
  void primeNow()
}

watch(
  () => appIconUrl.value,
  () => {
    iconFailed.value = false
  }
)

watch(
  () => userImageUrl.value,
  () => {
    userImageFailed.value = false
  }
)

watch(
  () => route.fullPath,
  () => {
    menuOpen.value = false
  }
)

function getInitials(value: string) {
  const words = String(value || '')
    .trim()
    .split(/\s+/)
    .filter(Boolean)

  if (!words.length) {
    return 'U'
  }

  if (words.length === 1) {
    return words[0].slice(0, 2).toUpperCase()
  }

  return `${words[0][0]}${words[1][0]}`.toUpperCase()
}

function toggleMenu() {
  menuOpen.value = !menuOpen.value

  if (menuOpen.value) {
    void initialisePushNotifications(true)
  }
}

async function handleNotificationToggle() {
  if (subscribed.value) {
    await disablePushNotifications()
    return
  }

  await enablePushNotifications()
}

async function clearBrowserCaches() {
  if ('caches' in window) {
    const cacheNames = await caches.keys()

    await Promise.all(
      cacheNames.map((cacheName) => caches.delete(cacheName))
    )
  }
}

async function reloadApp() {
  menuOpen.value = false

  try {
    await reloadMobileBoot()
    await clearBrowserCaches()
  } finally {
    window.location.reload()
  }
}

function openProfile() {
  menuOpen.value = false
  openAppBrowser({
    url: '/app/user-profile',
    title: 'My profile',
  })
}

function openLearning() {
  menuOpen.value = false
  openAppBrowser({
    url: '/lms/',
    title: 'Learning',
  })
}

function openAppList() {
  menuOpen.value = false
  openAppBrowser({
    url: '/apps',
    title: 'Apps',
  })
}

function logout() {
  menuOpen.value = false
  window.location.href = '/logout'
}
</script>

<style scoped>
.app-header-safe {
  padding-top: var(--verto-header-safe-top, max(env(safe-area-inset-top, 0px), 20px));
}

.app-profile-compact {
  right: max(env(safe-area-inset-right, 0px), 0.75rem);
  top: max(env(safe-area-inset-top, 0px), 0.75rem);
}
</style>
