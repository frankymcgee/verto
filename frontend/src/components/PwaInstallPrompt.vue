<!-- VERTO_PWA_INSTALL_PROMPT_SETTINGS_FIX_2026_06_11 -->
<template>
  <Transition name="drawer-fade-slide">
    <div
      v-if="canShowPrompt"
      class="fixed inset-0 z-[90] flex items-end bg-black/40 px-0"
      @click.self="dismissPrompt"
    >
      <div
        class="drawer-panel w-full overflow-hidden rounded-b-none rounded-t-3xl border border-outline-gray-1 bg-surface-white shadow-2xl"
      >
        <div class="border-b border-outline-gray-1 px-4 py-3">
          <div class="flex items-center justify-between gap-3">
            <div class="flex min-w-0 items-center gap-3">
              <div class="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-2xl bg-surface-gray-2">
                <img
                  v-if="resolvedAppIcon"
                  :src="resolvedAppIcon"
                  :alt="`${resolvedAppName} icon`"
                  class="h-full w-full object-cover"
                  @error="iconFailed = true"
                />

                <span
                  v-else
                  class="text-sm font-bold text-ink-gray-7"
                >
                  {{ appInitials }}
                </span>
              </div>

              <div class="min-w-0">
                <h2 class="truncate text-base font-semibold text-ink-gray-9">
                  Install {{ resolvedAppName }}
                </h2>

                <p class="mt-0.5 truncate text-sm text-ink-gray-5">
                  {{ resolvedShortDescription }}
                </p>
              </div>
            </div>

            <button
              type="button"
              class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-gray-1 text-xl leading-none text-ink-gray-6 active:scale-95"
              aria-label="Close install prompt"
              @click="dismissPrompt"
            >
              ×
            </button>
          </div>
        </div>

        <div class="space-y-4 p-4 pb-[calc(env(safe-area-inset-bottom)+1rem)]">
          <div class="rounded-2xl bg-surface-gray-1 p-3">
            <p class="text-sm text-ink-gray-7">
              {{ resolvedInstallMessage }}
            </p>
          </div>

          <template v-if="isIOS && !installPromptAvailable">
            <div class="space-y-3">
              <p class="text-sm font-medium text-ink-gray-9">
                Install on iPhone or iPad
              </p>

              <ol class="space-y-2 text-sm text-ink-gray-7">
                <li class="flex gap-2">
                  <span class="font-semibold text-ink-gray-9">1.</span>
                  <span>Tap the Safari Share button.</span>
                </li>

                <li class="flex gap-2">
                  <span class="font-semibold text-ink-gray-9">2.</span>
                  <span>Choose <strong>Add to Home Screen</strong>.</span>
                </li>

                <li class="flex gap-2">
                  <span class="font-semibold text-ink-gray-9">3.</span>
                  <span>Confirm the name and tap <strong>Add</strong>.</span>
                </li>
              </ol>
            </div>

            <Button
              variant="solid"
              theme="gray"
              size="lg"
              class="w-full justify-center"
              @click="dismissPrompt"
            >
              Got it
            </Button>
          </template>

          <template v-else>
            <Button
              variant="solid"
              theme="gray"
              size="lg"
              class="w-full justify-center"
              :loading="installing"
              :disabled="installing"
              @click="install"
            >
              Install {{ resolvedAppName }}
            </Button>

            <Button
              variant="subtle"
              theme="gray"
              size="lg"
              class="w-full justify-center"
              :disabled="installing"
              @click="dismissPrompt"
            >
              Maybe later
            </Button>
          </template>

          <p
            v-if="error"
            class="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
          >
            {{ error }}
          </p>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Button } from 'frappe-ui'
import { useMobileBoot } from '../lib/mobileBoot'
import { usePwaInstallPrompt } from '../pwa/usePwaInstallPrompt'

const {
  loadMobileBoot,
  appName,
  appIconUrl,
} = useMobileBoot()

const {
  canShowPrompt,
  installPromptAvailable,
  installing,
  error,
  isIOS,
  install,
  dismissPrompt,
} = usePwaInstallPrompt()

const iconFailed = ref(false)

loadMobileBoot()

watch(
  () => appIconUrl.value,
  () => {
    iconFailed.value = false
  }
)

const resolvedAppName = computed(() => {
  return String(appName.value || '').trim() || 'MSS'
})

const resolvedAppIcon = computed(() => {
  if (iconFailed.value) {
    return ''
  }

  return String(appIconUrl.value || '').trim()
})

const resolvedShortDescription = computed(() => {
  return `${resolvedAppName.value} works better when installed.`
})

const resolvedInstallMessage = computed(() => {
  return `Install ${resolvedAppName.value} to your device for faster access, a full-screen app experience, and future offline and notification features.`
})

const appInitials = computed(() => {
  const words = resolvedAppName.value
    .split(/[ ._-]+/)
    .map((word) => word.trim())
    .filter(Boolean)

  if (!words.length) {
    return 'M'
  }

  if (words.length === 1) {
    return words[0].slice(0, 2).toUpperCase()
  }

  return `${words[0][0]}${words[1][0]}`.toUpperCase()
})
</script>

<style scoped>
.drawer-fade-slide-enter-active,
.drawer-fade-slide-leave-active {
  transition: opacity 0.2s ease;
}

.drawer-fade-slide-enter-from,
.drawer-fade-slide-leave-to {
  opacity: 0;
}

.drawer-fade-slide-enter-active .drawer-panel,
.drawer-fade-slide-leave-active .drawer-panel {
  transition:
    transform 0.24s ease,
    opacity 0.24s ease;
}

.drawer-fade-slide-enter-from .drawer-panel,
.drawer-fade-slide-leave-to .drawer-panel {
  opacity: 0;
  transform: translateY(100%);
}

.drawer-fade-slide-enter-to .drawer-panel,
.drawer-fade-slide-leave-from .drawer-panel {
  opacity: 1;
  transform: translateY(0);
}

@media (prefers-reduced-motion: reduce) {
  .drawer-fade-slide-enter-active,
  .drawer-fade-slide-leave-active,
  .drawer-fade-slide-enter-active .drawer-panel,
  .drawer-fade-slide-leave-active .drawer-panel {
    transition: none;
  }
}
</style>
