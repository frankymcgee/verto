<template>
  <Teleport to="body">
    <Transition name="about-toast">
      <div
        v-if="open"
        class="about-toast fixed inset-x-0 bottom-0 z-[100] w-full border border-b-0 border-outline-gray-1 bg-surface-white px-4 pt-4 pb-[calc(env(safe-area-inset-bottom)+1rem)] shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-label="About Verto"
      >
        <div class="mx-auto w-full max-w-md">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <h2 class="text-base font-semibold text-ink-gray-9">About</h2>
              <p class="mt-1 text-sm text-ink-gray-5">Verto Mobile</p>
            </div>
            <button type="button" class="shrink-0 rounded-md px-2 py-1 text-sm font-medium text-ink-gray-5 hover:bg-surface-gray-2 hover:text-ink-gray-8" @click="emit('close')">Close</button>
          </div>

          <div class="mt-4 overflow-hidden rounded-xl border border-outline-gray-1 bg-surface-gray-1">
            <div class="grid grid-cols-[7.5rem_minmax(0,1fr)] gap-3 border-b border-outline-gray-1 px-3 py-2.5 text-sm">
              <span class="font-medium text-ink-gray-6">Company name</span>
              <span class="break-words text-right font-semibold text-ink-gray-9">{{ loading ? 'Loading…' : companyName || 'Not configured' }}</span>
            </div>
            <div class="grid grid-cols-[7.5rem_minmax(0,1fr)] gap-3 px-3 py-2.5 text-sm">
              <span class="font-medium text-ink-gray-6">App version</span>
              <span class="text-right font-semibold text-ink-gray-9">{{ loading ? 'Loading…' : appVersion || 'Unavailable' }}</span>
            </div>
          </div>

          <p v-if="error" class="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{{ error }}</p>
          <p class="mt-4 text-center text-xs text-ink-gray-5">{{ copyrightText || 'Copyright 2026 Webwire Pty Ltd' }}</p>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { apiRequest } from '../lib/api'

type AboutInfo = { company_name?: string; app_version?: string; copyright?: string }
type FrappeResponse<T> = { message: T }

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()
const loading = ref(false)
const error = ref('')
const companyName = ref('')
const appVersion = ref('')
const copyrightText = ref('Copyright 2026 Webwire Pty Ltd')

async function loadAboutInfo() {
  loading.value = true
  error.value = ''
  try {
    const response = await apiRequest<FrappeResponse<AboutInfo>>('/api/method/verto.api.mobile.about.get_about_info')
    companyName.value = String(response.message?.company_name || '').trim()
    appVersion.value = String(response.message?.app_version || '').trim()
    copyrightText.value = String(response.message?.copyright || 'Copyright 2026 Webwire Pty Ltd').trim()
  } catch (err) {
    if (err instanceof Error && err.message === 'Login required') return
    error.value = err instanceof Error ? err.message : 'Could not load app information.'
  } finally {
    loading.value = false
  }
}

watch(() => props.open, (isOpen) => {
  if (isOpen) void loadAboutInfo()
})
</script>

<style scoped>
.about-toast {
  max-height: calc(100dvh - max(env(safe-area-inset-top, 0px), 0.75rem));
  overflow-x: hidden;
  overflow-y: auto;
  touch-action: pan-y;
  -webkit-overflow-scrolling: touch;
}
.about-toast-enter-active, .about-toast-leave-active { transition: opacity 0.18s ease, transform 0.18s ease; }
.about-toast-enter-from, .about-toast-leave-to { opacity: 0; transform: translateY(100%); }
@media (prefers-reduced-motion: reduce) { .about-toast-enter-active, .about-toast-leave-active { transition: none; } }
</style>
