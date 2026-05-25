<template>
  <section class="space-y-4 p-4">
    <div>
      <p class="text-sm text-gray-500">Field tools</p>
      <h1 class="text-2xl font-semibold">Forms</h1>
    </div>

    <div
      v-if="loading"
      class="rounded-2xl bg-white p-4 shadow-sm"
    >
      Loading forms...
    </div>

    <div
      v-else-if="error"
      class="rounded-2xl bg-red-50 p-4 text-sm text-red-700"
    >
      {{ error }}
    </div>

    <div
      v-else
      class="space-y-3"
    >
      <button
        v-for="form in forms"
        :key="form.doctype"
        type="button"
        class="w-full rounded-2xl bg-white p-4 text-left shadow-sm active:scale-[0.99]"
        @click="openForm(form.route)"
      >
        <div class="flex items-start justify-between gap-3">
          <div>
            <p class="text-sm text-gray-500">{{ form.category }}</p>
            <h2 class="mt-1 text-base font-semibold text-gray-900">
              {{ form.label }}
            </h2>
            <p class="mt-1 text-sm text-gray-500">
              {{ form.description }}
            </p>
          </div>

          <div class="rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-600">
            New
          </div>
        </div>
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { apiRequest } from '../lib/api'

type MobileForm = {
  label: string
  doctype: string
  description: string
  icon: string
  route: string
  category: string
}

type FormsPayload = {
  forms: MobileForm[]
}

type FrappeResponse<T> = {
  message: T
}

const loading = ref(true)
const error = ref('')
const forms = ref<MobileForm[]>([])

function openForm(route: string) {
  window.location.href = route
}

async function loadForms() {
  loading.value = true
  error.value = ''

  try {
    const data = await apiRequest<FrappeResponse<FormsPayload>>(
      '/api/method/verto.api.mobile.forms.get_mobile_forms'
    )

    forms.value = data.message.forms
  } catch (err) {
    if (err instanceof Error && err.message === 'Login required') {
      return
    }

    error.value = err instanceof Error ? err.message : 'Could not load forms.'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadForms()
})
</script>