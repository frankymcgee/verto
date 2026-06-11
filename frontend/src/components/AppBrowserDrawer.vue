<!-- VERTO_APP_BROWSER_DRAWER_SLIDE_UP_2026_06_11 -->
<template>
  <Transition name="app-browser-drawer">
    <div
      v-if="open"
      class="app-browser-overlay fixed inset-0 z-[90] flex items-end bg-black/45"
      @click.self="closeBrowser"
    >
      <section class="app-browser-panel mx-auto flex h-[92dvh] w-full max-w-[var(--verto-shell-max-width,56rem)] flex-col overflow-hidden rounded-t-3xl border border-outline-gray-1 bg-surface-white shadow-2xl">
        <header class="flex shrink-0 items-center justify-between gap-3 border-b border-outline-gray-1 bg-surface-white px-4 py-3">
          <div class="min-w-0">
            <p class="truncate text-sm font-semibold text-ink-gray-9">
              {{ title || 'Browser' }}
            </p>

            <p class="mt-0.5 truncate text-xs text-ink-gray-5">
              {{ displayUrl }}
            </p>
          </div>

          <div class="flex shrink-0 items-center gap-2">
            <button
              type="button"
              class="rounded-lg border border-outline-gray-2 bg-surface-white px-3 py-1.5 text-sm font-medium text-ink-gray-7 active:scale-95"
              @click="openInNewTab"
            >
              Open
            </button>

            <button
              type="button"
              class="rounded-lg bg-surface-gray-2 px-3 py-1.5 text-sm font-semibold text-ink-gray-8 active:scale-95"
              @click="closeBrowser"
            >
              Close
            </button>
          </div>
        </header>

        <div class="relative min-h-0 flex-1 bg-surface-gray-1">
          <div
            v-if="loading"
            class="absolute inset-x-0 top-0 z-10 h-0.5 overflow-hidden bg-surface-gray-2"
          >
            <div class="browser-loading-bar h-full w-1/2 bg-blue-600" />
          </div>

          <iframe
            v-if="safeUrl"
            :key="iframeKey"
            :src="safeUrl"
            class="h-full w-full border-0 bg-surface-white"
            title="Verto browser drawer"
            @load="handleLoad"
          />

          <div
            v-else
            class="flex h-full items-center justify-center p-6 text-center"
          >
            <div class="max-w-sm rounded-2xl border border-outline-gray-1 bg-surface-white p-4 shadow-sm">
              <p class="text-sm font-semibold text-ink-gray-9">
                Could not open this link.
              </p>

              <p class="mt-1 text-sm text-ink-gray-5">
                The URL was empty or invalid.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  APP_BROWSER_OPEN_EVENT,
  type AppBrowserRequest,
} from '../lib/appBrowser'

const open = ref(false)
const url = ref('')
const title = ref('')
const loading = ref(false)
const iframeKey = ref(0)

const safeUrl = computed(() => {
  const value = String(url.value || '').trim()

  if (!value) {
    return ''
  }

  try {
    return new URL(value, window.location.origin).toString()
  } catch {
    return ''
  }
})

const displayUrl = computed(() => {
  if (!safeUrl.value) {
    return ''
  }

  try {
    const parsed = new URL(safeUrl.value)
    return `${parsed.pathname}${parsed.search}` || parsed.hostname
  } catch {
    return safeUrl.value
  }
})

function handleOpen(event: Event) {
  const detail = (event as CustomEvent<AppBrowserRequest>).detail

  if (!detail?.url) {
    return
  }

  url.value = detail.url
  title.value = detail.title || 'Browser'
  loading.value = true
  iframeKey.value += 1
  open.value = true
}

function handleLoad() {
  loading.value = false
}

function closeBrowser() {
  open.value = false
  loading.value = false
  url.value = ''
  title.value = ''
}

function openInNewTab() {
  if (!safeUrl.value) {
    return
  }

  window.open(safeUrl.value, '_blank', 'noopener,noreferrer')
}

onMounted(() => {
  window.addEventListener(APP_BROWSER_OPEN_EVENT, handleOpen)
})

onBeforeUnmount(() => {
  window.removeEventListener(APP_BROWSER_OPEN_EVENT, handleOpen)
})
</script>

<style scoped>
.app-browser-overlay {
  will-change: opacity;
}

.app-browser-panel {
  will-change: transform, opacity;
}

.app-browser-drawer-enter-active,
.app-browser-drawer-leave-active {
  transition: opacity 0.22s ease;
}

.app-browser-drawer-enter-active .app-browser-panel,
.app-browser-drawer-leave-active .app-browser-panel {
  transition:
    transform 0.28s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.22s ease;
}

.app-browser-drawer-enter-from,
.app-browser-drawer-leave-to {
  opacity: 0;
}

.app-browser-drawer-enter-from .app-browser-panel,
.app-browser-drawer-leave-to .app-browser-panel {
  opacity: 0.96;
  transform: translateY(100%);
}

.app-browser-drawer-enter-to,
.app-browser-drawer-leave-from {
  opacity: 1;
}

.app-browser-drawer-enter-to .app-browser-panel,
.app-browser-drawer-leave-from .app-browser-panel {
  opacity: 1;
  transform: translateY(0);
}

@media (prefers-reduced-motion: reduce) {
  .app-browser-drawer-enter-active,
  .app-browser-drawer-leave-active,
  .app-browser-drawer-enter-active .app-browser-panel,
  .app-browser-drawer-leave-active .app-browser-panel {
    transition: none;
  }
}

.browser-loading-bar {
  animation: browser-loading 1.1s ease-in-out infinite;
}

@keyframes browser-loading {
  0% {
    transform: translateX(-100%);
  }

  100% {
    transform: translateX(220%);
  }
}
</style>
