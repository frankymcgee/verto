<template>
  <div
    v-if="shouldPrompt"
    class="mx-auto w-full max-w-[var(--verto-shell-max-width,28rem)] px-[var(--verto-page-x,0.75rem)] pt-2"
  >
    <div class="relative rounded-xl border border-blue-200 bg-blue-50 px-3 py-3 text-blue-950 shadow-sm">
      <button
        type="button"
        class="absolute right-2 top-2 flex h-7 w-7 items-center justify-center rounded-full text-blue-700 hover:bg-blue-100 active:scale-95"
        aria-label="Dismiss notification prompt"
        @click="dismissPushPrompt"
      >
        ×
      </button>

      <div class="pr-8">
        <p class="text-sm font-semibold">
          Enable Verto notifications
        </p>

        <p class="mt-1 text-xs leading-5 text-blue-800">
          <template v-if="needsIosInstall">
            Add Verto to your Home Screen, open the installed app, then enable notifications here.
          </template>

          <template v-else-if="permission === 'denied'">
            Notifications are blocked. Allow them in this app’s site settings to continue.
          </template>

          <template v-else>
            Receive shift, assignment and allocated-project chat updates on this device.
          </template>
        </p>

        <p
          v-if="error"
          class="mt-1 text-xs text-red-700"
        >
          {{ error }}
        </p>

        <button
          v-if="!needsIosInstall && permission !== 'denied'"
          type="button"
          class="mt-2 rounded-lg bg-blue-700 px-3 py-1.5 text-xs font-semibold text-white shadow-sm active:scale-95 disabled:opacity-60"
          :disabled="enabling || loading"
          @click="enablePushNotifications"
        >
          {{ enabling ? 'Enabling…' : 'Enable notifications' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { usePushNotifications } from '../pwa/usePushNotifications'

const {
  loading,
  enabling,
  permission,
  error,
  needsIosInstall,
  shouldPrompt,
  initialisePushNotifications,
  enablePushNotifications,
  dismissPushPrompt,
} = usePushNotifications()

onMounted(() => {
  void initialisePushNotifications()
})
</script>
