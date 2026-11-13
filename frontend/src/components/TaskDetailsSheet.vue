<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Badge, Button } from 'frappe-ui'
import MobileFormPicker, { type MobileFormOption } from './MobileFormPicker.vue'
import MobileSheet from './MobileSheet.vue'
import { formatScheduleDate, type ScheduleTask } from '../lib/ganttSchedule'

const props = defineProps<{
  task: ScheduleTask | null
  project: string
  options: { form: MobileFormOption[]; ccv: MobileFormOption[] }
  titlesByName?: Map<string, string>
}>()

const emit = defineEmits<{ close: [] }>()
const router = useRouter()
const picker = ref<'form' | 'ccv' | null>(null)
const pickerTitle = computed(() => picker.value === 'ccv' ? 'Select CCV to Create' : 'Select Form to Create')

watch(() => props.task, () => { picker.value = null })

function closeTask() {
  picker.value = null
  emit('close')
}

function createFromPicker(option: MobileFormOption) {
  if (!props.task) return

  void router.push({
    path: `/new/${encodeURIComponent(option.mobile_doctype)}`,
    query: { link_task: props.task.name, project: props.project },
  })
}
</script>

<template>
  <MobileSheet :open="Boolean(task)" :title="picker ? pickerTitle : 'Task details'" @update:open="!$event && closeTask()">
    <MobileFormPicker
      v-if="task && picker"
      :title="pickerTitle"
      :task-title="task.title"
      :options="options[picker]"
      close-label="Back"
      @close="picker = null"
      @select="createFromPicker"
    />
    <section v-else-if="task" class="drawer-panel w-full overflow-y-auto bg-surface-base px-4 py-4 pb-[calc(env(safe-area-inset-bottom)+1rem)]">
      <div class="mx-auto max-w-2xl space-y-4">
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <h2 class="break-words text-lg-semibold text-ink-gray-9">{{ task.title }}</h2>
            <p class="mt-1 break-words text-sm text-ink-gray-6">{{ task.name }}</p>
          </div>
          <Button class="min-h-11 shrink-0" variant="subtle" @click="closeTask">Close</Button>
        </div>
        <div class="flex flex-wrap gap-2">
          <Badge v-if="task.status">{{ task.status }}</Badge>
          <Badge v-if="task.type">{{ task.type }}</Badge>
          <Badge v-if="task.isMilestone">Milestone</Badge>
        </div>
        <dl class="grid grid-cols-2 gap-3 rounded-7 border border-outline-gray-1 p-3 text-sm">
          <div>
            <dt class="text-ink-gray-6">Expected start</dt>
            <dd class="mt-1 text-ink-gray-9">{{ formatScheduleDate(task.start) }}</dd>
          </div>
          <div>
            <dt class="text-ink-gray-6">Expected end</dt>
            <dd class="mt-1 text-ink-gray-9">{{ formatScheduleDate(task.end) }}</dd>
          </div>
          <div>
            <dt class="text-ink-gray-6">Progress</dt>
            <dd class="mt-1 text-ink-gray-9">{{ task.progress }}%</dd>
          </div>
          <div v-if="task.parent" class="min-w-0">
            <dt class="text-ink-gray-6">Parent task</dt>
            <dd class="mt-1 break-words text-ink-gray-9">{{ task.parent }}</dd>
          </div>
          <div v-if="task.dependencies.length" class="col-span-2 min-w-0">
            <dt class="text-ink-gray-6">Depends on</dt>
            <dd class="mt-1 break-words text-ink-gray-9">
              {{ task.dependencies.map((id) => titlesByName?.get(id) || id).join(', ') }}
            </dd>
          </div>
        </dl>
        <div class="grid grid-cols-2 gap-2">
          <Button class="min-h-11" variant="solid" theme="gray" @click="picker = 'form'">+ Form</Button>
          <Button class="min-h-11" variant="subtle" theme="gray" @click="picker = 'ccv'">+ CCV</Button>
        </div>
      </div>
    </section>
  </MobileSheet>
</template>
