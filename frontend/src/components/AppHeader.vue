<template>
  <header class="sticky top-0 z-40 border-b border-outline-gray-1 bg-surface-white/95 backdrop-blur">
    <div class="mx-auto flex h-14 max-w-md items-center justify-between gap-3 px-3">
      <!-- Left: App icon + page title -->
      <div class="flex min-w-0 items-center gap-3">
        <div class="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-surface-gray-2">
          <img
            v-if="appIcon"
            :src="appIcon"
            alt="App icon"
            class="h-full w-full object-cover"
          />

          <span
            v-else
            class="text-sm font-semibold text-ink-gray-8"
          >
            {{ appInitials }}
          </span>
        </div>

        <div class="min-w-0">
          <p class="truncate text-base font-semibold text-ink-gray-9">
            {{ pageTitle }}
          </p>

          <p
            v-if="pageSubtitle"
            class="truncate text-xs text-ink-gray-5"
          >
            {{ pageSubtitle }}
          </p>
        </div>
      </div>

      <!-- Right: user avatar menu -->
      <Dropdown :options="menuOptions">
        <template #default="{ open }">
          <button
            type="button"
            class="flex h-10 w-10 items-center justify-center rounded-full transition hover:bg-surface-gray-1 active:scale-95"
            :class="{ 'bg-surface-gray-1': open }"
            aria-label="Open user menu"
          >
            <Avatar
              :image="userImage"
              :label="avatarLabel"
              size="md"
            />
          </button>
        </template>
      </Dropdown>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  Avatar,
  Dropdown,
} from 'frappe-ui'
import { apiRequest } from '../lib/api'

type FrappeResponse<T> = {
  message: T
}

type LoggedUserResponse = string

type UserProfileResponse = {
  full_name?: string
  user_image?: string
}

const route = useRoute()

const appName = 'Verto'
const appIcon = '/assets/verto/frontend/app-icon.png'

const loggedUser = ref('')
const fullName = ref('')
const userImage = ref('')

const pageTitle = computed(() => {
  const metaTitle = route.meta?.title

  if (typeof metaTitle === 'string' && metaTitle.trim()) {
    return metaTitle
  }

  return getTitleFromPath(route.path)
})

const pageSubtitle = computed(() => {
  const metaSubtitle = route.meta?.subtitle

  if (typeof metaSubtitle === 'string' && metaSubtitle.trim()) {
    return metaSubtitle
  }

  return ''
})

const appInitials = computed(() => {
  return getInitials(appName)
})

const avatarLabel = computed(() => {
  return getInitials(fullName.value || loggedUser.value || 'User')
})

const menuOptions = computed(() => {
  return [
    {
      label: fullName.value || formatFallbackUserName(loggedUser.value) || 'My Account',
      group: 'User',
      disabled: true,
    },
    {
      label: 'My Profile',
      icon: 'user',
      onClick: openProfile,
    },
    {
      label: 'Reload App',
      icon: 'refresh-cw',
      onClick: reloadApp,
    },
    {
      label: 'Log Out',
      icon: 'log-out',
      onClick: logout,
    },
  ]
})

watch(
  () => route.path,
  () => {
    document.title = `${pageTitle.value} - ${appName}`
  },
  { immediate: true }
)

function getTitleFromPath(path: string) {
  if (path === '/') return 'My Site Work'
  if (path.startsWith('/forms')) return 'Completed Forms'
  if (path.startsWith('/shifts')) return 'Shifts'
  if (path.startsWith('/chat')) return 'Chat'
  if (path.startsWith('/more')) return 'More'
  if (path.startsWith('/new')) return 'New Form'

  return appName
}

function getInitials(value: string) {
  return value
    .split(/[ ._-]/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join('')
}

function formatFallbackUserName(user?: string) {
  if (!user) return ''

  if (!user.includes('@')) {
    return user
  }

  return user
    .split('@')[0]
    .split(/[._-]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

async function loadCurrentUser() {
  try {
    const data = await apiRequest<FrappeResponse<LoggedUserResponse>>(
      '/api/method/frappe.auth.get_logged_user'
    )

    loggedUser.value = data.message || ''

    await loadUserProfile()
  } catch (err) {
    if (err instanceof Error && err.message === 'Login required') {
      return
    }

    loggedUser.value = ''
    fullName.value = ''
    userImage.value = ''
  }
}

async function loadUserProfile() {
  if (!loggedUser.value) {
    return
  }

  try {
    const filters = encodeURIComponent(JSON.stringify({ name: loggedUser.value }))
    const fieldname = encodeURIComponent(JSON.stringify(['full_name', 'user_image']))

    const data = await apiRequest<FrappeResponse<UserProfileResponse>>(
      `/api/method/frappe.client.get_value?doctype=User&filters=${filters}&fieldname=${fieldname}`
    )

    fullName.value = data.message?.full_name || ''
    userImage.value = data.message?.user_image || ''
  } catch {
    fullName.value = ''
    userImage.value = ''
  }
}

function openProfile() {
  window.location.href = '/app/user-profile'
}

async function reloadApp() {
  try {
    if ('caches' in window) {
      const cacheNames = await caches.keys()

      await Promise.all(
        cacheNames.map((cacheName) => caches.delete(cacheName))
      )
    }

    if ('serviceWorker' in navigator) {
      const registrations = await navigator.serviceWorker.getRegistrations()

      await Promise.all(
        registrations.map((registration) => registration.update())
      )
    }
  } finally {
    window.location.reload()
  }
}

async function logout() {
  try {
    await fetch('/api/method/logout', {
      method: 'POST',
      credentials: 'include',
    })
  } finally {
    window.location.href = '/login'
  }
}

onMounted(() => {
  loadCurrentUser()
})
</script>