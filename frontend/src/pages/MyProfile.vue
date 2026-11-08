<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Button } from 'frappe-ui'
import { apiRequest } from '../lib/api'
import { useMobileBoot } from '../lib/mobileBoot'

type Profile = {
  user: { full_name?: string; email?: string; mobile_no?: string; phone?: string }
  employee: {
    name: string; employee_name?: string; employee_number?: string
    company?: string; department?: string; designation?: string; employment_type?: string
    branch?: string; status?: string; date_of_joining?: string
    company_email?: string; personal_email?: string; cell_number?: string
  } | null
}

const router = useRouter()
const { userFullname, userImageUrl } = useMobileBoot()
const profile = ref<Profile | null>(null)
const loading = ref(true)
const error = ref('')
const imageFailed = ref(false)
const fullName = computed(() => profile.value?.employee?.employee_name || profile.value?.user.full_name || userFullname.value)
const initials = computed(() => fullName.value.trim().split(/\s+/).filter(Boolean).slice(0, 2).map(word => word[0]).join('').toUpperCase() || 'U')

function formatDate(value?: string) {
  if (!value) return ''
  const date = new Date(`${value.slice(0, 10)}T00:00:00`)
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(undefined, {
    day: 'numeric', month: 'short', year: 'numeric',
  }).format(date)
}

const sections = computed(() => {
  const account = profile.value?.user
  const employee = profile.value?.employee
  return [
    { title: 'Account details', rows: [
      ['Full name', account?.full_name], ['Email address', account?.email],
      ['Mobile number', account?.mobile_no], ['Phone number', account?.phone],
    ] },
    ...(employee ? [{ title: 'Employment details', rows: [
      ['Employee ID', employee.name],
      ...(employee.employee_number ? [['Employee number', employee.employee_number]] : []),
      ['Employee name', employee.employee_name], ['Company', employee.company],
      ['Department', employee.department], ['Designation', employee.designation],
      ['Employment type', employee.employment_type], ['Branch', employee.branch],
      ['Status', employee.status], ['Date of joining', formatDate(employee.date_of_joining)],
    ] }, { title: 'Employee contact details', rows: [
      ['Work email', employee.company_email], ['Personal email', employee.personal_email],
      ['Mobile number', employee.cell_number],
    ] }] : []),
  ]
})

async function loadProfile() {
  loading.value = true
  error.value = ''
  try {
    const response = await apiRequest<{ message: Profile }>(
      '/api/method/verto.api.mobile.profile.get_my_profile', { cache: 'no-store' },
    )
    profile.value = response.message
  } catch {
    error.value = 'Could not load your profile. Check your connection and try again.'
  } finally {
    loading.value = false
  }
}

onMounted(loadProfile)
</script>

<template>
  <section class="mx-auto max-w-3xl space-y-4 px-[var(--verto-page-x,0.75rem)] py-[var(--verto-page-y,0.75rem)] pb-8" :aria-busy="loading">
    <div class="flex items-center justify-between gap-3">
      <h1 class="text-xl-semibold text-ink-gray-9">My profile</h1>
      <Button variant="subtle" @click="router.push('/')">Home</Button>
    </div>
    <p class="text-sm text-ink-gray-6">View your account and employee information. Contact your administrator if any details need updating.</p>

    <p v-if="loading" role="status" class="py-6 text-sm text-ink-gray-6">Loading your profile…</p>
    <div v-else-if="error" class="space-y-3 rounded-7 border border-outline-gray-1 bg-surface-base p-4">
      <p role="alert" class="text-sm text-ink-red-4">{{ error }}</p>
      <Button variant="subtle" @click="loadProfile">Try again</Button>
    </div>
    <template v-else-if="profile">
      <div class="flex items-center gap-3 rounded-7 border border-outline-gray-1 bg-surface-base p-4">
        <div class="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-full bg-surface-gray-2 text-xl-semibold text-ink-gray-7">
          <img v-if="userImageUrl && !imageFailed" :src="userImageUrl" :alt="fullName" class="h-full w-full object-cover" @error="imageFailed = true" />
          <span v-else aria-hidden="true">{{ initials }}</span>
        </div>
        <div class="min-w-0">
          <p class="break-words text-lg-semibold text-ink-gray-9">{{ fullName }}</p>
          <p v-if="profile.employee" class="break-words text-sm text-ink-gray-6">{{ profile.employee.name }}</p>
        </div>
      </div>

      <div v-for="section in sections" :key="section.title" class="overflow-hidden rounded-7 border border-outline-gray-1 bg-surface-base">
        <h2 class="border-b border-outline-gray-1 px-4 py-3 text-base-semibold text-ink-gray-9">{{ section.title }}</h2>
        <dl class="divide-y divide-outline-gray-1 px-4">
          <div v-for="[label, value] in section.rows" :key="label" class="grid gap-1 py-3 sm:grid-cols-2 sm:gap-4">
            <dt class="text-sm text-ink-gray-6">{{ label }}</dt>
            <dd class="min-w-0 whitespace-pre-wrap break-words text-sm-medium text-ink-gray-9">{{ value || 'Not set' }}</dd>
          </div>
        </dl>
      </div>
      <p v-if="!profile.employee" class="rounded-7 border border-outline-gray-1 bg-surface-base p-4 text-sm text-ink-gray-6">No employee record is linked to your account.</p>
    </template>
  </section>
</template>
