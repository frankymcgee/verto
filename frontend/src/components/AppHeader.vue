<template>
  <header class="sticky top-0 z-40 border-b border-outline-gray-1 bg-surface-white/95 backdrop-blur">
    <div class="mx-auto flex max-w-md items-center justify-between gap-3 px-3 py-2">
      <!-- Left: App icon + current page -->
      <div class="flex min-w-0 items-center gap-2">
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

      <!-- Right: User menu -->
      <div class="relative shrink-0">
        <button
          type="button"
          class="flex h-9 w-9 items-center justify-center overflow-hidden rounded-full border border-outline-gray-2 bg-surface-gray-1 text-sm font-semibold text-ink-gray-8 active:scale-95"
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
          class="absolute right-0 mt-2 w-56 overflow-hidden rounded-xl border border-outline-gray-1 bg-surface-white shadow-lg"
        >
          <div class="border-b border-outline-gray-1 px-3 py-2">
            <div class="flex items-center gap-2">
              <div class="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-full bg-surface-gray-2 text-sm font-semibold text-ink-gray-8">
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

const route = useRoute()

const {
  appName,
  appIconUrl,
  user,
  userFullname,
  userImageUrl,
  reloadMobileBoot,
} = useMobileBoot()

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
  window.location.href = '/app/user-profile'
}

function logout() {
  menuOpen.value = false
  window.location.href = '/logout'
}
</script>