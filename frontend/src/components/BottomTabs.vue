<template>
  <nav
    class="bottom-tabs fixed inset-x-0 bottom-0 z-50 border-t border-outline-gray-1 bg-surface-white/95 shadow-[0_-8px_24px_rgba(15,23,42,0.08)] backdrop-blur"
    aria-label="Primary mobile navigation"
  >
    <div class="mx-auto grid max-w-md grid-cols-5 px-1 pb-[env(safe-area-inset-bottom)]">
      <RouterLink
        to="/"
        class="navbar-item"
        :class="{ active: isActive('/') }"
        :aria-current="isActive('/') ? 'page' : undefined"
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
        :class="{ loading: periLoading }"
        :disabled="periLoading"
        :aria-busy="periLoading ? 'true' : 'false'"
        aria-label="Open PERI chat"
        @click="openPeri"
      >
        <span class="peri-avatar">
          <span
            class="peri-avatar-frame"
            :style="{ backgroundImage: `url('${periAvatarUrl}')` }"
          />
        </span>

        <span class="navbar-label">
          {{ periLoading ? 'Loading' : 'Ask PERI' }}
        </span>
      </button>

      <RouterLink
        to="/forms"
        class="navbar-item"
        :class="{ active: isActive('/forms') }"
        :aria-current="isActive('/forms') ? 'page' : undefined"
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

      <a
        href="/raven"
        class="navbar-item"
        target="_self"
        rel="noopener noreferrer"
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
      </a>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { apiRequest } from '../lib/api'

type FrappeResponse<T> = {
  message: T
}

type PeriResponse = {
  channel: string
  url: string
}

const route = useRoute()
const periLoading = ref(false)

const periAvatarUrl = '/private/files/ChatGPT Image Jun 23, 2025, 10_20_03 AM.png'

function isActive(path: string) {
  if (path === '/') {
    return route.path === '/'
  }

  return route.path.startsWith(path)
}

async function openPeri() {
  if (periLoading.value) {
    return
  }

  periLoading.value = true

  try {
    const data = await apiRequest<FrappeResponse<PeriResponse>>(
      '/api/method/verto.api.mobile.raven.get_or_create_peri_channel'
    )

    window.location.href = data.message.url
  } catch (err) {
    if (err instanceof Error && err.message === 'Login required') {
      return
    }

    alert(err instanceof Error ? err.message : 'PERI chat is still loading, please try again.')
  } finally {
    periLoading.value = false
  }
}
</script>

<style scoped>
.bottom-tabs {
  --mobile-bottom-tabs-height: calc(68px + env(safe-area-inset-bottom));
  min-height: var(--mobile-bottom-tabs-height);
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
  display: block;
  height: 36px;
  width: 36px;
  border-radius: 9999px;
  background-position: center;
  background-size: cover;
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.28);
  transform: translateY(-8px);
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

.peri-item.loading .peri-avatar-frame {
  opacity: 0.65;
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
</style>