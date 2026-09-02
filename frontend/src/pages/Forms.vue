<template>
  <section class="h-full min-h-0 bg-surface-gray-1">
    <main class="space-y-3 px-[var(--verto-page-x,0.75rem)] py-[var(--verto-page-y,0.75rem)]">
      <!-- Filters -->
      <Card class="p-3 !py-1 !px-1">
        <div class="space-y-4">
          <div>
            <h2 class="text-sm font-semibold text-ink-gray-9">
              Filter records
            </h2>

            <p class="mt-1 text-sm text-ink-gray-5">
              Showing completed forms within the selected date range.
            </p>
          </div>

          <div class="grid grid-cols-2 gap-3 sm:grid-cols-2">
            <FormControl
              v-model="startDate"
              type="date"
              label="Start date"
              placeholder="Start date"
            />

            <FormControl
              v-model="endDate"
              type="date"
              label="End date"
              placeholder="End date"
            />
          </div>

          <div class="flex gap-2">
            <Button
              variant="solid"
              theme="gray"
              class="flex-1"
              :loading="loading"
              :disabled="loading"
              @click="fetchRecords"
            >
              Apply Filter
            </Button>

            <Button
              variant="subtle"
              theme="gray"
              :disabled="loading"
              @click="resetDateRange"
            >
              Reset
            </Button>
          </div>
        </div>
      </Card>

      <!-- Loading State -->
      <Card
        v-if="loading"
        class="p-3"
      >
        <div class="space-y-3">
          <div class="h-4 w-40 rounded bg-surface-gray-3" />
          <div class="h-28 rounded-xl bg-surface-gray-2" />
          <div class="h-28 rounded-xl bg-surface-gray-2" />
          <div class="h-28 rounded-xl bg-surface-gray-2" />
        </div>
      </Card>

      <!-- Error State -->
      <Card
        v-else-if="error"
        class="border border-red-200 bg-red-50 p-3"
      >
        <div class="space-y-2">
          <p class="text-sm font-medium text-red-800">
            Could not load completed forms
          </p>

          <p class="text-sm text-red-700">
            {{ error }}
          </p>
        </div>
      </Card>

      <!-- Empty State -->
      <Card
        v-else-if="records.length === 0"
        class="p-3"
      >
        <div class="rounded-xl border border-dashed border-outline-gray-2 bg-surface-gray-1 px-4 py-6 text-center">
          <p class="text-sm font-medium text-ink-gray-7">
            No completed forms found.
          </p>

          <p class="mt-1 text-sm text-ink-gray-5">
            Try adjusting the date range and filtering again.
          </p>
        </div>
      </Card>

      <!-- Records -->
      <div
        v-else
        class="space-y-3"
      >
        <div class="flex items-center justify-between gap-3 px-1">
          <p class="text-sm text-ink-gray-5">
            {{ records.length }} completed {{ records.length === 1 ? 'form' : 'forms' }}
          </p>

          <p class="text-sm font-medium text-ink-gray-7">
            Page {{ currentPage }} of {{ totalPages }}
          </p>
        </div>

        <Card
          v-for="record in pagedRecords"
          :key="`${record.doctype}-${record.name}`"
          class="overflow-hidden border border-outline-gray-1 bg-surface-white"
        >
          <!-- Record Header -->
          <div class="space-y-3 border-b border-outline-gray-1 px-3 py-3">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <p class="truncate text-sm font-semibold text-ink-gray-9">
                  {{ record.doctype || 'Form' }}
                </p>

                <p class="mt-0.5 truncate text-xs text-ink-gray-5">
                  {{ record.name }}
                </p>
              </div>

              <div class="shrink-0 rounded-full bg-surface-gray-2 px-2.5 py-1 text-xs font-medium text-ink-gray-7">
                {{ normalisedCompliance(record.compliance_percentage) }}
              </div>
            </div>

            <div>
              <div class="h-2 overflow-hidden rounded-full bg-surface-gray-2">
                <div
                  class="h-full rounded-full bg-blue-600 transition-all"
                  :style="{ width: normalisedCompliance(record.compliance_percentage) }"
                />
              </div>
            </div>

            <div class="flex flex-wrap gap-2 text-xs text-ink-gray-5">
              <span v-if="record.project">
                {{ record.project }}
              </span>

              <span v-if="record.project && record.creation">
                •
              </span>

              <span v-if="record.creation">
                {{ formatDateTime(record.creation) }}
              </span>
            </div>
          </div>

          <!-- Record Details -->
          <div class="space-y-3 px-3 py-3">
            <div class="space-y-2 text-sm">
              <div
                v-if="record.task"
                class="flex gap-2"
              >
                <span class="shrink-0 text-ink-gray-5">Task</span>
                <span class="min-w-0 flex-1 text-ink-gray-8">{{ record.task }}</span>
              </div>

              <div
                v-if="record.contractor || record.supervisor"
                class="flex gap-2"
              >
                <span class="shrink-0 text-ink-gray-5">Team</span>
                <span class="min-w-0 flex-1 text-ink-gray-8">
                  <template v-if="record.contractor">
                    Contractor: {{ record.contractor }}
                  </template>

                  <template v-if="record.contractor && record.supervisor">
                    |
                  </template>

                  <template v-if="record.supervisor">
                    Supervisor: {{ record.supervisor }}
                  </template>
                </span>
              </div>

              <div
                v-if="record.owner"
                class="flex gap-2"
              >
                <span class="shrink-0 text-ink-gray-5">Completed by</span>
                <span class="min-w-0 flex-1 text-ink-gray-8">{{ record.owner }}</span>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-2 pt-1">
              <Button
                variant="subtle"
                theme="gray"
                :loading="downloadingKey === getRecordKey(record)"
                :disabled="Boolean(downloadingKey)"
                @click="downloadPdf(record)"
              >
                Download
              </Button>

              <Button
                variant="subtle"
                theme="gray"
                @click="editRecord(record)"
              >
                Edit
              </Button>
            </div>
          </div>
        </Card>

        <!-- Pagination -->
        <Card
          v-if="totalPages > 1"
          class="p-3"
        >
          <div class="flex items-center justify-between gap-3">
            <Button
              variant="subtle"
              theme="gray"
              :disabled="currentPage === 1"
              @click="previousPage"
            >
              Prev
            </Button>

            <p class="text-sm font-medium text-ink-gray-7">
              Page {{ currentPage }} of {{ totalPages }}
            </p>

            <Button
              variant="subtle"
              theme="gray"
              :disabled="currentPage === totalPages"
              @click="nextPage"
            >
              Next
            </Button>
          </div>
        </Card>
      </div>
    </main>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Button,
  Card,
  FormControl,
} from 'frappe-ui'
import { apiRequest } from '../lib/api'
import { withCsrfHeaders } from '../lib/csrf'

type FrappeResponse<T> = {
  message: T
}

type CompletedFormRecord = {
  doctype: string
  name: string
  mobile_doctype?: string
  mobile_doctype_name?: string
  mobile_form?: string
  project?: string
  creation?: string
  compliance_percentage?: string | number | null
  task?: string
  contractor?: string
  supervisor?: string
  owner?: string
  link?: string
}

const router = useRouter()

const pageSize = 5

const loading = ref(true)
const error = ref('')
const records = ref<CompletedFormRecord[]>([])
const currentPage = ref(1)
const startDate = ref('')
const endDate = ref('')
const downloadingKey = ref('')

const totalPages = computed(() => {
  return Math.max(1, Math.ceil(records.value.length / pageSize))
})

const pagedRecords = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  const end = start + pageSize

  return records.value.slice(start, end)
})

function getDefaultDateRange() {
  const today = new Date()
  const fourWeeksAgo = new Date()

  fourWeeksAgo.setDate(today.getDate() - 28)

  return {
    start_date: formatDateForInput(fourWeeksAgo),
    end_date: formatDateForInput(today),
  }
}

function formatDateForInput(date: Date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')

  return `${year}-${month}-${day}`
}

function resetDateRange() {
  const range = getDefaultDateRange()

  startDate.value = range.start_date
  endDate.value = range.end_date

  fetchRecords()
}

function getRecordKey(record: CompletedFormRecord) {
  return `${record.doctype}-${record.name}`
}

function normalisedCompliance(value: CompletedFormRecord['compliance_percentage']) {
  if (value === null || value === undefined || value === '') {
    return '0%'
  }

  if (typeof value === 'number') {
    return `${Math.max(0, Math.min(100, value))}%`
  }

  const stringValue = String(value).trim()

  if (stringValue.endsWith('%')) {
    const numberValue = Number(stringValue.replace('%', ''))

    if (Number.isFinite(numberValue)) {
      return `${Math.max(0, Math.min(100, numberValue))}%`
    }

    return '0%'
  }

  const numberValue = Number(stringValue)

  if (!Number.isFinite(numberValue)) {
    return '0%'
  }

  return `${Math.max(0, Math.min(100, numberValue))}%`
}

function formatDateTime(value?: string) {
  if (!value) {
    return ''
  }

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat(undefined, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function previousPage() {
  if (currentPage.value <= 1) {
    return
  }

  currentPage.value -= 1
}

function nextPage() {
  if (currentPage.value >= totalPages.value) {
    return
  }

  currentPage.value += 1
}

function getMobileDoctypeForRecord(record: CompletedFormRecord) {
  return (
    record.mobile_doctype ||
    record.mobile_doctype_name ||
    record.mobile_form ||
    record.doctype
  )
}

function editRecord(record: CompletedFormRecord) {
  const mobileDoctype = getMobileDoctypeForRecord(record)

  if (!mobileDoctype || !record.name) {
    error.value = 'Could not determine which form to edit.'
    return
  }

  router.push({
    path: `/edit/${encodeURIComponent(mobileDoctype)}/${encodeURIComponent(record.name)}`,
  })
}

async function fetchRecords() {
  loading.value = true
  error.value = ''

  try {
    const payload = new FormData()

    if (startDate.value) {
      payload.append('start_date', startDate.value)
    }

    if (endDate.value) {
      payload.append('end_date', endDate.value)
    }

    const data = await apiRequest<FrappeResponse<CompletedFormRecord[]>>(
      '/api/method/verto.api.fetch_records.fetch_created_records',
      {
        method: 'POST',
        body: payload,
      }
    )

    records.value = data.message || []
    currentPage.value = 1
  } catch (err) {
    if (err instanceof Error && err.message === 'Login required') {
      return
    }

    error.value = err instanceof Error ? err.message : 'Could not load completed forms.'
  } finally {
    loading.value = false
  }
}

async function downloadPdf(record: CompletedFormRecord) {
  const recordKey = getRecordKey(record)

  downloadingKey.value = recordKey

  try {
    const response = await fetch('/api/method/verto.api.fetch_records.open_pdf', {
      method: 'POST',
      credentials: 'include',
      body: JSON.stringify({
        doctype: record.doctype,
        name: record.name,
      }),
      headers: withCsrfHeaders(
        { 'Content-Type': 'application/json' },
        'POST'
      ),
    })

    if (response.status === 401 || response.status === 403) {
      window.location.href = `/login?redirect-to=${encodeURIComponent(window.location.pathname)}`
      throw new Error('Login required')
    }

    if (!response.ok) {
      throw new Error(`Failed to generate PDF for ${record.name}`)
    }

    const pdfBlob = await response.blob()
    const pdfUrl = URL.createObjectURL(pdfBlob)
    const downloadLink = document.createElement('a')

    downloadLink.href = pdfUrl
    downloadLink.download = `${record.doctype}_${record.name}.pdf`

    document.body.appendChild(downloadLink)
    downloadLink.click()
    document.body.removeChild(downloadLink)

    URL.revokeObjectURL(pdfUrl)
  } catch (err) {
    if (err instanceof Error && err.message === 'Login required') {
      return
    }

    error.value = err instanceof Error ? err.message : 'Could not download PDF.'
  } finally {
    downloadingKey.value = ''
  }
}

onMounted(() => {
  const range = getDefaultDateRange()

  startDate.value = range.start_date
  endDate.value = range.end_date

  fetchRecords()
})
</script>
