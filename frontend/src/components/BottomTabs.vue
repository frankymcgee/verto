<template>
  <nav
    class="bottom-tabs z-40 shrink-0 border-t border-outline-gray-1 bg-surface-white/95 shadow-[0_-8px_24px_rgba(15,23,42,0.08)] backdrop-blur"
    :class="{ 'sidebar-collapsed': sidebarCollapsed }"
    aria-label="Primary navigation"
  >
    <div class="desktop-sidebar-header">
      <div class="desktop-app-icon">
        <img
          v-if="resolvedAppIcon"
          :src="resolvedAppIcon"
          :alt="appName || 'Verto'"
          class="h-full w-full object-cover"
          @error="appIconFailed = true"
        >

        <span v-else>
          {{ appInitials }}
        </span>
      </div>

      <div class="desktop-sidebar-copy min-w-0">
        <p class="truncate text-sm font-semibold text-ink-gray-9">
          {{ appName || 'Verto' }}
        </p>

        <p class="truncate text-xs text-ink-gray-5">
          {{ desktopUserLabel }}
        </p>
      </div>
    </div>

    <div class="bottom-tabs-items mx-auto grid w-full max-w-[var(--verto-shell-max-width,28rem)] grid-cols-5 px-1 pb-[var(--verto-footer-safe-bottom,env(safe-area-inset-bottom,0px))]">
      <RouterLink
        to="/"
        class="navbar-item"
        :class="{ active: isActive('/') }"
        :aria-current="isActive('/') ? 'page' : undefined"
        title="Home"
      >
        <svg
          class="navbar-icon"
          fill="currentColor"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path d="M12 13.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z" />
          <path d="M19.071 3.429h.001c3.905 3.905 3.905 10.237 0 14.142l-5.403 5.403a2.36 2.36 0 0 1-3.336 0l-5.375-5.375-.028-.028c-3.905-3.905-3.905-10.237 0-14.142 3.904-3.905 10.236-3.905 14.141 0ZM5.99 4.489v.001a8.5 8.5 0 0 0 0 12.02l.023.024.002.002 5.378 5.378a.859.859 0 0 0 1.214 0l5.403-5.404a8.5 8.5 0 0 0-.043-11.977A8.5 8.5 0 0 0 5.99 4.489Z" />
        </svg>

        <span class="navbar-label">Home</span>
      </RouterLink>

      <RouterLink
        to="/shifts"
        class="navbar-item"
        :class="{ active: isActive('/shifts') }"
        :aria-current="isActive('/shifts') ? 'page' : undefined"
        title="Shifts"
      >
        <svg
          class="navbar-icon"
          fill="currentColor"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path d="M6.75 0a.75.75 0 0 1 .75.75V3h9V.75a.75.75 0 0 1 1.5 0V3h2.75c.966 0 1.75.784 1.75 1.75v16a1.75 1.75 0 0 1-1.75 1.75H3.25a1.75 1.75 0 0 1-1.75-1.75v-16C1.5 3.784 2.284 3 3.25 3H6V.75A.75.75 0 0 1 6.75 0ZM21 9.5H3v11.25c0 .138.112.25.25.25h17.5a.25.25 0 0 0 .25-.25Zm-17.75-5a.25.25 0 0 0-.25.25V8h18V4.75a.25.25 0 0 0-.25-.25Z" />
        </svg>

        <span class="navbar-label">Shifts</span>
      </RouterLink>

      <button
        type="button"
        class="navbar-item peri-item"
        :class="{ active: isPeriActive, loading: periLoading }"
        :disabled="periLoading"
        :aria-current="isPeriActive ? 'page' : undefined"
        :aria-busy="periLoading ? 'true' : 'false'"
        :aria-label="`Open ${periBotName} AI chat`"
        :title="askPeriLabel"
        @click="openPeriChat"
      >
        <span class="peri-avatar">
          <span class="peri-avatar-frame">
            <img
              v-if="resolvedPeriAvatarUrl"
              :src="resolvedPeriAvatarUrl"
              :alt="`${periBotName} avatar`"
              class="peri-avatar-image"
              @error="periAvatarFailed = true"
            />

            <span
              v-else
              class="peri-avatar-fallback"
            >
              {{ periInitials }}
            </span>
          </span>
        </span>

        <span class="navbar-label">
          {{ periLoading ? 'Loading' : askPeriLabel }}
        </span>
      </button>

      <RouterLink
        to="/forms"
        class="navbar-item"
        :class="{ active: isActive('/forms') }"
        :aria-current="isActive('/forms') ? 'page' : undefined"
        title="Forms"
      >
        <svg
          class="navbar-icon"
          fill="currentColor"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path d="M3 3a2 2 0 0 1 2-2h9.982a2 2 0 0 1 1.414.586l4.018 4.018A2 2 0 0 1 21 7.018V21a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Zm2-.5a.5.5 0 0 0-.5.5v18a.5.5 0 0 0 .5.5h14a.5.5 0 0 0 .5-.5V8.5h-4a2 2 0 0 1-2-2v-4Zm10 0v4a.5.5 0 0 0 .5.5h4a.5.5 0 0 0-.146-.336l-4.018-4.018A.5.5 0 0 0 15 2.5Z" />
        </svg>

        <span class="navbar-label">Forms</span>
      </RouterLink>

      <RouterLink
        :to="generalChatRoute"
        class="navbar-item"
        :class="{ active: isGeneralChatActive }"
        :aria-current="isGeneralChatActive ? 'page' : undefined"
        title="Chat"
      >
        <svg
          class="navbar-icon"
          fill="currentColor"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path d="M1.75 1h12.5c.966 0 1.75.784 1.75 1.75v9.5A1.75 1.75 0 0 1 14.25 14H8.061l-2.574 2.573A1.458 1.458 0 0 1 3 15.543V14H1.75A1.75 1.75 0 0 1 0 12.25v-9.5C0 1.784.784 1 1.75 1ZM1.5 2.75v9.5c0 .138.112.25.25.25h2a.75.75 0 0 1 .75.75v2.19l2.72-2.72a.749.749 0 0 1 .53-.22h6.5a.25.25 0 0 0 .25-.25v-9.5a.25.25 0 0 0-.25-.25H1.75a.25.25 0 0 0-.25.25Z" />
          <path d="M22.5 8.75a.25.25 0 0 0-.25-.25h-3.5a.75.75 0 0 1 0-1.5h3.5c.966 0 1.75.784 1.75 1.75v9.5A1.75 1.75 0 0 1 22.25 20H21v1.543a1.457 1.457 0 0 1-2.487 1.03L15.939 20H10.75A1.75 1.75 0 0 1 9 18.25v-1.465a.75.75 0 0 1 1.5 0v1.465c0 .138.112.25.25.25h5.5a.75.75 0 0 1 .53.22l2.72 2.72v-2.19a.75.75 0 0 1 .75-.75h2a.25.25 0 0 0 .25-.25v-9.5Z" />
        </svg>

        <span class="navbar-label">Chat</span>
      </RouterLink>
    </div>

    <button
      type="button"
      class="desktop-sidebar-collapse"
      :aria-label="sidebarCollapsed ? 'Expand navigation' : 'Collapse navigation'"
      :title="sidebarCollapsed ? 'Expand navigation' : 'Collapse navigation'"
      @click="toggleSidebar"
    >
      <svg
        class="h-4 w-4 shrink-0"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.75"
        aria-hidden="true"
      >
        <rect x="3" y="4" width="18" height="16" rx="2" />
        <path d="M9 4v16" />
        <path
          v-if="sidebarCollapsed"
          d="m13 9 3 3-3 3"
        />
        <path
          v-else
          d="m16 9-3 3 3 3"
        />
      </svg>

      <span class="desktop-sidebar-copy">
        {{ sidebarCollapsed ? 'Expand' : 'Collapse' }}
      </span>
    </button>
  </nav>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiRequest } from '../lib/api'
import { useMobileBoot } from '../lib/mobileBoot'

type FrappeResponse<T> = {
  message: T
}

type PeriChannelResponse = {
  channel?: string
  channel_id?: string
  channel_name?: string
  name?: string
  url?: string
  peri_bot_name?: string
  peri_bot_user?: string
  peri_bot_image?: string
  peri_bot_image_url?: string
}

const route = useRoute()
const router = useRouter()

const {
  loadMobileBoot,
  appName,
  appIconUrl,
  user,
  userFullname,
  defaultChatChannel,
  periBotName,
  periBotImageUrl,
} = useMobileBoot()

const periLoading = ref(false)
const periAvatarFailed = ref(false)
const appIconFailed = ref(false)
const sidebarCollapsed = ref(false)

const SIDEBAR_STORAGE_KEY = 'verto-desktop-sidebar-collapsed'

const generalChannelName = computed(() => {
  return defaultChatChannel.value || 'general'
})

const generalChatRoute = computed(() => {
  return {
    path: '/chat',
    query: {
      channel: generalChannelName.value,
    },
  }
})

const askPeriLabel = computed(() => {
  const name = periBotName.value || 'PERI'

  return `Ask ${name}`
})

const resolvedAppIcon = computed(() => {
  if (appIconFailed.value) {
    return ''
  }

  return appIconUrl.value || ''
})

const appInitials = computed(() => {
  return getInitials(appName.value || 'Verto')
})

const desktopUserLabel = computed(() => {
  return userFullname.value || user.value || 'Signed in'
})

const resolvedPeriAvatarUrl = computed(() => {
  if (periAvatarFailed.value) {
    return ''
  }

  return periBotImageUrl.value || ''
})

const periInitials = computed(() => {
  return getInitials(periBotName.value || 'PERI')
})

const isPeriActive = computed(() => {
  const requestedMode = String(route.query.mode || '').toLowerCase()

  return (
    route.path === '/chat/peri' ||
    (
      route.path.startsWith('/chat') &&
      requestedMode === 'ai'
    )
  )
})

const isGeneralChatActive = computed(() => {
  const requestedChannel = String(route.query.channel || '').toLowerCase()
  const requestedMode = String(route.query.mode || '').toLowerCase()
  const generalChannel = generalChannelName.value.toLowerCase()

  return (
    route.path.startsWith('/chat') &&
    requestedChannel === generalChannel &&
    requestedMode !== 'ai'
  )
})

watch(
  () => periBotImageUrl.value,
  () => {
    periAvatarFailed.value = false
  }
)

watch(
  () => appIconUrl.value,
  () => {
    appIconFailed.value = false
  }
)

onMounted(() => {
  sidebarCollapsed.value = window.localStorage.getItem(SIDEBAR_STORAGE_KEY) === '1'
  loadMobileBoot()
})

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
  window.localStorage.setItem(
    SIDEBAR_STORAGE_KEY,
    sidebarCollapsed.value ? '1' : '0'
  )
}

function isActive(path: string) {
  if (path === '/') {
    return route.path === '/'
  }

  return route.path.startsWith(path)
}

function getInitials(value: string) {
  const words = String(value || '')
    .trim()
    .split(/[ ._-]+/)
    .filter(Boolean)

  if (!words.length) {
    return 'AI'
  }

  if (words.length === 1) {
    return words[0].slice(0, 2).toUpperCase()
  }

  return `${words[0][0]}${words[1][0]}`.toUpperCase()
}

function getPeriChannelName(message: PeriChannelResponse) {
  return (
    message.channel ||
    message.channel_id ||
    message.channel_name ||
    message.name ||
    ''
  )
}

async function openPeriChat() {
  if (periLoading.value) {
    return
  }

  periLoading.value = true

  try {
    await loadMobileBoot()

    const data = await apiRequest<FrappeResponse<PeriChannelResponse>>(
      '/api/method/verto.api.mobile.raven.get_or_create_peri_channel'
    )

    const channel = getPeriChannelName(data.message || {})

    if (!channel) {
      throw new Error(`Could not resolve the ${periBotName.value || 'PERI'} channel.`)
    }

    await router.push({
      path: '/chat/peri',
      query: {
        channel,
        mode: 'ai',
      },
    })
  } catch (err) {
    if (err instanceof Error && err.message === 'Login required') {
      return
    }

    alert(err instanceof Error ? err.message : `Could not open ${periBotName.value || 'PERI'} chat.`)
  } finally {
    periLoading.value = false
  }
}
</script>

<style scoped>
.bottom-tabs {
  --mobile-bottom-tabs-height: calc(68px + var(--verto-footer-safe-bottom, env(safe-area-inset-bottom, 0px)));
  min-height: var(--mobile-bottom-tabs-height);
}

.desktop-sidebar-header,
.desktop-sidebar-collapse {
  display: none;
}

.navbar-item {
  display: flex;
  min-height: 68px;
  align-items: center;
  justify-content: center;
  gap: 4px;
  flex-direction: column;
  color: #6b7280;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.15;
  text-decoration: none;
  -webkit-tap-highlight-color: transparent;
  transition:
    color 0.15s ease,
    transform 0.15s ease,
    opacity 0.15s ease;
}

.navbar-item.active {
  color: #2563eb;
}

.navbar-item:active {
  transform: scale(0.96);
}

.navbar-item:disabled {
  cursor: wait;
  opacity: 0.7;
}

.navbar-icon {
  height: 24px;
  width: 24px;
}

.navbar-label {
  white-space: nowrap;
}

.peri-item {
  border: 0;
  background: transparent;
  padding: 0;
  position: relative;
}

.peri-avatar {
  position: relative;
  display: flex;
  height: 38px;
  width: 38px;
  align-items: center;
  justify-content: center;
  border-radius: 9999px;
}

.peri-avatar-frame {
  display: flex;
  height: 36px;
  width: 36px;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: 9999px;
  background: linear-gradient(135deg, #dbeafe, #eff6ff);
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.28);
  transform: translateY(-8px);
}

.peri-avatar-image {
  height: 100%;
  width: 100%;
  object-fit: cover;
}

.peri-avatar-fallback {
  color: #2563eb;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.peri-avatar::after {
  content: '';
  position: absolute;
  inset: -3px;
  border-radius: 9999px;
  border: 2px solid rgba(37, 99, 235, 0.35);
  animation: peri-pulse 1.8s ease-out infinite;
  transform: translateY(-8px);
}

.peri-item.active .peri-avatar-frame {
  box-shadow: 0 8px 20px rgba(37, 99, 235, 0.42);
}

.peri-item.loading .peri-avatar-frame {
  opacity: 0.65;
}

.peri-item.active .navbar-label {
  color: #2563eb;
}

@keyframes peri-pulse {
  0% {
    opacity: 0.8;
    transform: translateY(-8px) scale(0.9);
  }

  100% {
    opacity: 0;
    transform: translateY(-8px) scale(1.25);
  }
}

@media (min-width: 1024px) {
  .bottom-tabs {
    order: 1;
    display: flex;
    height: 100dvh;
    min-height: 100dvh;
    width: 15rem;
    flex-direction: column;
    border-top: 0;
    border-right: 1px solid #e5e7eb;
    background: rgba(249, 250, 251, 0.98);
    box-shadow: 8px 0 24px rgba(15, 23, 42, 0.05);
    transition: width 0.2s ease;
  }

  .bottom-tabs.sidebar-collapsed {
    width: 4.75rem;
  }

  .desktop-sidebar-header {
    display: flex;
    min-height: 4.5rem;
    align-items: center;
    gap: 0.75rem;
    border-bottom: 1px solid #e5e7eb;
    padding: 0.875rem 1rem;
  }

  .desktop-app-icon {
    display: flex;
    height: 2.25rem;
    width: 2.25rem;
    flex-shrink: 0;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    border-radius: 0.75rem;
    background: #e5e7eb;
    color: #374151;
    font-size: 0.75rem;
    font-weight: 700;
  }

  .bottom-tabs-items {
    display: flex;
    max-width: none;
    flex: 1;
    flex-direction: column;
    gap: 0.25rem;
    padding: 0.75rem;
  }

  .navbar-item {
    min-height: 2.75rem;
    flex-direction: row;
    justify-content: flex-start;
    gap: 0.75rem;
    border: 1px solid transparent;
    border-radius: 0.75rem;
    padding: 0.625rem 0.75rem;
    font-size: 0.875rem;
    font-weight: 500;
  }

  .navbar-item:hover {
    background: rgba(255, 255, 255, 0.8);
    color: #1f2937;
  }

  .navbar-item.active {
    border-color: #e5e7eb;
    background: #ffffff;
    color: #2563eb;
    box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06);
  }

  .navbar-icon {
    height: 1.25rem;
    width: 1.25rem;
    flex-shrink: 0;
  }

  .peri-avatar {
    height: 1.25rem;
    width: 1.25rem;
    flex-shrink: 0;
  }

  .peri-avatar-frame {
    height: 1.5rem;
    width: 1.5rem;
    box-shadow: none;
    transform: none;
  }

  .peri-avatar::after {
    display: none;
  }

  .desktop-sidebar-collapse {
    display: flex;
    min-height: 2.75rem;
    align-items: center;
    gap: 0.75rem;
    margin: 0.75rem;
    border-radius: 0.75rem;
    padding: 0.625rem 0.75rem;
    color: #4b5563;
    font-size: 0.875rem;
    font-weight: 500;
    text-align: left;
    transition: background-color 0.15s ease, color 0.15s ease;
  }

  .desktop-sidebar-collapse:hover {
    background: #ffffff;
    color: #111827;
  }

  .sidebar-collapsed .desktop-sidebar-header,
  .sidebar-collapsed .navbar-item,
  .sidebar-collapsed .desktop-sidebar-collapse {
    justify-content: center;
  }

  .sidebar-collapsed .desktop-sidebar-header {
    padding-left: 0.75rem;
    padding-right: 0.75rem;
  }

  .sidebar-collapsed .desktop-sidebar-copy,
  .sidebar-collapsed .navbar-label {
    display: none;
  }

  .sidebar-collapsed .bottom-tabs-items {
    padding-left: 0.5rem;
    padding-right: 0.5rem;
  }

  .sidebar-collapsed .navbar-item,
  .sidebar-collapsed .desktop-sidebar-collapse {
    padding-left: 0.625rem;
    padding-right: 0.625rem;
  }
}

@media (prefers-reduced-motion: reduce) {
  .bottom-tabs {
    transition: none;
  }
}
</style>
