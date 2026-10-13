<template>
  <div v-if="reminders.length" class="shrink-0 border-b border-amber-200 bg-amber-50 px-3 py-2" role="status">
    <button
      type="button"
      class="flex w-full items-center justify-between gap-3 text-left text-sm text-amber-950"
      aria-haspopup="dialog"
      @click="open = true"
    >
      <span><strong>{{ reminders.length }} {{ reminders.length === 1 ? 'shift needs' : 'shifts need' }} hours</strong> · Please complete your daily timesheet.</span>
      <span class="shrink-0 font-semibold underline">Review</span>
    </button>
  </div>

  <MobileSheet :open="open && reminders.length > 0" title="Missing timesheet hours" @update:open="open = $event">
      <section
        class="drawer-panel flex max-h-[80dvh] w-full flex-col bg-surface-base"
      >
        <header class="flex shrink-0 items-center justify-between gap-3 border-b border-gray-200 px-4 py-3">
          <h2 id="missing-hours-title" class="text-base font-semibold">Missing timesheet hours</h2>
          <button type="button" class="rounded-lg bg-gray-100 px-3 py-2 text-sm font-semibold" @click="open = false">Close</button>
        </header>
        <div class="min-h-0 overflow-y-auto px-4 py-3 pb-[max(env(safe-area-inset-bottom,0px),1rem)]">
          <p class="mb-3 text-sm text-gray-600">These reminders stay until your hours are saved. Hours saved offline will clear after they sync.</p>
          <ul class="space-y-2">
            <li v-for="reminder in reminders" :key="reminder.name">
              <button type="button" class="flex w-full items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-left" @click="reviewShift(reminder)">
                <span class="min-w-0">
                  <span class="block font-semibold">{{ formatDate(reminder.date) }} · {{ reminder.shift_type }}</span>
                  <span v-if="reminder.project_name || reminder.project" class="block break-words text-sm text-gray-600">{{ reminder.project_name || reminder.project }}</span>
                </span>
                <span class="shrink-0 text-sm font-semibold text-amber-900">Enter hours →</span>
              </button>
            </li>
          </ul>
        </div>
      </section>
  </MobileSheet>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { apiRequest } from '../lib/api'
import { useMobileBoot } from '../lib/mobileBoot'
import MobileSheet from './MobileSheet.vue'

type Reminder = { name: string; date: string; shift_type: string; project: string; project_name?: string; shift_assignment: string }
const { boot } = useMobileBoot()
const router = useRouter()
const reminders = ref<Reminder[]>([])
const open = ref(false)
let stopped = false
let reading = false
let refreshAgain = false
let timer: ReturnType<typeof setInterval> | undefined

function formatDate(value: string) {
  return new Date(`${value}T12:00:00`).toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })
}

function reviewShift(reminder: Reminder) {
  open.value = false
  void router.push({ path: '/shifts', query: { date: reminder.date, shift: reminder.shift_assignment } })
}

async function refresh() {
  if (stopped || !boot.value.navigation_access?.has_employee_profile || document.hidden || !navigator.onLine) return
  if (reading) { refreshAgain = true; return }
  reading = true
  try {
    const response = await apiRequest<{ message: { reminders: Reminder[] } }>(
      '/api/method/verto.api.mobile.timesheet_reminders.get_my_missing_hours_reminders'
    )
    if (!stopped) {
      reminders.value = response.message.reminders || []
      if (!reminders.value.length) open.value = false
    }
  } catch {
    // Keep the previous reminder during connectivity/server failures.
  } finally {
    reading = false
    if (refreshAgain && !stopped) { refreshAgain = false; void refresh() }
  }
}

watch(() => boot.value.navigation_access?.has_employee_profile, (hasProfile) => {
  if (hasProfile) void refresh()
  else { reminders.value = []; open.value = false }
}, { immediate: true })
watch(() => router.currentRoute.value.fullPath, () => { void refresh() })

onMounted(() => {
  timer = setInterval(() => { void refresh() }, 60_000)
  window.addEventListener('focus', refresh)
  window.addEventListener('online', refresh)
  window.addEventListener('verto:timesheet-saved', refresh)
  window.addEventListener('verto:offline-queue-synced', refresh)
  document.addEventListener('visibilitychange', refresh)
})
onBeforeUnmount(() => {
  stopped = true
  clearInterval(timer)
  window.removeEventListener('focus', refresh)
  window.removeEventListener('online', refresh)
  window.removeEventListener('verto:timesheet-saved', refresh)
  window.removeEventListener('verto:offline-queue-synced', refresh)
  document.removeEventListener('visibilitychange', refresh)
})
</script>
